param([Parameter(Mandatory=$true)][string]$Archive,
      [Parameter(Mandatory=$true)][string]$Target)
$ErrorActionPreference = 'Stop'
try {
    Expand-Archive -LiteralPath $Archive -DestinationPath $Target
    & (Join-Path $Target 'install.ps1')
    exit $LASTEXITCODE
} finally {
    if (Test-Path -LiteralPath $Target) { Remove-Item -LiteralPath $Target -Recurse -Force }
}
