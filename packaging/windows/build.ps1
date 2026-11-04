param([switch]$BootstrapOnly)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Push-Location $Root
try {
    py -3.12 -m venv .build-venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 x64 is required on the build machine.' }
    $Python = Join-Path $Root '.build-venv\Scripts\python.exe'
    & $Python -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'pip update failed' }
    & $Python -m pip install . 'pyinstaller>=6.11,<7' build
    if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed' }
    & $Python -m build --wheel
    if ($LASTEXITCODE -ne 0) { throw 'Wheel build failed' }
    if (-not $BootstrapOnly) {
    & $Python -m PyInstaller --noconfirm --clean --onedir --windowed --name voxd `
        --collect-submodules voxd --collect-all sherpa_onnx --collect-data spellchecker `
        --distpath dist/windows --workpath build/windows packaging/windows/entry.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
    }
    $ISCC = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($ISCC) { $Compiler = $ISCC.Source }
    else {
        $Compiler = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
        if (-not (Test-Path -LiteralPath $Compiler)) {
            $Compiler = Join-Path $env:ProgramFiles 'Inno Setup 7\ISCC.exe'
        }
    }
    if (-not (Test-Path -LiteralPath $Compiler)) { throw 'Install Inno Setup 6 or put ISCC.exe on PATH.' }
    & $Compiler packaging/windows/bootstrap.iss
    if ($LASTEXITCODE -ne 0) { throw 'Bootstrap installer compilation failed' }
    if (-not $BootstrapOnly) {
        & $Compiler packaging/windows/voxd.iss
        if ($LASTEXITCODE -ne 0) { throw 'Bundled installer compilation failed' }
    }
} finally { Pop-Location }
