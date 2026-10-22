# CRT MV music and choreography implementation

## Goal and constraints

Implement the user's accepted CRT optimization plan: amber terminal aesthetic, music-led accents, stronger composition, readable words/subtitles, and calm/loud contrast across the complete song. Primary display is Windows Terminal at 128x44; also support 64x24, 80x30, 120x30 and 180x55.

- Runtime remains Python 3.9+ standard library with the existing native audio backends.
- Keep original audio, lyrics, spectrum, recognizable organic scenes, hotkeys, snapshot/plain modes and macOS support.
- No automatic commit, push, or Release publication for this implementation. Work in the existing checkout; preserve `.kilo/` and all unrelated files.
- Use `.build/crt-enhancement/` for baselines, progress, previews and measurements. Do not change ignore rules or tool configuration.
- Automated timing checks and listening/visual review are distinct. Record any human acceptance still outstanding honestly.

## Shared interfaces

### Music data

`music.py`: immutable `MusicEvent(time, kind, label, strength)` and `MusicState` with `time`, normalized `energy`, `low`, `mid`, `high`, `onset`, `beat`, `beat_phase`, `beat_position`, `accent`, `section`, and `cues`.

`MusicState.events(kind)` returns all events of a kind. `event(kind)` returns the latest event at or before its time (or None). `event_age(kind)` returns elapsed time or infinity. `anchor(label)` returns a transition event time and raises KeyError for missing anchors. `MusicTimeline(root).at(t)` performs deterministic interpolated lookup.

`music_features.json` holds generated continuous features and source provenance. `score.json` holds reviewed section/beat/lyric/transition markers. Runtime never performs FFT or imports NumPy. The analysis tool may generate candidates but must not overwrite curated score data implicitly.

Event kinds: `execution` (12 cues in 147.66..158.9), `count` (EIN..LIU, six cues), `disconnect` (six departures beginning 110.9), `accent` (semantic vocal hits), `transition` (named visual anchors). Required transition labels: `title_scatter`, `title_gather`, `title_lock`, `title_release`, `point_handoff`, `completion`, `isolation`, `fragments`, `repair_failed`, `execution_start`, `count_start`, `love_start`, `outro_start`, `final_execution` (205.811).

### Terminal encoding

`render_output.encode_frame(current, previous=None, *, styles, force_full=False)` returns `FrameOutput(text, full, changed_cells, byte_count)`. Frames expose `w`, `h`, `cells` and the existing full `ansi()` method. The encoder preserves styles and complete wide-character cells, supports clearing old glyphs, and chooses the shorter byte representation for dense changes. First frame, resize and explicit reset use full output.

### Rendering and UI

`Film.render(..., hud_visible=None)` preserves positional arguments. The scene canvas area is fixed regardless of HUD visibility. Ready/paused/help show the HUD by default; playback controller keeps it visible for three seconds after starting/input. Snapshot defaults to the cinematic view. Four subtitle lines and one spectrum line remain reserved.

Scene dispatch consumes `MusicState` instead of a scalar pulse. Scene animation is a pure function of audio time, viewport and immutable data. Caption offset affects captions, not choreography.

## Tasks

- [x] Capture baseline source, keyframes, preview clips and CPU/terminal timing.
- [x] Add music feature generation, score, deterministic runtime lookup and meaningful tests.
- [x] Add HUD overlay behavior, clean subtitle layout and frame output/reset/report integration.
- [x] Correct geometry scale and implement title/point and ECG/network transitions.
- [x] Rework six disconnections, 12 executions in groups of four, six count words, learning loop and final 99% sequence.
- [x] Apply layered contrast and musical transients throughout remaining scenes; protect key words from glitches.
- [x] Package new runtime files, update usage/development documentation and retain existing tests.
- [x] Produce before/after previews and five-size/boundary/determinism checks.
- [x] Profile full playback with separate draw/encode/write costs; enable 30 FPS by default after the user's viewing acceptance.
- [x] Independent review, fix actionable findings, run full regression and report exact acceptance status.

## Visual score

| Range | Behavior |
| --- | --- |
| 0..29.709 | Boot stages, musically staged title scatter/gather/lock, release into point set |
| 29.709..110.9 | Geometry reaches 55–75% viewport height; subtle band-driven motion; recognizable produce/cat; half-time ECG synchronizes at completion |
| 110.9..125.708 | Six lyric-driven ruptures with recoil, gaps and restrained pauses; memory fragments attempt a failed heart reconstruction |
| 125.708..177.246 | Escalating error stages; execution hits grouped QUEUE/OVERWRITE/LOCK; count words occupy a clean center on their exact cues |
| 177.246..192.5 | Dim peripheral logs, focus information flow into LOVE, close the loop |
| 192.5..end | Sparse 99% wait, one final hit at 205.811, decaying phosphor and residual activity |

## Acceptance

All existing 17 tests plus music, rendering, wide-character and reset regressions. Named semantic events must fire within one 30 FPS frame. Sequential render, arbitrary seeks and paused snapshots at identical times must agree. Validate five viewport sizes and all scene boundaries. Preserve original CLI and native audio protocol. Render same-audio comparison clips for human viewing/listening; do not claim human acceptance without feedback.

## Results and decisions

- Release regression: **97 tests passed**. Python 3.9 grammar and a bundled snapshot with site-packages disabled also passed; Python 3.9 itself and macOS were not run.
- Final actual-song run: **6,324 frames**, final audio time **211.98365s**, at 30 FPS and a 128x44 content area in a hidden Windows console. Steady P95: draw 5.32ms, encode 1.44ms, write 1.55ms, total **7.61ms**. There were 17 frames above 33.3ms among 6,294 steady frames. Records are in `.build/crt-enhancement/final-playback-30.json`.
- The user subsequently confirmed the playback looked correct and explicitly requested **30 FPS** by default. The default is now 30; `--fps 24` remains available. The automated performance measurement above still refers to the hidden Windows console.
- The first execution revision was too repetitive according to user feedback. It was replaced by twelve distinct motions across QUEUE / OVERWRITE / LOCK. The user reviewed the updated audio comparison and confirmed that the variation/direction is appropriate. This accepts that segment's visual direction, not full-song perceptual beat calibration.
- Full-song beat/meter listening remains unverified; data records numeric/onset review honestly. Before/after title, isolation and execution clips are in `.build/crt-enhancement/previews/`.
- Independent review found EOF rewind flashing the boot scene, protection overwriting a LOVE status line, small-screen EXECUTION corruption, and stale feature provenance. All four were reproduced and fixed with regression checks. Text/provenance issues were treated as acceptance issues rather than optional polish; none remain deferred.
- EOF handling now distinguishes transient native completion resets from explicit seeks. The native audio backends/protocol are unchanged; R and chapter navigation have regressions to prevent the guard masking a real restart.
- The follow-up release request includes the full CRT changes, default 30 FPS, and a Windows prerequisite bootstrap that reuses Python 3.9+ or downloads a checksum-pinned official embedded runtime into the user's application cache. Publication is tracked by the Git commit and v1.1.0 Release.
- The official embedded Python 3.14.9 download, SHA-256 check and installation were exercised in an isolated user cache. With Python removed from PATH, both source and extracted-release CMD launchers reused the cache without downloading; packaged MP3 playback using this runtime reported 30 FPS. Local proxy stalls were isolated by using a direct connection only inside the verification PowerShell process; system proxy settings were unchanged.
- Bootstrap review found the interpreter probe was isolated while application startup still inherited PYTHONHOME. Both CMD launchers now use the same isolated mode; source and distribution regression checks cover an invalid inherited Python environment.
