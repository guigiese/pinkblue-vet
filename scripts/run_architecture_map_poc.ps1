param(
    [int]$Port = 8765,
    [switch]$OpenBrowser
)

$target = Resolve-Path (Join-Path $PSScriptRoot '..\poc\architecture-map')
$python = Get-Command python -ErrorAction Stop
$url = "http://127.0.0.1:$Port"

Write-Host "Refreshing live architecture snapshot..."
& $python.Source (Join-Path $PSScriptRoot 'refresh_architecture_map_data.py')
if ($LASTEXITCODE -ne 0) {
    throw "Failed to refresh architecture map runtime data."
}

Write-Host "Rendering node icons..."
& $python.Source (Join-Path $PSScriptRoot 'build_architecture_map_icons.py')
if ($LASTEXITCODE -ne 0) {
    throw "Failed to build architecture map rendered icons."
}

Write-Host "Serving architecture map PoC from $target"
Write-Host "Open $url"

if ($OpenBrowser) {
    Start-Process $url
}

& $python.Source -m http.server $Port -d $target
