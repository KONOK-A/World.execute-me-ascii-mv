"""Music data, exact cue semantics and offline DSP; no player integration needed."""
import ast
from dataclasses import FrozenInstanceError
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import wave


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CHANNELS = ('energy', 'low', 'mid', 'high', 'onset')


def runtime():
    import music
    return music


def fixture(root):
    features = {
        'version': 1, 'duration': 4.0, 'source': {'sha256': 'a' * 64},
        'times': [0.0, 1.0, 3.0, 4.0],
        **{name: [0.0, 1.0, 0.5, 0.0] for name in CHANNELS},
    }
    score = {
        'version': 1, 'duration': 4.0, 'source': {'sha256': 'a' * 64},
        'sections': [{'time': 0.0, 'label': 'boot'}, {'time': 2.0, 'label': 'love'}],
        'beats': [{'time': t, 'strength': 1.0} for t in (0.5, 1.0, 2.0, 3.0)],
        'events': [
            {'time': 1.0, 'kind': 'execution', 'label': 'one', 'strength': 1.0},
            {'time': 2.0, 'kind': 'execution', 'label': 'two', 'strength': 0.8},
            {'time': 2.0, 'kind': 'transition', 'label': 'love_start', 'strength': 1.0},
        ],
    }
    for name, data in [('music_features.json', features), ('score.json', score)]:
        (root / name).write_text(json.dumps(data), encoding='utf-8')
    return features, score


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('music'), 'music.py is required')
        self.music = runtime()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.features, self.score = fixture(self.root)

    def timeline(self):
        return self.music.MusicTimeline(self.root)

    def rewrite(self, filename, data):
        (self.root / filename).write_text(json.dumps(data), encoding='utf-8')

    def test_interpolates_using_actual_timestamps_and_clamps_endpoints(self):
        timeline = self.timeline()
        for time, want in [(-1, 0), (0, 0), (0.5, 0.5), (1, 1), (2, 0.75), (4, 0), (9, 0)]:
            with self.subTest(time=time):
                state = timeline.at(time)
                for name in CHANNELS:
                    self.assertAlmostEqual(getattr(state, name), want)
        self.assertEqual(timeline.at(-1).time, 0)
        self.assertEqual(timeline.at(9).time, 4)

    def test_cues_include_future_events_but_latest_lookup_never_fires_early(self):
        timeline = self.timeline()
        before = timeline.at(0.999999)
        self.assertEqual(len(before.events('execution')), 2)
        self.assertIsNone(before.event('execution'))
        self.assertEqual(before.event_age('execution'), math.inf)
        self.assertEqual(before.anchor('love_start'), 2)
        self.assertEqual(timeline.at(1).event('execution').label, 'one')
        self.assertEqual(timeline.at(2).event('execution').label, 'two')
        self.assertEqual(timeline.at(2.25).event_age('execution'), 0.25)
        self.assertEqual(before.events('absent'), ())
        with self.assertRaises(KeyError):
            before.anchor('absent')

    def test_defaults_and_nested_cues_are_immutable(self):
        event = self.music.MusicEvent(1, 'accent', 'hit', 1)
        cues = [event]
        state = self.music.MusicState(cues=cues)
        cues.clear()
        self.assertEqual(state.events('accent'), (event,))
        self.assertEqual(state.energy, 0)
        with self.assertRaises(FrozenInstanceError):
            state.time = 2
        with self.assertRaises(FrozenInstanceError):
            event.time = 2

    def test_beats_are_continuous_across_irregular_intervals_and_half_time(self):
        timeline = self.timeline()
        for time, position in [(0, -1), (0.5, 0), (0.75, 0.5), (1, 1), (1.5, 1.5),
                               (2, 2), (2.5, 2.5), (3, 3), (3.5, 3.5)]:
            state = timeline.at(time)
            self.assertAlmostEqual(state.beat_position, position)
            self.assertAlmostEqual(state.beat_phase, position % 1)
        for boundary in (0.5, 1, 2, 3):
            left = timeline.at(boundary - 1e-7).beat_position / 2
            right = timeline.at(boundary + 1e-7).beat_position / 2
            self.assertLess(right - left, 1e-6)
        self.assertEqual(timeline.at(0.49).beat, 0)
        self.assertEqual(timeline.at(1).beat, 1)
        self.assertLess(timeline.at(1.1).beat, timeline.at(1).beat)

    def test_section_and_semantic_envelope_change_exactly_at_cues(self):
        timeline = self.timeline()
        self.assertEqual(timeline.at(1.99999).section, 'boot')
        self.assertEqual(timeline.at(2).section, 'love')
        self.assertEqual(timeline.at(0.99999).accent, 0)
        self.assertEqual(timeline.at(1).accent, 1)
        self.assertLess(timeline.at(1.2).accent, timeline.at(1.1).accent)

    def test_lookup_is_seek_order_independent(self):
        timeline = self.timeline()
        points = (0, 0.49, 0.5, 1, 1.75, 2, 3.5, 4)
        expected = {t: timeline.at(t) for t in points}
        for t in reversed(points * 3):
            self.assertEqual(timeline.at(t), expected[t])

    def test_missing_assets_and_mismatched_source_fail_loudly(self):
        self.score['source']['sha256'] = 'b' * 64
        self.rewrite('score.json', self.score)
        with self.assertRaisesRegex(ValueError, 'source|hash'):
            self.timeline()
        (self.root / 'score.json').unlink()
        with self.assertRaises(FileNotFoundError):
            self.timeline()

    def test_invalid_features_are_rejected(self):
        for field, value in [('times', [0, 1, 1, 4]), ('times', [0, 1, 3]),
                             ('times', [0.1, 1, 3, 4]), ('times', [0, 1, 3, 3.9]),
                             ('energy', [0, math.nan, 0.5, 0]),
                             ('onset', [0, 1.1, 0.5, 0]), ('low', [0, -0.1, 0.5, 0]),
                             ('mid', [0, 1]), ('duration', 0)]:
            with self.subTest(field=field, value=value):
                features = dict(self.features, **{field: value})
                self.rewrite('music_features.json', features)
                with self.assertRaises(ValueError):
                    self.timeline()

    def test_invalid_score_order_and_duplicate_anchors_are_rejected(self):
        for key, value in [('beats', []), ('beats', [self.score['beats'][0]] * 2),
                           ('sections', [{'time': 1, 'label': 'late'}]),
                           ('events', list(reversed(self.score['events']))),
                           ('events', self.score['events'] + [self.score['events'][-1]])]:
            with self.subTest(key=key):
                self.rewrite('score.json', dict(self.score, **{key: value}))
                with self.assertRaises(ValueError):
                    self.timeline()

    def test_nonfinite_playback_times_are_rejected(self):
        timeline = self.timeline()
        for time in (math.nan, math.inf, -math.inf):
            with self.assertRaises(ValueError):
                timeline.at(time)

    def test_runtime_loads_without_site_packages_and_parses_as_python39(self):
        for filename in ('music.py',):
            ast.parse((ROOT / filename).read_text(encoding='utf-8'), feature_version=(3, 9))
        result = subprocess.run(
            [sys.executable, '-B', '-S', '-c',
             'from music import MusicTimeline; import sys; '
             'assert MusicTimeline(sys.argv[1]).at(2).energy == 0.75; '
             'assert "numpy" not in sys.modules', str(self.root)],
            cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


class PackagedDataTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / 'score.json').is_file(), 'reviewed score is required')
        self.features = json.loads((ROOT / 'music_features.json').read_text(encoding='utf-8'))
        self.score = json.loads((ROOT / 'score.json').read_text(encoding='utf-8'))
        self.timeline = runtime().MusicTimeline(ROOT)

    def test_complete_features_cover_song_and_match_generator(self):
        self.assertEqual(self.timeline.duration, 211.906667)
        self.assertEqual(self.features['generator']['script_sha256'],
                         hashlib.sha256((ROOT / 'tools/analyze_music.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest())
        self.assertEqual(self.features['analysis']['sample_count'], 4672542)
        self.assertEqual(len(self.features['times']), 21240)
        self.assertAlmostEqual(self.features['times'][1], 220 / 22050, places=8)
        for name in CHANNELS:
            values = self.features[name]
            self.assertEqual(len(values), 21240)
            self.assertTrue(all(math.isfinite(v) and 0 <= v <= 1 for v in values))
            self.assertGreater(max(values) - min(values), 0.1)

    @unittest.skipUnless((ROOT/'media/song.mp3').is_file(), 'Original audio is local and optional')
    def test_original_audio_matches_profile_source(self):
        self.assertEqual(self.features['source']['sha256'],
                         hashlib.sha256((ROOT/'media/song.mp3').read_bytes()).hexdigest())

    def test_exact_lyric_events_and_all_transition_anchors(self):
        state = self.timeline.at(0)
        expected = {
            'execution': [147.66, 148.6, 149.52, 150.54, 151.52, 152.28,
                          153.16, 153.98, 155.2, 156.08, 157.04, 158.0],
            'count': [158.9, 159.321, 159.657, 160.244, 160.693, 161.124],
            'disconnect': [110.9, 112.22, 113.1, 114.18, 114.92, 115.78],
        }
        for kind, times in expected.items():
            actual = state.events(kind)
            self.assertEqual(len(actual), len(times))
            for event, time in zip(actual, times):
                self.assertAlmostEqual(event.time, time, places=9)
                self.assertNotEqual(self.timeline.at(event.time - 1e-7).event(kind), event)
                self.assertEqual(self.timeline.at(event.time).event(kind), event)
                frame = math.ceil(event.time * 30) / 30
                self.assertLessEqual(self.timeline.at(frame).event_age(kind), 1 / 30 + 1e-9)
        self.assertEqual([e.label for e in state.events('count')], ['EIN', 'DOS', 'TROIS', 'NE', 'FEM', 'LIU'])
        anchors = ('title_scatter', 'title_gather', 'title_lock', 'title_release',
                   'point_handoff', 'completion', 'isolation', 'fragments', 'repair_failed',
                   'execution_start', 'count_start', 'love_start', 'outro_start', 'final_execution')
        for label in anchors:
            self.assertTrue(math.isfinite(state.anchor(label)), label)
        title_times = [state.anchor(label) for label in anchors[:5]]
        self.assertTrue(all(a < b for a, b in zip(title_times, title_times[1:])))
        self.assertEqual(state.anchor('final_execution'), 205.811)
        self.assertEqual(state.anchor('completion'), 110.221)
        self.assertEqual(state.anchor('point_handoff'), 29.709)
        self.assertEqual(state.anchor('isolation'), 110.9)
        self.assertEqual(state.anchor('fragments'), 118.333)
        self.assertEqual(state.anchor('repair_failed'), 124.89)
        self.assertEqual(state.anchor('outro_start'), 192.5)
        self.assertGreater(len(state.events('accent')), 25)
        self.assertEqual(self.timeline.at(205.811).accent, 1)

    def test_five_boot_checks_use_reviewed_early_onsets_and_fire_exactly(self):
        self.assertEqual(self.score['calibration']['boot_review']['features_sha256'],
                         hashlib.sha256((ROOT/'music_features.json').read_bytes().replace(b'\r\n',b'\n')).hexdigest())
        events = self.timeline.at(0).events('boot')
        self.assertEqual([event.label for event in events],
                         ['POWER', 'MEMORY', 'IDENTITY', 'SIGNAL', 'CONSCIOUSNESS'])
        self.assertTrue(all(0 < event.time < 1.74 for event in events))
        self.assertTrue(all(a.time < b.time for a, b in zip(events, events[1:])))
        self.assertIsNone(self.timeline.at(0).event('boot'))
        onset = self.features['onset']
        stored = [event for event in self.score['events'] if event['kind'] == 'boot']
        for event, record in zip(events, stored):
            with self.subTest(label=event.label):
                source = record['source']
                self.assertEqual(source['type'], 'audio_onset_numeric_review')
                frame = source['feature_frame']
                self.assertAlmostEqual(event.time, self.features['times'][frame], places=6)
                self.assertGreater(onset[frame], 0.3)
                self.assertGreaterEqual(onset[frame], onset[frame - 1])
                self.assertGreater(onset[frame], onset[frame + 1])
                self.assertEqual(event.strength, onset[frame])
                self.assertNotEqual(self.timeline.at(event.time - 1e-7).event('boot'), event)
                self.assertEqual(self.timeline.at(event.time).event('boot'), event)
                self.assertEqual(self.timeline.at(event.time).event_age('boot'), 0)
        self.assertEqual(self.timeline.at(1.74).event('boot').label, 'CONSCIOUSNESS')

    def test_calibration_is_honest_and_preserves_lyric_provenance(self):
        calibration = self.score['calibration']
        self.assertFalse(calibration['human_listening'])
        self.assertEqual(calibration['status'], 'numeric_review_only')
        self.assertEqual(self.score['lyrics']['sha256'],
                         hashlib.sha256((ROOT / 'lyrics.json').read_bytes().replace(b'\r\n',b'\n')).hexdigest())
        lyrics = json.loads((ROOT / 'lyrics.json').read_text(encoding='utf-8'))
        for event in self.score['events']:
            source = event['source']
            if source['type'] == 'lyrics':
                self.assertEqual(event['time'], lyrics[source['index']]['time'])

    def test_reviewed_beats_follow_local_onsets_and_keep_boundary_phase(self):
        sections = self.score['beat_calibration']
        self.assertEqual(len(sections), len(self.score['sections']))
        self.assertGreater(len({s['period'] for s in sections}), 5)
        beats = self.score['beats']
        self.assertGreater(len(beats), 440)
        gaps = [b['time'] - a['time'] for a, b in zip(beats, beats[1:])]
        self.assertGreater(min(gaps), 0.35)
        self.assertLess(max(gaps), 0.57)
        for beat in beats:
            if beat['evidence'] == 'onset_peak':
                self.assertGreater(self.timeline.at(beat['time']).onset, 0.15)
        for section in self.score['sections'][1:]:
            time = section['time']
            left = self.timeline.at(time - 1e-6).beat_position
            right = self.timeline.at(time + 1e-6).beat_position
            self.assertGreater(right, left)
            self.assertLess(right - left, 1e-4)

    def test_real_timeline_supports_random_seeks_and_stdlib_only_loading(self):
        times = [0, 15.98, 29.709, 110.221, 110.9, 147.66, 158.9, 177.246, 205.811, 211.906667]
        forward = [self.timeline.at(t) for t in times]
        self.assertEqual(forward, list(reversed([self.timeline.at(t) for t in reversed(times)])))
        result = subprocess.run([sys.executable, '-B', '-S', '-c',
                                 'from music import MusicTimeline; '
                                 'assert MusicTimeline(".").at(205.811).accent == 1'],
                                cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / 'tools/analyze_music.py').is_file(), 'offline analyzer is required')
        import numpy as np
        from tools import analyze_music
        self.np = np
        self.analyzer = analyze_music

    def test_centered_frame_times_cover_short_and_nonintegral_hops(self):
        features = self.analyzer.analyze_samples(self.np.ones(2401), sample_rate=8000,
                                                fft_size=256, hop_size=80)
        self.assertEqual(features['duration'], 0.300125)
        self.assertEqual(features['times'][:3], [0, 0.01, 0.02])
        self.assertEqual(features['times'][-1], 0.300125)
        self.assertEqual(len(features['energy']), len(features['times']))
        short = self.analyzer.analyze_samples(self.np.ones(1), sample_rate=8000,
                                             fft_size=256, hop_size=80)
        self.assertEqual(short['times'], [0, 0.000125])

    def test_silence_is_finite_zero_and_invalid_audio_is_rejected(self):
        features = self.analyzer.analyze_samples(self.np.zeros(22050))
        for name in CHANNELS:
            self.assertTrue(all(v == 0 for v in features[name]))
        for samples in ([], [math.nan], [math.inf], [[0, 1], [1, 0]]):
            with self.assertRaises(ValueError):
                self.analyzer.analyze_samples(samples)

    def test_frequency_bands_do_not_amplify_leakage_into_other_bands(self):
        rate = 22050
        times = self.np.arange(rate) / rate
        for frequency, expected_band in [(100, 'low'), (1000, 'mid'), (5000, 'high')]:
            with self.subTest(frequency=frequency):
                features = self.analyzer.analyze_samples(0.4 * self.np.sin(2 * math.pi * frequency * times))
                i = min(range(len(features['times'])), key=lambda i: abs(features['times'][i] - 0.5))
                self.assertGreater(features[expected_band][i], 0.95)
                self.assertGreater(features['energy'][i], 0.95)
                for band in ('low', 'mid', 'high'):
                    if band != expected_band:
                        self.assertLess(features[band][i], 0.02)

    def test_impulse_timestamp_has_no_half_window_or_smoothing_delay(self):
        samples = self.np.zeros(22050)
        samples[11025] = 1
        features = self.analyzer.analyze_samples(samples)
        for name in ('energy', 'onset'):
            peak = max(range(len(features[name])), key=features[name].__getitem__)
            self.assertLess(abs(features['times'][peak] - 0.5), 0.02)
        self.assertEqual(features['onset'][0], 0)

    def test_features_are_reproducible_normalized_and_preserve_loudness(self):
        rate = 22050
        t = self.np.arange(rate * 2) / rate
        samples = self.np.sin(2 * math.pi * 440 * t) * self.np.where(t < 1, 0.1, 0.5)
        a = self.analyzer.analyze_samples(samples)
        self.assertEqual(a, self.analyzer.analyze_samples(samples))
        for name in CHANNELS:
            self.assertTrue(all(math.isfinite(v) and 0 <= v <= 1 for v in a[name]))
        quiet = min(range(len(a['times'])), key=lambda i: abs(a['times'][i] - 0.5))
        loud = min(range(len(a['times'])), key=lambda i: abs(a['times'][i] - 1.5))
        self.assertAlmostEqual(a['energy'][quiet] / a['energy'][loud], 0.2, delta=0.01)

    def test_candidate_detection_measures_each_section_instead_of_one_bpm(self):
        times = self.np.arange(0, 12, 0.01)
        onset = self.np.zeros(len(times))
        expected = list(self.np.arange(0.2, 6, 0.5)) + list(self.np.arange(6.1, 12, 0.4))
        for t in expected:
            onset[int(round(t * 100))] = 1
        candidates = self.analyzer.beat_candidates(
            {'times': times.tolist(), 'onset': onset.tolist()},
            [{'time': 0, 'label': 'slow'}, {'time': 6, 'label': 'fast'}], 12)
        self.assertEqual(len(candidates), 2)
        self.assertAlmostEqual(candidates[0]['period'], 0.5, delta=0.015)
        self.assertAlmostEqual(candidates[1]['period'], 0.4, delta=0.015)
        for section, count in zip(candidates, (12, 15)):
            self.assertEqual(len(section['beats']), count)
            self.assertTrue(all(b['evidence'] == 'onset_peak' for b in section['beats']))

    def test_cli_records_source_hash_and_never_overwrites_curated_score(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio = root / 'pulse.wav'
            samples = self.np.zeros(16000, dtype='<i2')
            samples[::4000] = 20000
            with wave.open(str(audio), 'wb') as stream:
                stream.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
                stream.writeframes(samples.tobytes())
            score = root / 'score.json'
            original = b'{"curated":true}\n'
            score.write_bytes(original)
            output = root / 'features.json'
            candidates = root / 'candidates.json'
            command = [sys.executable, '-B', str(ROOT / 'tools/analyze_music.py'),
                       '--audio', str(audio), '--output', str(output), '--candidates', str(candidates)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            features = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(features['source']['sha256'], hashlib.sha256(audio.read_bytes()).hexdigest())
            self.assertEqual(features['duration'], 2)
            self.assertEqual(score.read_bytes(), original)
            rejected = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(rejected.returncode, 0, 'existing candidates must not be overwritten')
            rejected = subprocess.run(command[:5] + ['--output', str(score)],
                                      capture_output=True, text=True, timeout=30)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertEqual(score.read_bytes(), original)

    def test_generator_provenance_is_independent_of_checkout_newlines(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            audio=root/'silent.wav'
            with wave.open(str(audio),'wb') as stream:
                stream.setparams((1,2,8000,0,'NONE','not compressed'))
                stream.writeframes(b'\0\0'*800)
            source=(ROOT/'tools/analyze_music.py').read_bytes().replace(b'\r\n',b'\n')
            digests=[]
            for name,data in (('lf',source),('crlf',source.replace(b'\n',b'\r\n'))):
                script=root/(name+'.py');script.write_bytes(data)
                output=root/(name+'.json')
                result=subprocess.run([sys.executable,'-B',str(script),'--audio',str(audio),'--output',str(output)],
                                      capture_output=True,encoding='utf-8',timeout=30)
                self.assertEqual(result.returncode,0,result.stderr)
                digests.append(json.loads(output.read_text(encoding='utf-8'))['generator']['script_sha256'])
            self.assertEqual(digests[0],digests[1])


if __name__ == '__main__':
    unittest.main(verbosity=2)
