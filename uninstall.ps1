$ErrorActionPreference = 'Stop'
$InstallDir = $PSScriptRoot
if (-not (Test-Path -LiteralPath (Join-Path $InstallDir 'voxd-install.marker'))) { throw 'Installation marker missing; remove manually.' }
$Python = Join-Path $InstallDir 'venv\Scripts\python.exe'
if (Test-Path $Python) { & $Python -m voxd.cli quit }
Start-Sleep -Seconds 2
Remove-Item -LiteralPath (Join-Path ([Environment]::GetFolderPath('Startup')) 'voxd.lnk') -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path ([Environment]::GetFolderPath('Programs')) 'voxd') -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $InstallDir 'venv') -Recurse -Force
Write-Host 'Application removed. Models, settings and the uninstall script were retained.'
