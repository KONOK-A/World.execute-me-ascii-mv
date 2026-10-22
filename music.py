"""Immutable, seek-independent music state. Python 3.9+ standard library only.

The two JSON assets are required: missing/corrupt data is an error, never a
synthetic rhythm. Features use their stored timestamps; score beats carry a
continuous ordinal, including linear extrapolation outside the measured beats.
Only measured beats produce pulses. Half-time motion can use beat_position / 2.
"""
from bisect import bisect_right
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Optional, Tuple


_CHANNELS = ('energy', 'low', 'mid', 'high', 'onset')


@dataclass(frozen=True)
class MusicEvent:
    time: float
    kind: str
    label: str
    strength: float = 1.0


class _CueIndex:
    """Built once per timeline and shared by every sampled state."""

    def __init__(self, cues):
        groups = {}
        anchors = {}
        for cue in cues:
            groups.setdefault(cue.kind, []).append(cue)
            if cue.kind == 'transition':
                if cue.label in anchors:
                    raise ValueError('duplicate transition anchor: ' + cue.label)
                anchors[cue.label] = cue.time
        self.events = MappingProxyType({
            kind: tuple(sorted(events, key=lambda e: e.time))
            for kind, events in groups.items()
        })
        self.times = MappingProxyType({
            kind: tuple(e.time for e in events) for kind, events in self.events.items()
        })
        self.anchors = MappingProxyType(anchors)


@dataclass(frozen=True)
class MusicState:
    time: float = 0.0
    energy: float = 0.0
    low: float = 0.0
    mid: float = 0.0
    high: float = 0.0
    onset: float = 0.0
    beat: float = 0.0
    beat_phase: float = 0.0
    beat_position: float = 0.0
    accent: float = 0.0
    section: str = ''
    cues: Tuple[MusicEvent, ...] = ()
    _index: Optional[_CueIndex] = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        object.__setattr__(self, 'cues', tuple(self.cues))
        if self._index is None:
            object.__setattr__(self, '_index', _CueIndex(self.cues))

    def events(self, kind):
        """All events of this kind, including future ones, in time order."""
        return self._index.events.get(kind, ())

    def event(self, kind):
        """Latest event at or before time; equal-time events use file order."""
        events = self.events(kind)
        i = bisect_right(self._index.times.get(kind, ()), self.time) - 1
        return events[i] if i >= 0 else None

    def event_age(self, kind):
        event = self.event(kind)
        return self.time - event.time if event is not None else math.inf

    def anchor(self, label):
        """Named transition time, independent of playback time; missing is an error."""
        return self._index.anchors[label]


def _number(value, name, lower=None, upper=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(name + ' must be a number')
    if not math.isfinite(value):
        raise ValueError(name + ' must be finite')
    if lower is not None and value < lower or upper is not None and value > upper:
        raise ValueError(name + ' is out of range')
    return float(value)


def _ordered(times, name, strict=True):
    if any(b <= a if strict else b < a for a, b in zip(times, times[1:])):
        raise ValueError(name + ' must be ordered' + (' and unique' if strict else ''))


def _label(value, name):
    if not isinstance(value, str) or not value:
        raise ValueError(name + ' must be a nonempty string')
    return value


class MusicTimeline:
    """Load and validate packaged assets once; at(t) performs only bisects/math.

    Playback times clamp to [0, duration]. Nonfinite times are rejected. Runtime
    checks the two assets describe the same source, without requiring the MP3
    (snapshots and bundles may use an external audio path).
    """

    def __init__(self, root):
        root = Path(root)
        features = json.loads((root / 'music_features.json').read_text(encoding='utf-8'))
        score = json.loads((root / 'score.json').read_text(encoding='utf-8'))
        if features['version'] != 1 or score['version'] != 1:
            raise ValueError('unsupported music data version')
        self.duration = _number(features['duration'], 'duration', 0)
        if not self.duration or _number(score['duration'], 'score duration') != self.duration:
            raise ValueError('music duration must be positive and match score')
        source_hash = features['source']['sha256']
        if (not isinstance(source_hash, str) or len(source_hash) != 64
                or any(c not in '0123456789abcdef' for c in source_hash)
                or source_hash != score['source']['sha256']):
            raise ValueError('music source hash is invalid or does not match score')

        self._times = tuple(_number(t, 'feature time', 0, self.duration) for t in features['times'])
        if len(self._times) < 2 or self._times[0] != 0 or self._times[-1] != self.duration:
            raise ValueError('feature times must cover the complete duration')
        _ordered(self._times, 'feature times')
        self._channels = {}
        for name in _CHANNELS:
            values = tuple(_number(v, name, 0, 1) for v in features[name])
            if len(values) != len(self._times):
                raise ValueError(name + ' length does not match feature times')
            self._channels[name] = values

        self._sections = tuple(
            (_number(s['time'], 'section time', 0, self.duration), _label(s['label'], 'section label'))
            for s in score['sections'])
        self._section_times = tuple(s[0] for s in self._sections)
        if not self._sections or self._section_times[0] != 0:
            raise ValueError('sections must start at zero')
        _ordered(self._section_times, 'sections')
        self._beats = tuple(_number(b['time'], 'beat time', 0, self.duration) for b in score['beats'])
        self._strengths = tuple(_number(b['strength'], 'beat strength', 0, 1) for b in score['beats'])
        if len(self._beats) < 2:
            raise ValueError('score needs at least two measured beats')
        _ordered(self._beats, 'beats')

        self._cues = tuple(MusicEvent(
            _number(e['time'], 'event time', 0, self.duration),
            _label(e['kind'], 'event kind'), _label(e['label'], 'event label'),
            _number(e['strength'], 'event strength', 0, 1)) for e in score['events'])
        _ordered(tuple(e.time for e in self._cues), 'events', strict=False)
        self._index = _CueIndex(self._cues)
        self._hits = tuple(e for e in self._cues if e.kind in ('accent', 'execution', 'count', 'disconnect'))
        self._hit_times = tuple(e.time for e in self._hits)

    def at(self, t):
        t = min(self.duration, max(0.0, _number(t, 'playback time')))
        i = min(len(self._times) - 2, bisect_right(self._times, t) - 1)
        fraction = (t - self._times[i]) / (self._times[i + 1] - self._times[i])
        features = {name: values[i] + (values[i + 1] - values[i]) * fraction
                    for name, values in self._channels.items()}

        previous = bisect_right(self._beats, t) - 1
        interval = min(len(self._beats) - 2, max(0, previous))
        position = interval + (t - self._beats[interval]) / (self._beats[interval + 1] - self._beats[interval])
        beat = self._strengths[previous] * math.exp(-(t - self._beats[previous]) / 0.085) if previous >= 0 else 0.0
        # Max avoids a weak new hit cancelling an already decaying strong hit.
        lo = bisect_right(self._hit_times, t - 2)
        hi = bisect_right(self._hit_times, t)
        accent = max((e.strength * math.exp(-(t - e.time) / 0.16)
                      for e in self._hits[lo:hi]), default=0.0)
        section = self._sections[bisect_right(self._section_times, t) - 1][1]
        return MusicState(time=t, **features, beat=beat, beat_phase=position % 1,
                          beat_position=position, accent=accent, section=section,
                          cues=self._cues, _index=self._index)
