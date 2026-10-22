# Windows Support Implementation Plan

> **For agentic workers:** Execute task-by-task with `executing-plans`, test-driven development, and a final independent review.

**Goal:** 在 Windows 10/11 上运行现有终端 MV，支持播放、暂停、跳转、音量和单文件分发。

**Architecture:** 保留场景、字幕、频谱及音频时钟协议。将终端平台操作放入 `terminal.py`；Windows 音频进程通过系统自带 Windows PowerShell 5.1 调用 WPF `MediaPlayer`，继续输出 `{time, duration, playing}`。macOS 继续使用原 Swift 音频组件。

**Tech Stack:** Python 3.9+ 标准库、Windows Console API、Windows PowerShell 5.1 / .NET Framework WPF、macOS AVFoundation。

**Spec:** 本次用户要求“帮我把项目修改下，让其能在windows上运行”；此前研究确认 Unix 终端依赖、macOS 音频依赖及默认编码是启动阻塞。

## Global Constraints

- 不修改场景内容、字幕或频谱数据。
- 保留 macOS 运行路径；Windows 不要求 Swift 或额外 Python 包。
- 保留已有操作键和命令行参数。
- 不提交、不推送，不修改用户的 `.kilo/` 或忽略规则。
- 仓库不包含原曲；使用临时静音音频验证，真实音画同步取决于用户提供音频。

## Review Focus

- 中文和空格路径、CP936 默认编码：快照及音频均可正常打开。
- 暂停时 seek 不得意外开始播放，播放时 seek 必须继续播放。
- 初始化失败、正常退出、Ctrl+C：终端状态和音频子进程均须清理。
- Windows 特殊键必须完整消费，不能把方向键尾字节当作普通快捷键。
- 单文件解包校验、平台匹配和临时文件清理必须保留。

## Task 1: Terminal and snapshots

**Files:** modify `player.py`; create `terminal.py`, `tests/test_player.py`, `tests/test_windows_console.py`.

**Interfaces:** `Terminal` context manager, `read_keys(timeout) -> str` (normal characters / ANSI left-right sequences), `size() -> (width, height)`.

- [x] Add subprocess snapshot tests with UTF-8 output and legacy default encoding, expected lyric markers at existing four test timestamps, minimum-size message.
- [x] Run `python -B -m unittest discover -s tests -p test_player.py -v`; confirm Windows import failure.
- [x] Isolate platform imports, explicitly read UTF-8 resources, use `Terminal` for setup, input, dimensions, cleanup.
- [x] Verify snapshots and actual Windows console modes/key handling in an isolated hidden console.

## Task 2: Windows audio clock

**Files:** create `windows_audio.ps1`, `tests/test_windows_audio.py`; modify `player.py` audio subprocess selection and cleanup.

**Interfaces:** Windows helper accepts one audio path; stdin commands `play`, `pause`, `seek <seconds>`, `volume <0..1>`, `quit`; stdout UTF-8 JSON state in seconds, error JSON on failure.

- [x] Add real-device tests using a temporary silent WAV under a Unicode path: advancing clock, stable pause, seek in both states, volume, EOF/quit, invalid file.
- [x] Run the new tests and confirm the missing Windows backend fails them.
- [x] Implement the native Windows helper; all audio API calls run on one thread, input reader queues commands.
- [x] Run audio tests and a hidden-console player smoke test using the same silent audio.

## Task 3: Launching and packaging

**Files:** modify `tools/build_bundle.py`, `tools/bundle_main.py`, `tests/test_bundle.py`, `README.md`; create `run.cmd`, `运行单文件.cmd`.

**Interfaces:** `build_bundle.build(audio, output) -> Path` builds for the host platform; CLI `--audio` / `--output` supports explicit input and isolated test output. Package contains platform metadata and hashes.

- [x] Make packaging tests build a temporary real Windows bundle using silent audio, retaining resource equality, snapshot, corruption rejection, and cleanup assertions.
- [x] Run tests to observe failure before implementation.
- [x] Add Windows resources/platform guard, safe Windows extraction paths, launchers and documentation; retain macOS universal build.
- [x] Verify packaging from a Unicode path and running the bundle outside the repository.

## Task 4: Final verification and review

- [x] Run `python -B -m unittest discover -s tests -v`.
- [x] Exercise MP3 decoding with a temporary generated silent MP3 if the installed FFmpeg is available.
- [x] Check `git diff --check`, inspect scope and request an independent review.
- [x] Report exact validation scope and startup commands; distinguish silent-audio verification from original-song synchronization.

## Execution notes

- Implementation is authorized by the user's request; proceed in this chat without an additional plan approval step.
- Use the existing workspace and leave changes uncommitted. No isolation is needed for this single-writer task.
- Context7 failed with an invalid API key; use official Microsoft and Python documentation instead.
- Native MCI was rejected after a real VBR MP3 regression: a 4-second file reported 2.336 seconds and its playback position stopped advancing early. WPF MediaPlayer passed the same duration/tail-seek check. The helper is started directly, without modifying execution policy or introducing a grandchild audio process.
- Independent review found batch argument expansion broke paths containing parentheses. Reproduced with `world.execute(me).mp3` and fixed by moving argument expansion outside parenthesized command blocks.
- Follow-up review found MediaPlayer resumes implicitly when seeking after natural completion. A real-audio regression reproduced the advancing clock despite `playing=false`; the MediaEnded handler now pauses the underlying player, and the test checks the clock remains still after end-to-start seeking.

## Verification results

- Windows / Python 3.14.4: `python -B -m unittest discover -s tests -v` — 17 tests passed, no skips.
- Real hidden-console playback passed for source and bundled players using a generated VBR MP3; both Windows launchers accepted parentheses in audio arguments.
- Python files parsed with Python 3.9 grammar; PowerShell helper parsed successfully and ran under Windows PowerShell 5.1. Python 3.9 itself and macOS were not available for runtime validation.
- `git diff --check` passed.
- Follow-up with the supplied original MP3: container duration exactly matches `211.906667` seconds in the configuration. Default local audio and Windows distribution were built and hash-verified. Muted full playback completed normally: 5,086 frames, final native time `211.98365` seconds. Chapter seek/pause/resume and natural completion passed. An audio-envelope comparison against the saved spectrum peaked at zero lag; perceptual lyric synchronization was not evaluated by this muted test.

## API references

- [Windows console modes](https://learn.microsoft.com/en-us/windows/console/setconsolemode)
- [Python Windows console input](https://docs.python.org/3.9/library/msvcrt.html)
- [MediaPlayer](https://learn.microsoft.com/en-us/dotnet/api/system.windows.media.mediaplayer)
- [MediaPlayer.Position](https://learn.microsoft.com/en-us/dotnet/api/system.windows.media.mediaplayer.position)
