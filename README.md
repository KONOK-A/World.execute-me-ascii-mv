# world.execute(me); —ascii

![world.execute(me);](docs/images/mv-cover.png)

Mili《world.execute(me);》的字符动画。支持 Windows 10/11 和 macOS，提供中英字幕、原曲同步播放和终端字符动画。Python 播放器仅使用标准库，无需 `pip install`。

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

播放包需要 **Python 3.9 或更新版本**。Windows 自动调用系统自带的 Windows PowerShell 5.1 和 .NET Framework 媒体组件，无需 Swift 或额外 Python 包；macOS 音频组件包含 Apple Silicon 和 Intel 架构。音乐、动画、字幕、频谱数据和播放组件均内嵌于 `world-execute-mv.pyz`，无需额外指定 MP3。两个系统的播放包不能混用。

在 Windows Terminal / PowerShell 中进入解压目录：

```powershell
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

内嵌音乐是随程序封装的资源，不是加密或 DRM。播放时会解包到当前用户的临时目录，正常退出后清理；不会读取旧电脑 Downloads 中的文件。运行过程无需联网。

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

安装 Python 3.9+，然后在项目目录运行（或双击 `run.cmd`）：

```powershell
.\run.cmd

# 音频放在其他目录时，可直接指定；支持中文和空格路径
python player.py --audio "D:\音乐\world.execute(me).mp3"

# 从指定时间直接播放
python player.py --audio "D:\音乐\world.execute(me).mp3" --start 158.7 --autoplay
```

如果没有 `python` 命令但已安装 Python Launcher，可用 `py -3` 替代。启动器会优先尝试 `py -3`。

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
- `world-execute-mv-windows.zip` 或 `world-execute-mv-macos.zip`：包含播放器、对应启动器、说明的分发包。
- `SHA256SUMS.txt`：下载校验值。

音频以系统播放器报告的位置驱动画面；暂停、跳转时字幕与动画跟随音频时间。Windows 使用 WPF `MediaPlayer`，macOS 使用 AVFoundation。macOS 构建会生成 universal 音频组件；两种包都会记录各资源 SHA-256 以检查完整性。

## 验证

```powershell
python -B -m unittest discover -s tests -v
```

测试使用临时静音 WAV 自动构建测试包，无需原曲或预先生成 `dist/`。覆盖快照、资源完整性、临时文件清理；Windows 额外验证真实音频接口和隐藏控制台中的按键、播放、退出与状态恢复。如果本机已有 FFmpeg，还会生成变码率 MP3 验证音频时钟；没有 FFmpeg 时仅跳过这一项，正常播放不依赖 FFmpeg。macOS 构建测试需要 Apple Command Line Tools。静音测试不验证原曲与画面的实际同步效果。

## 收录范围

本仓库为项目归档，包含当前播放器、字幕、频谱和构建工具。音乐仅内嵌于 Release 播放包。

原曲与歌词：Mili《world.execute(me);》。本项目是个人创作与备份，未对原曲、歌词或其他第三方素材授予额外使用许可。
