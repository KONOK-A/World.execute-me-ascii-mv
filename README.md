# world.execute(me); —ascii

![world.execute(me);](docs/images/mv-cover.png)

Mili《world.execute(me);》的字符动画。支持 Windows 10/11 和 macOS，提供中英字幕、原曲同步播放和终端字符动画。Python 播放器仅使用标准库，无需 `pip install`。

## 音乐编排与画面

- 使用预计算的整体能量、低／中／高频和瞬态信息驱动画面，拍点与强调事件保存在 `score.json`；暂停、跳转和快照都按音频时间定位。
- 保留琥珀色 CRT 风格，扩大几何主体，保护关键文字和双语字幕；12 次 EXECUTION 按“入队、覆盖、锁死”递进，每次使用不同动作。
- 播放提示在开始或操作后显示 3 秒，随后收起；暂停或按 H 显示信息。浮层切换不改变动画与字幕位置。
- 终端采用差量输出，减少重复写出，并正确处理中文双宽字符。

默认以 **30 FPS** 播放，已完成整曲测试和用户观看确认。本机隐藏 Windows 控制台、128×44 内容区的整曲测试中，稳态整帧 P95 为 **7.61ms**。如需降低帧率：

```powershell
python player.py --fps 24
```

## 创作提示词

整理了这支 MV 从初始构想到逐段调整的 **25 轮提示词**，以及一份方便复用的合并版。

- **[在线阅读创作过程](docs/prompts/creation-prompts.md)**：按轮次查看需求、场景位置与修改方向，文内目录可直接跳转。
- **[直接查看合并提示词](docs/prompts/creation-prompts.md#combined-prompt)**：适合整体阅读和复制使用。
- **[纯文本版](docs/prompts/creation-prompts.txt)**：方便保存到本地或在文本编辑器中打开。

## 单文件运行（推荐）

请使用对应系统的播放包，可下载已发布的 Release 或按下文自行构建：

| 系统 | 分发包 | 双击启动器 |
| --- | --- | --- |
| Windows 10/11 | `world-execute-mv-windows.zip` | `运行单文件.cmd` |
| macOS 12+ | `world-execute-mv-macos.zip` | `运行单文件.command` |

播放包使用 **Python 3.9 或更新版本**。Windows 解压完整 ZIP 后，双击 `运行单文件.cmd` 即可：启动器会检查 Python 和系统音频组件，优先复用现有 Python；未找到可用版本时，自动从 python.org 下载匹配 x64／ARM64／x86 的 Python 3.14.9 便携运行时，校验 SHA-256 后保存在 `%LOCALAPPDATA%\world-execute-mv\runtime`。首次缺少 Python 时需要联网，后续可离线使用；无需管理员权限，不修改系统 Python、PATH 或 PowerShell 执行策略。

Windows 音频使用系统自带的 Windows PowerShell 5.1 和 .NET Framework 媒体组件，无需 Swift 或额外 Python 包；如果系统组件被禁用，启动器会显示修复提示。macOS 需自行准备 Python，音频组件包含 Apple Silicon 和 Intel 架构。音乐、动画、字幕、频谱数据和播放组件均内嵌于 `world-execute-mv.pyz`，无需额外指定 MP3。两个系统的播放包不能混用。

在 Windows Terminal / PowerShell 中进入解压目录：

```powershell
.\运行单文件.cmd

# 已有 Python 时也可直接运行单文件
python world-execute-mv.pyz
```

macOS「终端」中运行：

```sh
python3 world-execute-mv.pyz
```

也可双击对应启动器。按空格开始。Windows 推荐使用 Windows Terminal；请在真实终端中运行，IDE 的输出面板不支持交互播放。推荐全屏，终端至少 64 列 × 24 行，128 列 × 44 行及以上效果更好。

```sh
# 从 2:38.7 开始直接播放
python3 world-execute-mv.pyz --start 158.7 --autoplay
```

内嵌音乐是随程序封装的资源，不是加密或 DRM。播放时会解包到当前用户的临时目录，正常退出后清理；不会读取旧电脑 Downloads 中的文件。依赖准备完成后，播放过程无需联网。

## 操作

| 按键 | 功能 |
| --- | --- |
| 空格 | 开始／暂停 |
| 左／右 | 后退／前进 5 秒 |
| R | 从头播放 |
| Q | 退出 |
| H | 显示全部帮助 |
| 1–5 | 跳转章节 |

## 从源码运行

仓库不保存音频文件。从源码运行或重新打包前，请将自己的音频放到本地 `media/song.mp3`。使用 Release 播放包无需此步骤。

### Windows

在项目目录运行（或双击 `run.cmd`），启动器同样会自动检测并准备 Python：

```powershell
.\run.cmd

# 音频放在其他目录时，可直接指定；支持中文和空格路径
python player.py --audio "D:\音乐\world.execute(me).mp3"

# 从指定时间直接播放
python player.py --audio "D:\音乐\world.execute(me).mp3" --start 158.7 --autoplay
```

直接使用 `python` 命令需要自行安装 Python 3.9+；如果只有 Python Launcher，可用 `py -3` 替代。两个 CMD 启动器依次检查 `py -3`、`python` 和用户缓存，跳过不可用或过旧的版本。保留启动器旁的 `ensure-runtime.ps1` 与 `python-runtime.json`；仅下载 `.pyz` 不包含自动准备前置。

还没有音频时，可以先查看动画快照，无需音频设备或交互终端：

```powershell
python player.py --snapshot 67.3 --plain --width 125 --height 45
```

Windows 支持 MP3 和 PCM WAV，使用系统媒体组件解码。字幕和场景基于仓库内固定时间轴，音频应使用匹配版本的原曲。

### macOS

首次构建音频组件需要 Apple Command Line Tools（含 Swift 编译器）：

```sh
xcode-select --install
```

然后执行：

```sh
./run.sh
```

启动脚本在缺少 `audio-clock` 时自动编译本机架构。双击 `播放MV.command` 可在 macOS 系统终端中运行源码版。

## 重新打包

在目标系统上构建该系统的播放包。Windows 不需要编译器；macOS 需要 Swift 编译器。

```powershell
python tools/build_bundle.py

# 也可显式指定本地音频及输出目录
python tools/build_bundle.py --audio "D:\音乐\world.execute(me).mp3" --output dist
```

macOS 将 `python` 换为 `python3`，音频路径换为本机路径即可。构建也接受 WAV；内嵌资源扩展名及配置会随输入文件调整。

构建输出在 `dist/`：

- `world-execute-mv.pyz`：内嵌音乐的单文件播放器。
- `world-execute-mv-windows.zip` 或 `world-execute-mv-macos.zip`：包含播放器、对应启动器、说明的分发包；Windows ZIP 还包含依赖检测和下载前置。
- `SHA256SUMS.txt`：下载校验值。

音频以系统播放器报告的位置驱动画面；暂停、跳转时字幕与动画跟随音频时间。Windows 使用 WPF `MediaPlayer`，macOS 使用 AVFoundation。macOS 构建会生成 universal 音频组件；两种包都会记录各资源 SHA-256 以检查完整性。

## 验证

完整开发测试使用 Python 3.14，并需要 FFmpeg、NumPy 和 Pillow。它们仅用于制作、预览和测试，普通播放不需要安装：

```powershell
python -m pip install -r tools/requirements-music.txt Pillow
python -B -m unittest discover -s tests -v
```

测试用临时静音 WAV 构建播放包，覆盖音乐事件边界、五种尺寸、跳转确定性、字幕布局、差量输出、双宽字符、完整性和文件清理。Windows 额外验证真实音频接口和隐藏控制台。原曲未放入 `media/song.mp3` 时，仅跳过原曲指纹／原曲片段检查；macOS 构建测试需要 Apple Command Line Tools。

记录播放性能（正常退出后写入报告）：

```powershell
New-Item -ItemType Directory -Path .build -Force | Out-Null
python player.py --fps 30 --report .build/playback-report.json
```

报告包含绘制、ANSI 编码、终端写出及整帧的 P50/P95/P99、输出字节数、全量／差量／未变化帧数和超预算帧数。长运行剔除开始的 30 帧后统计稳态数据。自动测试不代替实际听看验收。

## 制作音乐数据与对照预览

`music_features.json` 是连续特征，`score.json` 是按乐段校准的拍点、歌词强调和转场标记。两者随包分发，播放时直接查询，不进行 FFT。

```powershell
# 重新计算特征；不会修改人工维护的 score.json
python tools/analyze_music.py

# 候选拍点必须输出到新文件，再单独审核
python tools/analyze_music.py --candidates .build/beat-candidates.json

# 制作一段带原曲的预览（开发工具，需要 Windows 字体）
python tools/render_preview.py --source-dir . --start 147.66 --duration 29.586 --fps 30 --width 128 --height 44 --audio media/song.mp3 --output .build/execution-preview.mp4
```

采样参数、音频指纹和校准来源均记录在数据中。当前拍点校准依据分段音频分析与歌词时间；`human_listening` 标记不会因为自动测试通过而自动变为已听审。比较不同版本时，分别指定各自源码目录，使用相同音频起点、长度和帧率。

## 收录范围

本仓库为项目归档，包含当前播放器、字幕、频谱和构建工具。音乐仅内嵌于 Release 播放包。

原曲与歌词：Mili《world.execute(me);》。本项目是个人创作与备份，未对原曲、歌词或其他第三方素材授予额外使用许可。
