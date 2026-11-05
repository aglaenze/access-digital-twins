# The app of the digital twins WITHOUT the container, on a Windows computer where the twins are installed by hand
# (route B of TUTORIAL.md: conda environments "mcstas" and "nicos"). For teachers and developers: it runs the code of
# this folder as it is. Students use run_twin.ps1 (the container).
#
# First time: right-click > "Run with PowerShell". It puts the icon "ESS digital twins (local)" on the desktop and
# opens the app. Then: double-click the icon. Same app as in the container (catalogue, notebooks alone); "Open NICOS"
# opens the choice of the instrument and the NICOS window as windows of this computer. Closing the app window stops
# the server (NICOS, if open, stays until its window is closed).
# Settings: TWIN_PYTHON (the Python of the environment "mcstas"), TWIN_APP_PORT (default 8890).
$ErrorActionPreference = "Continue"
Add-Type -AssemblyName System.Windows.Forms
[System.Net.WebRequest]::DefaultWebProxy = $null      # no proxy for localhost (the detection of the proxy makes the first requests time out)
$AppName = "ESS digital twins (local)"
$Twin = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$Port = if ($env:TWIN_APP_PORT) { $env:TWIN_APP_PORT } else { "8890" }
$State = Join-Path $env:LOCALAPPDATA "ESS-twins-local"
New-Item -ItemType Directory -Force $State | Out-Null
$Py = $env:TWIN_PYTHON
if (-not $Py) {
    $Py = @("$env:LOCALAPPDATA\miniforge3\envs\mcstas\python.exe", "$env:USERPROFILE\miniforge3\envs\mcstas\python.exe",
            "$env:USERPROFILE\miniconda3\envs\mcstas\python.exe", "$env:USERPROFILE\anaconda3\envs\mcstas\python.exe") |
          Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $Py) {
    [System.Windows.Forms.MessageBox]::Show("No conda environment 'mcstas' found. Set TWIN_PYTHON, or use run_twin.ps1 (container).", $AppName) | Out-Null
    exit 1
}

# 1. The icon on the desktop (once)
$LnkPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "$AppName.lnk"
if (-not (Test-Path $LnkPath) -and -not $env:TWIN_APP_TEST) {
    $Lnk = (New-Object -ComObject WScript.Shell).CreateShortcut($LnkPath)
    $Lnk.TargetPath = (Get-Command powershell).Source
    $Lnk.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    $Lnk.WorkingDirectory = $Twin
    $Lnk.IconLocation = Join-Path $Twin "container\app_icon.ico"
    $Lnk.Description = "The ESS digital twins, from this folder (no container)"
    $Lnk.Save()
}

# 2. The server (Jupyter, with the settings of the app), unless it is already running
function Alive($t) {
    try { Invoke-WebRequest -UseBasicParsing "http://localhost:$Port/api/status?token=$t" -TimeoutSec 5 | Out-Null; return $true }
    catch { return $false }
}
$TokFile = Join-Path $State "token.txt"
$Token = if (Test-Path $TokFile) { Get-Content $TokFile } else { "" }
$Started = $false
if (-not ($Token -and (Alive $Token))) {
    $Token = -join ((48..57) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })
    Set-Content $TokFile $Token
    $env:JUPYTER_CONFIG_PATH = Join-Path $Twin "container\app_config"
    $env:JUPYTER_PATH = Join-Path $Twin "container\app_data"          # Voila template of the app (formulas)
    $env:TWIN_APP_LOCAL = "1"
    # (through cmd for the log file: Start-Process -RedirectStandardError would keep this script waiting)
    $Log = Join-Path $State "server.log"
    $Cmd = "`"`"$Py`" -m jupyter server --no-browser --ServerApp.ip=127.0.0.1 --port=$Port --IdentityProvider.token=$Token " +
           "`"--ServerApp.root_dir=$Twin`" --ServerApp.default_url=/voila/render/Catalogue.ipynb > `"$Log`" 2>&1`""
    Start-Process cmd.exe -WindowStyle Hidden -WorkingDirectory $Twin -ArgumentList "/s", "/c", $Cmd
    $Started = $true
    for ($i = 0; ($i -lt 60) -and -not (Alive $Token); $i++) { Start-Sleep -Seconds 1 }
    if (-not (Alive $Token)) {
        [System.Windows.Forms.MessageBox]::Show("The server did not start: see $State\server.log", $AppName) | Out-Null; exit 1
    }
}

# 3. The window of the app (Edge or Chrome in app mode); closing it stops the server
$Url = "http://localhost:$Port/?token=$Token"
if ($env:TWIN_APP_TEST) { Write-Output $Url; exit 0 }      # (test: the server only, no window)
$Browser = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
             "$env:ProgramFiles\Google\Chrome\Application\chrome.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($Browser) {
    Start-Process $Browser -Wait -ArgumentList "--app=$Url", "--user-data-dir=`"$State\window`"", "--no-first-run",
        "--no-default-browser-check", "--window-size=1400,900"
    if ($Started) {
        try { Invoke-WebRequest -UseBasicParsing -Method Post "http://localhost:$Port/api/shutdown?token=$Token" -TimeoutSec 10 | Out-Null } catch { }
    }
} else {
    Start-Process $Url
}
