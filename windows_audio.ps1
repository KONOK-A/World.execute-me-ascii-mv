# Windows PowerShell 5.1 / .NET Framework media clock. Launched by player.py.
# MediaPlayer uses its owning STA dispatcher; stdin is read on a C# worker.
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$player = $null
$script:playing = $false
$script:ended = $false
$script:mediaError = $null

function Send-State($state) {
    [Console]::Out.WriteLine(($state | ConvertTo-Json -Compress))
    [Console]::Out.Flush()
}

function Read-Number([string]$value) {
    $number = [double]::Parse($value, [Globalization.CultureInfo]::InvariantCulture)
    if ([double]::IsNaN($number) -or [double]::IsInfinity($number)) {
        throw 'Audio command requires a finite number.'
    }
    return $number
}

try {
    Add-Type -AssemblyName PresentationCore
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Concurrent;
using System.Threading;
public static class MvInput {
    private static readonly ConcurrentQueue<string> commands = new ConcurrentQueue<string>();
    public static void Start() {
        var reader = new Thread(() => {
            string line;
            while ((line = Console.ReadLine()) != null) commands.Enqueue(line);
            commands.Enqueue("quit");
        });
        reader.IsBackground = true;
        reader.Start();
    }
    public static string ReadCommand() {
        string line;
        return commands.TryDequeue(out line) ? line : null;
    }
}
'@
    $player = New-Object System.Windows.Media.MediaPlayer
    $player.add_MediaFailed({ param($sender, $event) $script:mediaError = $event.ErrorException.Message })
    $player.add_MediaEnded({
        param($sender, $event)
        $sender.Pause()
        $script:playing = $false
        $script:ended = $true
    })
    $player.Volume = 0.75
    $player.Open([Uri]::new($env:WORLD_EXECUTE_AUDIO))
    $dispatcher = [System.Windows.Threading.Dispatcher]::CurrentDispatcher
    $deadline = [DateTime]::UtcNow.AddSeconds(6)
    while (-not $player.NaturalDuration.HasTimeSpan) {
        $dispatcher.Invoke([System.Windows.Threading.DispatcherPriority]::Background, [Action]{})
        if ($script:mediaError) { throw $script:mediaError }
        if ([DateTime]::UtcNow -gt $deadline) { throw 'Audio open timed out.' }
        Start-Sleep -Milliseconds 10
    }
    $duration = $player.NaturalDuration.TimeSpan.TotalSeconds
    if ($duration -le 0 -or -not $player.HasAudio) { throw 'No playable audio found.' }
    [MvInput]::Start()
    $quitting = $false
    while (-not $quitting) {
        $dispatcher.Invoke([System.Windows.Threading.DispatcherPriority]::Background, [Action]{})
        if ($script:mediaError) { throw $script:mediaError }
        while ($null -ne ($line = [MvInput]::ReadCommand())) {
            $fields = $line.Trim() -split '\s+'
            switch ($fields[0]) {
                '' { }
                'play' { $player.Play(); $script:playing = $true; $script:ended = $false }
                'pause' { $player.Pause(); $script:playing = $false }
                'seek' {
                    if ($fields.Count -ne 2) { throw 'seek requires seconds.' }
                    $position = [Math]::Min([Math]::Max(0.0, (Read-Number $fields[1])), [Math]::Max(0.0, $duration - 0.01))
                    $player.Position = [TimeSpan]::FromSeconds($position)
                    $script:ended = $false
                }
                'volume' {
                    if ($fields.Count -ne 2) { throw 'volume requires a value.' }
                    $player.Volume = [Math]::Min(1.0, [Math]::Max(0.0, (Read-Number $fields[1])))
                }
                'quit' { $quitting = $true }
                default { throw ('Unknown audio command: ' + $fields[0]) }
            }
            if ($quitting) { break }
        }
        if ($quitting) { break }
        $position = if ($script:ended) { $duration } else { $player.Position.TotalSeconds }
        Send-State @{ time = $position; duration = $duration; playing = $script:playing }
        Start-Sleep -Milliseconds 15
    }
} catch {
    Send-State @{ error = $_.Exception.Message }
    exit 1
} finally {
    if ($null -ne $player) { $player.Close() }
}
