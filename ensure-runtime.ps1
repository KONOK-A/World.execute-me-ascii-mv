# Windows PowerShell 5.1: prepare an app-private CPython without changing PATH.
$ErrorActionPreference = 'Stop'

function Get-MvArchitecture {
    $architecture = $env:PROCESSOR_ARCHITEW6432
    if (-not $architecture) { $architecture = $env:PROCESSOR_ARCHITECTURE }
    switch ($architecture) {
        'AMD64' { return 'x64' }
        'ARM64' { return 'arm64' }
        'x86' { return 'x86' }
        default { throw "Unsupported Windows architecture: $architecture" }
    }
}

function Test-MvPython {
    param([string]$Executable)
    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) { return $false }
    try {
        & $Executable -I -B -c 'import sys,ctypes,json,zipfile,unicodedata,msvcrt; raise SystemExit(sys.version_info < (3,9))' *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        # An incomplete download or incompatible executable is not a usable cache.
        return $false
    }
}

function Remove-MvOwnedDirectory {
    param([string]$Directory, [string]$CacheRoot)
    $root = [IO.Path]::GetFullPath($CacheRoot).TrimEnd('\') + '\'
    $target = [IO.Path]::GetFullPath($Directory)
    if (-not $target.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Refusing to remove a directory outside the runtime cache.'
    }
    if (Test-Path -LiteralPath $target) {
        $item = Get-Item -LiteralPath $target -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw 'Refusing to remove a linked runtime directory.'
        }
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}

function Save-MvRuntimeArchive {
    param([string]$Uri, [string]$OutFile)
    $client = New-Object Net.WebClient
    try {
        # WebClient uses Windows proxy settings by default; also honor the common
        # HTTPS_PROXY environment variable when started from a terminal.
        if ($env:HTTPS_PROXY) { $client.Proxy = New-Object Net.WebProxy($env:HTTPS_PROXY) }
        $download = $client.DownloadFileTaskAsync([Uri]$Uri, $OutFile)
        if (-not $download.Wait(120000)) {
            $client.CancelAsync()
            throw 'The download timed out after 120 seconds.'
        }
    } finally {
        $client.Dispose()
    }
}

function Install-MvPython {
    param([string]$CacheRoot, [string]$ManifestPath, [string]$Architecture)
    $CacheRoot = [IO.Path]::GetFullPath($CacheRoot)
    $runtime = Join-Path $CacheRoot 'runtime'
    $executable = Join-Path $runtime 'python.exe'
    if (Test-MvPython $executable) { return }

    $manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $package = $manifest.packages.$Architecture
    if (-not $package -or $package.url -notmatch '^https://www\.python\.org/ftp/python/' -or
        $package.sha256 -notmatch '^[a-fA-F0-9]{64}$') {
        throw "Invalid Python download manifest for $Architecture. Re-extract the release ZIP."
    }
    [IO.Directory]::CreateDirectory($CacheRoot) | Out-Null
    $lock = $null
    $stage = $null
    try {
        # Serialize concurrent first launches; recheck after the other installer finishes.
        $deadline = [DateTime]::UtcNow.AddSeconds(120)
        while ($null -eq $lock) {
            try {
                $lock = [IO.File]::Open((Join-Path $CacheRoot 'install.lock'),
                    [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
            } catch [IO.IOException] {
                if ([DateTime]::UtcNow -ge $deadline) { throw 'Another runtime setup is still running. Try again shortly.' }
                Start-Sleep -Milliseconds 250
            }
        }
        if (Test-MvPython $executable) { return }
        $stage = Join-Path $CacheRoot ('setup-' + [Guid]::NewGuid().ToString('N'))
        [IO.Directory]::CreateDirectory($stage) | Out-Null
        $archive = Join-Path $stage 'python.zip'
        $unpacked = Join-Path $stage 'runtime'
        Write-Host "Python 3.9+ was not found. Downloading official Python $($manifest.version) ($Architecture)..."
        Write-Host 'This is a one-time setup. No administrator access is needed.'
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        $ProgressPreference = 'SilentlyContinue'
        try {
            Save-MvRuntimeArchive -Uri $package.url -OutFile $archive
        } catch {
            throw "Python download failed: $($_.Exception.GetBaseException().Message) Check your connection and retry, or install Python 3.9+ from https://www.python.org/downloads/windows/."
        }
        # Use .NET directly: inherited PowerShell 7 module paths can hide the
        # Windows PowerShell Get-FileHash function during a first launch.
        $sha = [Security.Cryptography.SHA256]::Create()
        $stream = [IO.File]::OpenRead($archive)
        try {
            $digest = [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '')
        } finally {
            $stream.Dispose()
            $sha.Dispose()
        }
        if ($digest -ne $package.sha256) { throw 'Python download SHA-256 verification failed. Retry setup.' }
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [IO.Compression.ZipFile]::ExtractToDirectory($archive, $unpacked)
        if (-not (Test-MvPython (Join-Path $unpacked 'python.exe'))) {
            throw 'The downloaded Python cannot run. Install Python 3.9+ from https://www.python.org/downloads/windows/ and retry.'
        }
        Remove-MvOwnedDirectory -Directory $runtime -CacheRoot $CacheRoot
        [IO.Directory]::Move($unpacked, $runtime)
        Write-Host 'Python is ready. Future launches can run offline.'
    } finally {
        try {
            if ($stage) { Remove-MvOwnedDirectory -Directory $stage -CacheRoot $CacheRoot }
        } finally {
            if ($null -ne $lock) { $lock.Dispose() }
        }
    }
}

function Invoke-MvBootstrap {
    try {
        Add-Type -AssemblyName PresentationCore
    } catch {
        throw 'Windows .NET Framework media components are unavailable. Enable .NET Framework in Windows Features, then retry.'
    }
    if ($env:MV_HAVE_PYTHON -eq '1') { return }
    if (-not $env:MV_RUNTIME_ROOT -or -not $env:MV_RUNTIME_MANIFEST) {
        throw 'Runtime paths are missing. Start the player with its CMD launcher.'
    }
    Install-MvPython -CacheRoot $env:MV_RUNTIME_ROOT -ManifestPath $env:MV_RUNTIME_MANIFEST -Architecture (Get-MvArchitecture)
}

# Dot sourcing exposes the functions for focused integrity checks without setup.
if ($MyInvocation.InvocationName -ne '.') { Invoke-MvBootstrap }
