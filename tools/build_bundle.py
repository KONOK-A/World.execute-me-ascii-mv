"""Build a single-file player with audio for the current supported platform."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipapp
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ('player.py', 'scenes.py', 'terminal.py', 'music.py', 'render_output.py',
         'config.json', 'lyrics.json', 'spectrum.json', 'music_features.json', 'score.json')


def build(audio, output):
    audio = Path(audio).expanduser().resolve()
    output = Path(output).expanduser().resolve()
    if not audio.is_file():
        raise SystemExit('请先将本地音频放入 media/song.mp3，或用 --audio 指定音频文件。')
    if sys.platform not in ('win32', 'darwin'):
        raise SystemExit('请在 Windows 或 macOS 上构建对应平台的播放包。')
    windows = sys.platform == 'win32'
    if not windows:
        subprocess.run(['/bin/zsh', str(ROOT/'build-audio.sh'), '--universal'], check=True)
    output.mkdir(parents=True, exist_ok=True)
    audio_name = 'media/song'+(audio.suffix.lower() or '.mp3')
    files = FILES + (('windows_audio.ps1',) if windows else ('audio-clock',))
    with tempfile.TemporaryDirectory(prefix='bundle-') as folder:
        stage = Path(folder)
        manifest = {'format': 1, 'platform': 'Windows 10+' if windows else 'macOS 12+',
                    'sys_platform': sys.platform, 'files': {}}
        if not windows:
            manifest['architectures'] = ['arm64', 'x86_64']
        for name in (*files, audio_name):
            data = audio.read_bytes() if name == audio_name else (ROOT/name).read_bytes()
            if name == 'config.json':
                config = json.loads(data)
                if config['audio'] != audio_name:
                    config['audio'] = audio_name
                    data = (json.dumps(config, indent=2)+'\n').encode('utf-8')
            target = stage/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            manifest['files'][name] = hashlib.sha256(data).hexdigest()
        (stage/'__main__.py').write_bytes((ROOT/'tools/bundle_main.py').read_bytes())
        (stage/'bundle-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
        package = output/'world-execute-mv.pyz'
        zipapp.create_archive(stage, package, interpreter='/usr/bin/env python3', compressed=True)
        package.chmod(0o755)
    # A small convenient download with the single-file player and instructions.
    distribution = output/('world-execute-mv-windows.zip' if windows else 'world-execute-mv-macos.zip')
    launcher = '运行单文件.cmd' if windows else '运行单文件.command'
    distribution_files = [('world-execute-mv.pyz', package), ('README.md', ROOT/'README.md'),
                          (launcher, ROOT/launcher),
                          ('docs/images/mv-cover.png', ROOT/'docs/images/mv-cover.png')]
    if windows:
        distribution_files.extend((name, ROOT/name) for name in ('ensure-runtime.ps1', 'python-runtime.json'))
    with zipfile.ZipFile(distribution, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, path in distribution_files:
            archive.write(path, 'world-execute-mv/'+name)
    paths = [package, distribution]
    (output/'SHA256SUMS.txt').write_text(''.join(
        hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in paths), encoding='utf-8')
    return package


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', type=Path, default=ROOT/'media/song.mp3')
    parser.add_argument('--output', type=Path, default=ROOT/'dist')
    args = parser.parse_args()
    package = build(args.audio, args.output)
    suffix = 'windows' if sys.platform == 'win32' else 'macos'
    paths = [package, package.parent/f'world-execute-mv-{suffix}.zip']
    print(json.dumps({'artifacts': [str(p) for p in paths], 'embedded_audio': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
