param([Parameter(Mandatory)][string]$Serial,[switch]$AlreadyInstalled,[switch]$CompareOff)
$script:blanked=$false
$ErrorActionPreference='Stop'
$pkg='org.cv10.dpuprobe'
$line = adb -s $Serial shell dumpsys SurfaceFlinger --display-id | Select-String 'Display (\d+) .*HUAWEIAV03' | Select-Object -First 1
if (!$line) { throw 'CV10 display is unavailable' }
$display = $line.Matches[0].Groups[1].Value
$clock=adb -s $serial shell dumpsys SurfaceFlinger --scheduler | Select-String 'forcedPacesetterDisplayId='
if (!$clock -or $clock -notmatch 'nullopt') { throw 'SurfaceFlinger clock was already forced or not readable' }
function Require-On60($path) {
    $battery=adb -s $serial shell 'dumpsys battery | grep -E "^ *level:|^ *temperature:"'
    $level=$battery | Select-String '^\s*level:\s*(\d+)\s*$'
    if (!$level -or [int]$level.Matches[0].Groups[1].Value -lt 20) { throw 'Battery below 20% or unknown' }
    $mode=adb -s $serial shell cmd display get-active-mode 0
    $power=adb -s $serial shell dumpsys display | Select-String 'DisplayDeviceInfo.*type INTERNAL.*committedState ON'
    if (($mode -join ' ') -notmatch '60\.00 Hz' -or $power.Count -ne 1) { throw 'Expected one phone panel ON at 60 Hz' }
    $thermal=adb -s $serial shell 'dumpsys thermalservice | grep "Thermal Status"'
    $battery,$mode,$thermal | Out-File -Append -Encoding utf8 $path
}
$config=@"
buffers { size_kb: 32768 fill_policy: RING_BUFFER }
duration_ms: 5500
data_sources { config { name: "android.surfaceflinger.frame" } }
data_sources { config { name: "linux.ftrace" ftrace_config { atrace_categories: "gfx" atrace_categories: "hal" ftrace_events: "ftrace/print" } } }
"@
function Require-Off($path) {
    $displays=adb -s $serial shell dumpsys display | Select-String 'DisplayDeviceInfo.*type (INTERNAL|EXTERNAL)'
    $displays | ForEach-Object {$_.Line} | Out-File -Append -Encoding utf8 $path
    if ($displays -match 'type INTERNAL.*committedState ON' -or
            -not ($displays -match 'DisplayDeviceInfo.*HUAWEIAV03.*type EXTERNAL.*committedState ON')) {
        throw 'Positive control requires only CV10 left on'
    }
}
function Run-Probe([string]$label,[bool]$force,[int]$format,[bool]$screenOff=$false) {
    $root=Join-Path $PSScriptRoot $label
    Require-On60 "$root-modes.txt"
    if ($force) {
        adb -s $serial shell sfdo force-pacesetter $display | Out-Null
        if ($LASTEXITCODE) { throw 'Failed to set CV10 as pacesetter' }
    } else {
        adb -s $serial shell sfdo reset-forced-pacesetter | Out-Null
        if ($LASTEXITCODE) { throw 'Failed to restore system pacesetter' }
    }
    adb -s $serial shell am force-stop $pkg
    $stamp=(adb -s $serial shell date '+%m-%d_%H:%M:%S').Trim().Replace('_',' ') + '.000'
    adb -s $serial shell am start -W --display 0 -n "$pkg/.Probe" --ei format $format | Out-Null
    if ($LASTEXITCODE) { throw 'Starting isolated probe failed' }
    $found=$false
    for ($n=0;$n -lt 24;$n++) {
        $running=adb -s $serial logcat -d -T $stamp -s Cv10DpuProbe
        if ($running -match 'start format=') { $found=$true; break }
        Start-Sleep -Milliseconds 250
    }
    if (!$found) {
        $running | Set-Content "$root.log"
        throw "Probe did not start $label"
    }
    if ($screenOff) {
        $script:blanked=$true
        adb -s $serial shell cmd display power-off 0
        if ($LASTEXITCODE) { throw 'Could not turn phone panel off' }
        Start-Sleep -Milliseconds 500
        Require-Off "$root-modes.txt"
    }
    adb -s $serial shell dumpsys -t 3 android.hardware.graphics.composer3.IComposer/default > "$root-hwc.txt"
    $remote="/data/misc/perfetto-traces/$label.perfetto-trace"
    $config | adb -s $serial shell "perfetto --txt -c - -o $remote"
    if ($LASTEXITCODE) { throw 'Perfetto capture failed' }
    adb -s $serial pull $remote "$root.perfetto-trace"
    if ($LASTEXITCODE) { throw 'Perfetto pull failed' }
    adb -s $serial shell rm -f $remote
    $complete=$false
    for ($n=0;$n -lt 40;$n++) {
        $log=adb -s $serial logcat -d -T $stamp -s Cv10DpuProbe
        if ($log -match 'finished (valid=|video)') { $complete=$true; break }
        Start-Sleep -Milliseconds 250
    }
    $log | Set-Content "$root.log"
    $log | Select-String 'start format|finished (valid|video)'
    if ($screenOff) {
        Require-Off "$root-modes.txt"
        adb -s $serial shell cmd display power-reset 0 | Out-Null
        if ($LASTEXITCODE) { throw 'Could not restore phone screen state' }
        $script:blanked=$false
    }
    Require-On60 "$root-modes.txt"
    if (!$complete) { throw "Probe did not finish $label" }
}
Require-On60 "$PSScriptRoot/preflight-modes.txt"
try {
    if (!$AlreadyInstalled) {
        adb -s $serial install --no-incremental -r "$PSScriptRoot/build/probe.apk"
        if ($LASTEXITCODE) { throw 'APK installation failed' }
    }
    Run-Probe fold7-dpu-video-auto $false 0
    Run-Probe fold7-dpu-video-cv10 $true 0
    if ($CompareOff) { Run-Probe fold7-dpu-rgbx-off $true 2 $true }
} finally {
    if ($script:blanked) { adb -s $serial shell cmd display power-reset 0 | Out-Null }
    adb -s $serial shell sfdo reset-forced-pacesetter | Out-Null
    adb -s $serial shell am force-stop $pkg | Out-Null
    adb -s $serial shell input keyevent KEYCODE_HOME | Out-Null
    if (!$AlreadyInstalled) { adb -s $serial uninstall $pkg | Out-Null }
}
