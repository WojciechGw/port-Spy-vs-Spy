# Run inside an Administrator PowerShell window. Keep that window open with -NoExit.
param(
    [string]$PythonPath = 'python',
    [string]$PicoAddress = '192.168.1.11',
    [string]$RecoverFrom = ''
)
$ErrorActionPreference = 'Stop'
$captureScript = Join-Path $PSScriptRoot 'capture_net_probe.py'
$captureCheckArgs = @($captureScript, '--host', $PicoAddress, '--check')
if ($RecoverFrom) {
    $captureCheckArgs += @('--recover-from', $RecoverFrom)
}
& $PythonPath @captureCheckArgs
if ($LASTEXITCODE -eq 0) {
    Write-Host 'PktMon check passed. Prepare Pico for the real test below.'
    & $PythonPath $captureScript --host $PicoAddress
} else {
    Write-Host 'PktMon check failed. No Pico test started; see saved commands.json.'
}
