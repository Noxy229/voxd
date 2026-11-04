# Download the current Windows release, verify it, then open its terminal UI.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
    throw 'voxd currently provides Windows x64 packages only.'
}
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$Directory = Join-Path ([IO.Path]::GetTempPath()) ('voxd-release-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $Directory | Out-Null
$Base = 'https://github.com/Noxy229/voxd/releases/latest/download'
$Name = 'voxd-terminal-setup-x64.exe'
function Download([string]$Url, [string]$Destination) {
    for ($Attempt = 1; $Attempt -le 3; $Attempt++) {
        try { Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $Destination; return }
        catch { if ($Attempt -eq 3) { throw }; Start-Sleep -Seconds $Attempt }
    }
}
try {
    Write-Host 'voxd: Windows detected. Downloading terminal installer ...'
    $Exe = Join-Path $Directory $Name
    $Sums = Join-Path $Directory 'SHA256SUMS'
    Download "$Base/$Name" $Exe
    Download "$Base/SHA256SUMS" $Sums
    $Rows = @(Get-Content -LiteralPath $Sums | Where-Object { $_ -match '^([a-fA-F0-9]{64})\s+voxd-terminal-setup-x64\.exe$' })
    if ($Rows.Count -ne 1) { throw 'Missing or ambiguous Windows installer checksum.' }
    $Expected = ($Rows[0] -split '\s+')[0]
    $Actual = (Get-FileHash -LiteralPath $Exe -Algorithm SHA256).Hash
    if ($Expected -ine $Actual) { throw 'Installer checksum mismatch; nothing executed.' }
    & $Exe
    exit $LASTEXITCODE
} finally {
    Remove-Item -LiteralPath $Directory -Recurse -Force -ErrorAction SilentlyContinue
}
