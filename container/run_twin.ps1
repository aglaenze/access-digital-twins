# The digital twins on your own computer (Windows), as an app: downloads the container image the first time, starts
# it, and opens the catalogue of exercises in your web browser. Needs Podman Desktop (free, recommended) or Docker
# Desktop (paid for large organizations), both with WSL2.
#   powershell -ExecutionPolicy Bypass -File run_twin.ps1        # then work in the browser; Ctrl+C here to stop
# Your files stay in the volume "twin-data" (kept between sessions).
$Image = if ($env:TWIN_IMAGE) { $env:TWIN_IMAGE } else { "ghcr.io/aglaenze/access-digital-twins:latest" }
$Port = if ($env:TWIN_PORT) { $env:TWIN_PORT } else { "8888" }
$Engine = (Get-Command podman -ErrorAction SilentlyContinue).Source
if (-not $Engine) { $Engine = (Get-Command docker -ErrorAction SilentlyContinue).Source }
if (-not $Engine) { Write-Host "Install Podman Desktop (https://podman-desktop.io) or Docker Desktop first."; exit 1 }
$Token = -join ((48..57) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })
Write-Host "Getting the image (several GB the first time)..."
& $Engine pull $Image
$Url = "http://localhost:$Port/voila/render/Catalogue.ipynb?token=$Token"
Start-Job -ScriptBlock {
    param($Port, $Token, $Url)
    for ($i = 0; $i -lt 90; $i++) {
        try { Invoke-WebRequest -UseBasicParsing "http://localhost:$Port/api/status?token=$Token" -TimeoutSec 2 | Out-Null
              Start-Process $Url; break } catch { Start-Sleep -Seconds 2 }
    }
} -ArgumentList $Port, $Token, $Url | Out-Null
Write-Host "The catalogue opens in your browser when the twin is ready: $Url"
& $Engine run --rm -it -p "${Port}:8888" -v twin-data:/data $Image bash -c `
  "python container/fetch_fronts.py || true; exec jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --ServerApp.token=$Token --ServerApp.root_dir=/home/mambauser/twin"
