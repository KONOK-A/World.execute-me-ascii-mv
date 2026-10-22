# world.execute(me); — ASCII MV for Windows

![world.execute(me);](docs/images/mv-cover.png)

在 Windows 终端里播放 Mili《world.execute(me);》的字符动画 MV。支持 Windows 10/11，提供琥珀色 CRT 画面、中英字幕和音乐同步，默认以 **30 FPS** 播放。

## 使用方法

1. 前往 [Releases](https://github.com/KONOK-A/world.execute-me-ascii-win/releases/latest)，下载 `world-execute-mv-windows.zip`。
2. 完整解压，双击文件夹中的 `运行单文件.cmd`。
3. 按空格开始播放。

播放包已内嵌音乐，无需另外准备 MP3。启动器会自动检查 Python，缺少时自动下载安装；首次下载需要联网，之后可离线播放。

推荐使用 **Windows Terminal 全屏**观看，窗口大小建议为 128 列 × 44 行或更大。

## 常用按键

| 按键 | 功能 |
| --- | --- |
| 空格 | 开始／暂停 |
| ← / → | 后退／前进 5 秒 |
| R | 从头播放 |
| 1–5 | 跳转章节 |
| H | 显示帮助 |
| Q | 退出 |

## 从源码运行

将自己的原曲保存为项目目录下的 `media/song.mp3`，然后双击 `run.cmd`，或在 PowerShell 中运行：

```powershell
.\run.cmd
```

原曲与歌词：Mili《world.execute(me);》。相关版权归原权利人所有。
