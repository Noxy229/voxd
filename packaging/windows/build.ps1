$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Push-Location $Root
try {
    py -3.12 -m venv .build-venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 x64 required on the build machine.' }
    $Python = Join-Path $Root '.build-venv\Scripts\python.exe'
    & $Python -m pip install build
    if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed' }
    & $Python -m build --wheel
    if ($LASTEXITCODE -ne 0) { throw 'Wheel build failed' }
    if (Test-Path 'C:\msys64\mingw64\bin') { $env:PATH = 'C:\msys64\mingw64\bin;' + $env:PATH }
    & $Python tools/build_terminal_installer.py
    if ($LASTEXITCODE -ne 0) { throw 'Install MinGW-w64 gcc and windres or add them to PATH.' }
} finally { Pop-Location }
