param(
  [switch]$Hard
)

$root = Split-Path -Parent $PSScriptRoot
$dataDir = Join-Path $root 'data'

if ($Hard) {
  if (Test-Path $dataDir) {
    Remove-Item -Recurse -Force $dataDir
  }
  New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
  foreach ($dir in @('docs','parsing','notebooks','logs')) {
    New-Item -ItemType Directory -Force -Path (Join-Path $dataDir $dir) | Out-Null
  }
  Write-Host 'Hard cleanup completed.'
  exit 0
}

foreach ($legacy in @('index','base','chunks')) {
  $target = Join-Path $dataDir $legacy
  if (Test-Path $target) {
    Remove-Item -Recurse -Force $target
    Write-Host "Removed $target"
  }
}

Write-Host 'Legacy cleanup completed. docs/parsing/notebooks/logs untouched.'
