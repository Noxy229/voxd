# Windows 10/11 x64, per-user installation. No developer tools required.
[CmdletBinding()]
param([switch]$NonInteractive, [switch]$Compact, [switch]$English, [switch]$Autostart,
      [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\voxd'))
$ErrorActionPreference = 'Stop'
if (-not $env:LOCALAPPDATA) { throw 'Windows desktop session required.' }
Set-StrictMode -Version Latest
$LogPath = Join-Path ([IO.Path]::GetTempPath()) 'voxd-install.log'
Start-Transcript -Path $LogPath -Append | Out-Null
try {
function Run-Checked([string]$Exe, [string[]]$Arguments) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $Exe" }
}
if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
    throw 'This installer currently supports Windows x64 only.'
}
$Python = $null
$candidates = @((Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'))
$py = Get-Command py.exe -ErrorAction SilentlyContinue
if ($py) {
    try {
        $detected = & $py.Source -3.12 -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0) { $candidates += $detected }
    } catch { Write-Verbose 'Existing Python launcher has no usable Python 3.12 runtime.' }
}
foreach ($candidate in $candidates) { if (Test-Path -LiteralPath $candidate) { $Python = $candidate; break } }
if (-not $Python) {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($winget) {
        Run-Checked $winget.Source @('install','--id','Python.Python.3.12','--exact','--scope','user',
            '--silent','--accept-package-agreements','--accept-source-agreements','--disable-interactivity')
    } else {
        $PythonSetup = Join-Path ([IO.Path]::GetTempPath()) ('voxd-python-' + [Guid]::NewGuid().ToString('N') + '.exe')
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $PythonSetup
            $Signature = Get-AuthenticodeSignature -LiteralPath $PythonSetup
            if ($Signature.Status -ne 'Valid' -or $Signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
                throw 'Python installer signature validation failed.'
            }
            $Process = Start-Process -FilePath $PythonSetup -ArgumentList '/quiet InstallAllUsers=0 PrependPath=0 Include_test=0' -Wait -PassThru
            if ($Process.ExitCode -ne 0 -and $Process.ExitCode -ne 3010) { throw 'Python installation failed.' }
        } finally { Remove-Item -LiteralPath $PythonSetup -Force -ErrorAction SilentlyContinue }
    }
    $Python = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
    if (-not (Test-Path -LiteralPath $Python)) { throw 'Python not found after winget; restart PowerShell and retry.' }
}
if (-not $NonInteractive) {
    $BootstrapDir = Join-Path $env:LOCALAPPDATA 'voxd\installer-venv'
    Write-Host 'voxd: preparing terminal UI (Python + Textual) ...'
    Run-Checked $Python @('-m','venv',$BootstrapDir)
    $UiPython = Join-Path $BootstrapDir 'Scripts\python.exe'
    Run-Checked $UiPython @('-m','pip','install','--disable-pip-version-check','textual>=8.2,<9','tomli>=2')
    $UiArgs = @((Join-Path $PSScriptRoot 'installer\launch_tui.py'), '--install-dir', $InstallDir,
                '--profile', $(if ($Compact) { 'compact' } else { 'auto' }),
                '--language', $(if ($English) { 'en' } else { 'de' }))
    if ($Autostart) { $UiArgs += '--autostart' }
    # Stop transcript capture while the alternate-screen terminal application runs.
    Stop-Transcript | Out-Null
    & $UiPython @UiArgs
    $UiResult = $LASTEXITCODE
    Start-Transcript -Path $LogPath -Append | Out-Null
    exit $UiResult
}
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
function Stage([string]$Name) { Write-Output ('VOXD_EVENT {"stage":"' + $Name + '"}') }
Stage 'preflight'
Stage 'dependencies'
$Venv = Join-Path $InstallDir 'venv'
$PreviousPython = Join-Path $Venv 'Scripts\python.exe'
if (Test-Path -LiteralPath $PreviousPython) {
    & $PreviousPython -m voxd.cli quit
    Start-Sleep -Seconds 2
}
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Set-Content -LiteralPath (Join-Path $InstallDir 'voxd-install.marker') -Value 'voxd-per-user-v1'
Stage 'environment'
Run-Checked $Python @('-m','venv',$Venv)
$EnvPython = Join-Path $Venv 'Scripts\python.exe'
Run-Checked $EnvPython @('-m','pip','install','--upgrade','pip')
$Wheel = Get-ChildItem -LiteralPath $PSScriptRoot -Filter 'voxd-*.whl' | Select-Object -First 1
$Package = if ($Wheel) { $Wheel.FullName } else { $PSScriptRoot }
Stage 'application'
Run-Checked $EnvPython @('-m','pip','install','--upgrade','--force-reinstall',$Package)
$Profile = if ($Compact) { 'compact' } else { 'auto' }
$Language = if ($English) { 'en' } else { 'de' }
Stage 'models'
Run-Checked $EnvPython @('-m','voxd.bootstrap','--apply','--profile',$Profile,'--language',$Language)
Stage 'shortcuts'
$Shell = New-Object -ComObject WScript.Shell
$StartMenu = Join-Path ([Environment]::GetFolderPath('Programs')) 'voxd'
New-Item -ItemType Directory -Force -Path $StartMenu | Out-Null
$Shortcut = $Shell.CreateShortcut((Join-Path $StartMenu 'voxd.lnk'))
$Shortcut.TargetPath = Join-Path $Venv 'Scripts\pythonw.exe'
$Shortcut.Arguments = '-m voxd'
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.Save()
if ($Autostart) {
    Copy-Item -LiteralPath (Join-Path $StartMenu 'voxd.lnk') -Destination (Join-Path ([Environment]::GetFolderPath('Startup')) 'voxd.lnk')
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'uninstall.ps1') -Destination (Join-Path $InstallDir 'uninstall.ps1') -Force
$Uninstall = $Shell.CreateShortcut((Join-Path $StartMenu 'Uninstall voxd.lnk'))
$Uninstall.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$Uninstall.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $InstallDir 'uninstall.ps1') + '"'
$Uninstall.Save()
Write-Host 'voxd installed. Start it from the Start menu. Run voxd --setup for microphone settings.'

} catch {
    $_ | Out-String | Add-Content -LiteralPath $LogPath
    throw
} finally { Stop-Transcript | Out-Null }
