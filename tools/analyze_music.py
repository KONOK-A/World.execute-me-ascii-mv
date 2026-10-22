"""Offline music analysis (NumPy + FFmpeg only; neither is a runtime dependency).

    python tools/analyze_music.py
    python tools/analyze_music.py --candidates path/to/new-candidates.json

The second command emits UNREVIEWED section-wise beat candidates. It never
generates or updates score.json. Existing candidate files are not overwritten.
Feature generation can overwrite music_features.json; curate score separately.

Timing: decoded sample zero is playback zero (FFmpeg applies MP3 skip samples).
Periodic Hann windows are centered on the reported sample, with zero padding.
Positive spectral differences live halfway between adjacent frame centers and
are interpolated onto the feature time grid before symmetric smoothing. There
is no causal smoothing delay, arbitrary encoder-delay subtraction or FPS drift.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_RATE = 22050
FFT_SIZE = 1024
HOP_SIZE = 220
# Boundaries from the accepted visual score and existing scene/lyric boundaries.
SECTIONS = [
    {'time': time, 'label': label} for time, label in (
        (0.0, 'boot'), (16.0, 'title'), (29.709, 'devotion'),
        (59.223, 'satisfaction'), (74.045, 'organic'), (88.587, 'identity'),
        (103.489, 'completion'), (110.9, 'isolation'), (118.333, 'fragments'),
        (125.708, 'arguments'), (147.66, 'execution'), (158.9, 'count'),
        (162.632, 'execution_return'), (177.246, 'love'), (192.5, 'outro'))
]


def _smooth(values):
    # Centered three-tap FIR: no frame-history dependence or group delay.
    padded = np.pad(values, (1, 1), mode='edge')
    return (padded[:-2] + 2 * padded[1:-1] + padded[2:]) / 4


def _reference(values):
    # Exclude silence/roundoff: sparse clicks must not become wide clipped plateaus.
    active = values[values > float(np.max(values)) * 1e-6]
    return float(np.percentile(active, 99)) if len(active) else 0.0


def analyze_samples(samples, sample_rate=SAMPLE_RATE, fft_size=FFT_SIZE, hop_size=HOP_SIZE):
    """Analyze mono PCM; return JSON-ready features, including exact endpoints."""
    samples = np.asarray(samples, dtype=np.float64)
    if samples.ndim != 1 or not samples.size or not np.all(np.isfinite(samples)):
        raise ValueError('audio must be nonempty finite mono PCM')
    if (not isinstance(sample_rate, int) or sample_rate <= 0
            or not isinstance(fft_size, int) or fft_size < 16 or fft_size % 2
            or not isinstance(hop_size, int) or not 0 < hop_size <= fft_size // 2):
        raise ValueError('invalid sample rate, even FFT size, or hop size')
    centers = np.append(np.arange(0, len(samples), hop_size), len(samples))
    times = centers / sample_rate
    duration = round(len(samples) / sample_rate, 6)
    window = np.hanning(fft_size + 1)[:-1]
    window_power = float(np.sum(window ** 2))
    frequencies = np.fft.rfftfreq(fft_size, d=1 / sample_rate)
    masks = [(frequencies >= 20) & (frequencies < 250),
             (frequencies >= 250) & (frequencies < 2000), frequencies >= 2000]
    padded = np.pad(samples, (fft_size // 2, fft_size // 2))
    views = np.lib.stride_tricks.sliding_window_view(padded, fft_size)
    energy = np.empty(len(centers))
    bands = np.empty((3, len(centers)))
    flux = np.zeros(len(centers))
    previous = None
    # Bound the working FFT allocation rather than materializing the whole song.
    for start in range(0, len(centers), 512):
        stop = min(start + 512, len(centers))
        frames = views[centers[start:stop]] * window
        energy[start:stop] = np.sqrt(np.sum(frames ** 2, axis=1) / window_power)
        power = np.abs(np.fft.rfft(frames, axis=1)) ** 2 / (fft_size * window_power)
        power[:, 1:-1] *= 2  # Real-input FFT: double neither DC nor Nyquist.
        for band, mask in enumerate(masks):
            bands[band, start:stop] = np.sqrt(np.sum(power[:, mask], axis=1))
        magnitude = np.sqrt(power)
        first = magnitude[:1] if previous is None else previous[None, :]
        flux[start:stop] = np.maximum(np.diff(magnitude, axis=0, prepend=first), 0).sum(axis=1)
        previous = magnitude[-1]

    midpoints = (times[1:] + times[:-1]) / 2
    onset = np.interp(times, midpoints, flux[1:], left=0, right=0)
    raw = {'energy': _smooth(energy), 'low': _smooth(bands[0]),
           'mid': _smooth(bands[1]), 'high': _smooth(bands[2]), 'onset': _smooth(onset)}
    rms_reference = _reference(raw['energy'])
    flux_reference = _reference(raw['onset'])
    result = {'version': 1, 'duration': duration, 'times': np.round(times, 9).tolist()}
    result['times'][-1] = duration
    for name, values in raw.items():
        reference = flux_reference if name == 'onset' else rms_reference
        normalized = np.clip(values / reference, 0, 1) if reference else np.zeros_like(values)
        result[name] = np.round(normalized, 5).tolist()
    result['analysis'] = {
        'sample_rate': sample_rate, 'sample_count': len(samples),
        'fft_size': fft_size, 'hop_samples': hop_size,
        'frame_step_seconds': hop_size / sample_rate,
        'frame_time': 'center sample / sample_rate; final endpoint at decoded duration',
        'window': 'periodic Hann, centered, zero padded at both edges',
        'rms': 'sqrt(sum((PCM * window)^2) / sum(window^2))',
        'bands_hz': {'low': [20, 250], 'mid': [250, 2000], 'high': [2000, sample_rate / 2]},
        'band_power': 'one-sided rfft power / (fft_size * sum(window^2)); interior bins doubled',
        'transient': 'sum positive differences of sqrt(bin power); midpoint times resampled to centers',
        'smoothing': {'kernel': [0.25, 0.5, 0.25], 'alignment': 'centered', 'edges': 'repeat'},
        'normalization': 'clip to [0,1]; shared energy reference for RMS/bands, separate flux reference; p99 of values above 1e-6*peak (zero if silent)',
        'rms_reference': rms_reference, 'onset_reference': flux_reference,
        'precision_decimals': 5,
        'fft_reference': 'https://numpy.org/doc/stable/reference/generated/numpy.fft.rfft.html',
    }
    return result


def beat_candidates(features, sections, duration):
    """Estimate each section independently, then fit/snap its grid to onsets.

    This is a numeric aid, not human listening or a claim of metrical certainty.
    Unmatched slots are explicitly marked inferred_grid with reduced strength.
    """
    times = np.asarray(features['times'])
    onset = np.asarray(features['onset'])
    step = float(np.median(np.diff(times)))
    peaks = np.flatnonzero((onset[1:-1] >= onset[:-2]) & (onset[1:-1] > onset[2:])) + 1
    reports = []
    for index, section in enumerate(sections):
        start = section['time']
        end = sections[index + 1]['time'] if index + 1 < len(sections) else duration
        values = onset[(times >= start) & (times < end)]
        report = dict(section, end=end, period=None, autocorrelation=0.0, beats=[])
        reports.append(report)
        if len(values) < 3 or not values.max():
            continue
        selected = peaks[(times[peaks] >= start) & (times[peaks] < end)
                         & (onset[peaks] >= values.max() * 0.15)]
        if len(selected) < 3:
            continue
        centered = values - values.mean()
        correlation = np.correlate(centered, centered, mode='full')[len(values) - 1:]
        lags = np.arange(max(1, math.ceil(0.3 / step)), min(len(values) - 1, math.floor(0.8 / step)))
        if not len(lags) or correlation[0] <= 0:
            continue
        lag = int(lags[np.argmax(correlation[lags])])
        denominator = correlation[lag - 1] - 2 * correlation[lag] + correlation[lag + 1]
        refinement = 0.5 * (correlation[lag - 1] - correlation[lag + 1]) / denominator if denominator else 0
        period = (lag + float(np.clip(refinement, -0.5, 0.5))) * step
        peak_times, strengths = times[selected], onset[selected]
        # Compare phases over the whole section, not just the loudest first hit.
        phases = peak_times[peak_times < start + period * 4]
        if not len(phases):
            phases = peak_times[:1]
        def phase_score(phase):
            distances = np.abs((peak_times - phase + period / 2) % period - period / 2)
            return np.sum(strengths * np.exp(-0.5 * (distances / 0.025) ** 2))
        phase = float(max(phases, key=phase_score))
        matched = []
        for iteration in range(3):
            ordinals = np.arange(math.ceil((start - phase) / period), math.ceil((end - phase) / period))
            matched = []
            for ordinal in ordinals:
                prediction = phase + ordinal * period
                nearby = np.flatnonzero(np.abs(peak_times - prediction) <= 0.075)
                if len(nearby):
                    best = max(nearby, key=lambda i: strengths[i] * math.exp(-0.5 * ((peak_times[i] - prediction) / 0.025) ** 2))
                    matched.append((int(ordinal), float(peak_times[best]), float(strengths[best]), 'onset_peak'))
                else:
                    matched.append((int(ordinal), float(prediction), 0.2, 'inferred_grid'))
            evidence = [b for b in matched if b[3] == 'onset_peak']
            if iteration < 2 and len(evidence) >= 4:
                fit = np.polyfit([b[0] for b in evidence], [b[1] for b in evidence], 1,
                                 w=[b[2] for b in evidence])
                if 0.3 <= fit[0] <= 0.8:
                    period, phase = map(float, fit)
        # Do not extend pulse trains into the silent tail of a section.
        matched = [b for b in matched if peak_times[0] - period / 2 <= b[1] <= peak_times[-1] + period / 2]
        residuals = [abs(t - (phase + ordinal * period)) for ordinal, t, _, kind in matched if kind == 'onset_peak']
        report.update(period=round(period, 9), phase=round(phase, 9),
                      autocorrelation=round(float(correlation[lag] / correlation[0]), 6),
                      onset_matches=len(residuals),
                      residual_p95_seconds=round(float(np.percentile(residuals, 95)), 6) if residuals else None,
                      beats=[{'time': round(t, 6), 'strength': round(strength, 5), 'evidence': kind}
                             for _, t, strength, kind in matched])
    return reports


def _protect_score(path):
    if path.name.lower() == 'score.json':
        raise ValueError('refusing to overwrite curated score.json; use a separate candidate path')
    if path.exists():
        existing = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(existing, dict) and {'sections', 'events', 'beats'} <= existing.keys():
            raise ValueError('refusing to overwrite curated score data')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--audio', type=Path, default=ROOT / 'media/song.mp3')
    parser.add_argument('--output', type=Path, default=ROOT / 'music_features.json')
    parser.add_argument('--candidates', type=Path, help='new file only; never score.json')
    args = parser.parse_args(argv)
    _protect_score(args.output)
    if args.output.resolve() == args.audio.resolve():
        raise ValueError('output must not replace source audio')
    if args.candidates:
        _protect_score(args.candidates)
        if args.candidates.exists() or args.candidates.resolve() == args.output.resolve():
            raise ValueError('candidate output must be a separate new file')
    command = ['ffmpeg', '-v', 'error', '-i', str(args.audio), '-vn', '-ac', '1',
               '-ar', str(SAMPLE_RATE), '-f', 'f32le', 'pipe:1']
    decoded = subprocess.run(command, capture_output=True, check=True)
    samples = np.frombuffer(decoded.stdout, dtype='<f4')
    features = analyze_samples(samples)
    source = args.audio.resolve()
    features['source'] = {
        'path': source.relative_to(ROOT).as_posix() if source.is_relative_to(ROOT) else source.name,
        'sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'bytes': source.stat().st_size,
        'decoded_sample_count': len(samples), 'decoded_duration': len(samples) / SAMPLE_RATE,
        'time_origin': 'first decoded PCM sample; FFmpeg applies codec skip/discard metadata',
    }
    features['generator'] = {
        'script': 'tools/analyze_music.py', 'python': platform.python_version(), 'numpy': np.__version__,
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
        'script_hash_encoding': 'UTF-8/LF',
        'ffmpeg': subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, text=True).stdout.splitlines()[0],
        'decode_arguments': command[:4] + ['<source>'] + command[5:],
    }
    if args.candidates:
        sections = [s for s in SECTIONS if s['time'] < features['duration']]
        candidates = {'source': features['source'], 'review_status': 'unreviewed_numeric_candidates',
                      'human_listening': False,
                      'sections': beat_candidates(features, sections, features['duration'])}
        with args.candidates.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(candidates, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.write('\n')
    args.output.write_text(json.dumps(features, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print('{} frames, {:.6f}s, {} bytes -> {}'.format(
        len(features['times']), features['duration'], args.output.stat().st_size, args.output))


if __name__ == '__main__':
    main()
