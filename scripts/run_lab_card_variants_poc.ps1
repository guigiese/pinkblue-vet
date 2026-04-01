param(
    [int]$Port = 8766,
    [switch]$OpenBrowser
)

$target = Resolve-Path (Join-Path $PSScriptRoot '..\poc\lab-card-variants')
$python = Get-Command python -ErrorAction Stop
$url = "http://127.0.0.1:$Port"

Write-Host "Serving Lab Monitor card variants from $target"
Write-Host "Open $url"

if ($OpenBrowser) {
    Start-Process $url
}

& $python.Source -m http.server $Port -d $target
