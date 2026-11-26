# Run after choosing the Huawei VR Glass and clicking Connect in NOLO HOME.
# Uses the active OpenVR installation and leaves the VR session running.
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$registryPath = Join-Path $env:LOCALAPPDATA 'openvr/openvrpaths.vrpath'
$paths = Get-Content -Raw -LiteralPath $registryPath | ConvertFrom-Json
$huaweiDriver = $paths.external_drivers | Where-Object {
    Test-Path -PathType Leaf -LiteralPath (Join-Path $_ 'bin/win64/driver_huaweicv1pro.dll')
} | Select-Object -First 1
if (!$huaweiDriver) { throw 'In NOLO HOME, select Huawei VR Glass and click Connect first.' }

$logDir = $paths.log[0]
$server = Get-Process -Name vrserver -ErrorAction SilentlyContinue | Select-Object -First 1
$since = (Get-Date).AddSeconds(-1)
if ($server) {
    $since = $server.StartTime.AddSeconds(-1)
} else {
    $startup = Join-Path $paths.runtime[0] 'bin/win64/vrstartup.exe'
    Start-Process -FilePath $startup -WorkingDirectory (Split-Path $startup) -WindowStyle Hidden
}

function Get-SessionLines([string]$File, [string]$Pattern, [datetime]$Started = $since) {
    $path = Join-Path $logDir $File
    if (!(Test-Path -LiteralPath $path)) { return }
    foreach ($match in (Select-String -LiteralPath $path -Pattern $Pattern)) {
        if ($match.Line -match '^\w{3} (\w{3} +\d{1,2} \d{4} \d\d:\d\d:\d\d\.\d{3}) ') {
            $stamp = [datetime]::ParseExact(($Matches[1] -replace ' +',' '), 'MMM d yyyy HH:mm:ss.fff', [cultureinfo]::InvariantCulture)
            if ($stamp -ge $Started) { $match.Line }
        }
    }
}

$deadline = (Get-Date).AddSeconds(45)
do {
    $compositor = Get-Process -Name vrcompositor -ErrorAction SilentlyContinue | Select-Object -First 1
    $graphicsSince = $since
    if ($compositor -and $compositor.StartTime.AddSeconds(-1) -gt $since) { $graphicsSince = $compositor.StartTime.AddSeconds(-1) }
    $result = Get-SessionLines 'vrcompositor.txt' 'Done initializing CGraphicsDevice resources|VRInitError_Compositor_InvalidOutputDesktop' $graphicsSince | Select-Object -Last 1
    if ($result -and ($compositor -or $result -match 'InvalidOutputDesktop')) { break }
    $result = $null
    Start-Sleep -Seconds 1
} while ((Get-Date) -lt $deadline)

Get-SessionLines 'vrserver.txt' 'Active HMD set to|Enable IMU:'
Get-SessionLines 'vrcompositor.txt' 'Headset is using direct mode|Headset display is on desktop|Current headset frequency|Invalid adapter output' $graphicsSince | Select-Object -Last 6
if (!$result) { throw "Timed out waiting for the compositor. See $logDir." }
if ($result -match 'InvalidOutputDesktop') { throw 'SteamVR 422: no usable desktop output. Check the CV10 display connection before restarting SteamVR.' }
Write-Output $result
$recent = (Get-Date).AddSeconds(-10)
if ($graphicsSince -gt $recent) { $recent = $graphicsSince }
$presentStatus = Get-SessionLines 'vrcompositor.txt' 'Current headset frequency|Invalid refresh: 0|WaitForPresent failed' $recent | Select-Object -Last 1
if ($presentStatus -match 'Invalid refresh: 0|WaitForPresent failed') {
    Write-Warning "The compositor recorded a presentation failure. $presentStatus"
}
$control = Get-CimInstance Win32_PnPEntity -Filter "Present = TRUE AND PNPDeviceID LIKE 'USB\\VID[_]12D1&PID[_]107E\\%'"
if (!$control) {
    Write-Warning 'CV10 USB motion control (12d1:107e) is absent. Leave SteamVR, PC and auxiliary power connected and reconnect only the glasses end.'
}
