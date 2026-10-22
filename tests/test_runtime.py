"""Windows prerequisite checks, download integrity and launcher argument handling."""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == 'win32', 'Windows bootstrap')
class RuntimeTests(unittest.TestCase):
    def powershell(self, script, **environment):
        script = ("$ErrorActionPreference='Stop'; "
                  ". ([scriptblock]::Create([IO.File]::ReadAllText($env:MV_TEST_SCRIPT))); " + script)
        encoded = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
        executable = Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
        return subprocess.run(
            [str(executable), '-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
            capture_output=True, encoding='utf-8', errors='replace', timeout=30,
            env=dict(os.environ, MV_TEST_SCRIPT=str(ROOT/'ensure-runtime.ps1'), **environment))

    def test_reuses_existing_python_without_downloading(self):
        with tempfile.TemporaryDirectory(prefix='mv 用户 (cache); ') as folder:
            result = subprocess.run(
                [str(ROOT/'run.cmd'), '--audio', r'D:\音乐\world.execute (me) ;.mp3',
                 '--snapshot', '67.3', '--plain'],
                input='', capture_output=True, encoding='utf-8', timeout=30,
                env=dict(os.environ, LOCALAPPDATA=folder))
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertIn('If I can make you happy', result.stdout)
            self.assertFalse((Path(folder)/'world-execute-mv/runtime').exists())

    def test_launcher_preserves_program_failure(self):
        result = subprocess.run([str(ROOT/'run.cmd'), '--invalid-option'], input='',
                                capture_output=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 2, result.stdout+result.stderr)
        self.assertIn('unrecognized arguments', result.stderr)

    def test_launcher_ignores_unrelated_python_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run(
                [str(ROOT/'run.cmd'), '--snapshot', '67.3', '--plain'], input='',
                capture_output=True, encoding='utf-8', timeout=30,
                env=dict(os.environ, PYTHONHOME=str(Path(folder)/'missing Python'),
                         PYTHONPATH=folder))
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertIn('If I can make you happy', result.stdout)

    def test_native_architecture_selection(self):
        result = self.powershell(
            "Get-MvArchitecture", PROCESSOR_ARCHITECTURE='x86', PROCESSOR_ARCHITEW6432='ARM64')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'arm64')

    def test_manifest_has_pinned_official_downloads(self):
        manifest = json.loads((ROOT/'python-runtime.json').read_text(encoding='utf-8'))
        self.assertEqual(set(manifest['packages']), {'x64', 'x86', 'arm64'})
        for package in manifest['packages'].values():
            self.assertTrue(package['url'].startswith('https://www.python.org/ftp/python/'))
            self.assertRegex(package['sha256'], r'^[0-9a-f]{64}$')

    def test_invalid_download_leaves_existing_files_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            archive = base/'download.zip'
            with zipfile.ZipFile(archive, 'w') as bundle:
                bundle.writestr('python.exe', b'not executable')
            cache = base/'cache'
            (cache/'runtime').mkdir(parents=True)
            sentinel = cache/'runtime/keep.txt'
            sentinel.write_text('existing data', encoding='utf-8')
            manifest = base/'manifest.json'
            manifest.write_text(json.dumps({'version': 'fixture', 'packages': {
                'x64': {'url': 'https://www.python.org/ftp/python/test.zip', 'sha256': '0'*64}}}), encoding='utf-8')
            result = self.powershell(
                "function Save-MvRuntimeArchive { param($Uri,$OutFile) "
                "[IO.File]::Copy($env:MV_TEST_ARCHIVE,$OutFile) }; "
                "Install-MvPython -CacheRoot $env:MV_TEST_CACHE -ManifestPath $env:MV_TEST_MANIFEST "
                "-Architecture x64",
                MV_TEST_ARCHIVE=str(archive), MV_TEST_CACHE=str(cache), MV_TEST_MANIFEST=str(manifest))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('SHA-256', result.stderr)
            self.assertEqual(sentinel.read_text(encoding='utf-8'), 'existing data')
            self.assertEqual([p.name for p in cache.iterdir() if p.name.startswith('setup-')], [])

    def test_download_error_is_actionable_and_cleans_staging(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder)/'cache'
            result = self.powershell(
                "function Save-MvRuntimeArchive { throw 'offline fixture' }; "
                "Install-MvPython -CacheRoot $env:MV_TEST_CACHE -ManifestPath $env:MV_TEST_MANIFEST "
                "-Architecture x64",
                MV_TEST_CACHE=str(cache), MV_TEST_MANIFEST=str(ROOT/'python-runtime.json'))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('offline fixture', result.stderr)
            self.assertFalse((cache/'runtime').exists())
            self.assertEqual([p.name for p in cache.iterdir() if p.name.startswith('setup-')], [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
