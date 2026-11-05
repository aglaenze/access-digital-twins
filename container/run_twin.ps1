# The ESS digital twins as an app on your own computer (Windows).
#
# First time: right-click this file > "Run with PowerShell". It installs the icon "ESS digital twins" on your desktop,
# downloads the twins (several GB, once) and opens them. After that: double-click the icon. Closing the window of the
# app stops the twins. Your work is kept between sessions (volume "twin-data").
#
# Needs Podman Desktop (free, recommended) or Docker Desktop, both with WSL2. Teachers: TWIN_IMAGE, TWIN_PORT.
$ErrorActionPreference = "Continue"
Add-Type -AssemblyName System.Windows.Forms
$AppName = "ESS digital twins"
$Image = if ($env:TWIN_IMAGE) { $env:TWIN_IMAGE } else { "ghcr.io/aglaenze/access-digital-twins:latest" }
$Port = if ($env:TWIN_PORT) { $env:TWIN_PORT } else { "8888" }
$Container = "ess-twins"
$Home_ = Join-Path $env:LOCALAPPDATA "ESS-twins"
$Raw = "https://raw.githubusercontent.com/aglaenze/access-digital-twins/main/container"

function Say($text, $icon = "Information") {
    [System.Windows.Forms.MessageBox]::Show($text, $AppName, "OK", $icon) | Out-Null
}

# 1. Install (once): this script in %LOCALAPPDATA%\ESS-twins, an icon on the desktop that starts it without a console
New-Item -ItemType Directory -Force $Home_ | Out-Null
$Self = Join-Path $Home_ "run_twin.ps1"
if ($PSCommandPath -and ($PSCommandPath -ne $Self)) {
    Copy-Item $PSCommandPath $Self -Force
    $Ico = Join-Path $Home_ "app_icon.ico"
    try { Invoke-WebRequest -UseBasicParsing "$Raw/app_icon.ico" -OutFile $Ico -TimeoutSec 20 } catch { }
    $Lnk = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "$AppName.lnk"))
    $Lnk.TargetPath = (Get-Command powershell).Source
    $Lnk.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Self`""
    $Lnk.WorkingDirectory = $Home_
    if (Test-Path $Ico) { $Lnk.IconLocation = $Ico }
    $Lnk.Description = "The ESS instruments ODIN and LoKI, virtual"
    $Lnk.Save()
}

# 2. The container engine (Podman or Docker), running
$Engine = (Get-Command podman -ErrorAction SilentlyContinue).Source
if (-not $Engine) { $Engine = (Get-Command docker -ErrorAction SilentlyContinue).Source }
if (-not $Engine) {
    Say "Please install Podman Desktop first (free): https://podman-desktop.io`nThen double-click '$AppName' again." "Warning"
    Start-Process "https://podman-desktop.io"; exit 1
}
function Ready { & $Engine info *> $null; return ($LASTEXITCODE -eq 0) }
if (-not (Ready)) {
    if ($Engine -like "*podman*") { & $Engine machine start *> $null }
    else {
        $DD = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
        if (Test-Path $DD) { Start-Process $DD }
    }
    for ($i = 0; ($i -lt 60) -and -not (Ready); $i++) { Start-Sleep -Seconds 3 }
    if (-not (Ready)) { Say "Podman (or Docker) does not start. Open Podman Desktop, start it, then try again." "Warning"; exit 1 }
}

# 3. The twins: the image (downloaded the first time, updated when there is a new one), the container
$State = Join-Path $Home_ "token.txt"
$Running = (& $Engine ps -q --filter "name=^$Container$") -ne $null
if ($Running -and (Test-Path $State)) {
    $Token = Get-Content $State
} else {
    & $Engine rm -f $Container *> $null
    & $Engine image inspect $Image *> $null
    if ($LASTEXITCODE -ne 0) {
        # first time: a window that shows the download
        Say "First start: the twins are downloaded now (several GB, 10-30 minutes). A window shows the progress; the app opens by itself at the end."
        $p = Start-Process (Get-Command powershell).Source -PassThru -Wait -ArgumentList `
            "-NoProfile", "-Command", "`$host.UI.RawUI.WindowTitle='$AppName - downloading'; & '$Engine' pull $Image"
        & $Engine image inspect $Image *> $null
        if ($LASTEXITCODE -ne 0) { Say "The download did not finish (network?). Double-click '$AppName' to try again." "Warning"; exit 1 }
    } else {
        Start-Job -ScriptBlock { param($E, $I) & $E pull -q $I } -ArgumentList $Engine, $Image | Out-Null   # update, for next time
    }
    $Token = -join ((48..57) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })
    Set-Content $State $Token
    & $Engine run -d --rm --name $Container -p "127.0.0.1:${Port}:8888" -v twin-data:/data $Image `
        jupyter "--IdentityProvider.token=$Token" *> $null
}
$Url = "http://localhost:$Port/?token=$Token"
for ($i = 0; $i -lt 120; $i++) {
    try { Invoke-WebRequest -UseBasicParsing "http://localhost:$Port/api/status?token=$Token" -TimeoutSec 2 | Out-Null; break }
    catch { Start-Sleep -Seconds 2 }
}

# 4. The window of the app (Edge or Chrome in app mode: no address bar, no tabs); closing it stops the twins
$Browser = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
             "$env:ProgramFiles\Google\Chrome\Application\chrome.exe", "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe") |
           Where-Object { Test-Path $_ } | Select-Object -First 1
if ($Browser) {
    Start-Process $Browser -Wait -ArgumentList "--app=$Url", "--user-data-dir=`"$Home_\window`"", "--no-first-run",
        "--no-default-browser-check", "--window-size=1400,900"
    & $Engine stop -t 5 $Container *> $null
} else {
    Start-Process $Url      # (no Edge nor Chrome: a tab of the default browser; the twins stop when the computer does)
}
