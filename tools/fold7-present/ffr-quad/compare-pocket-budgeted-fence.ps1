param([switch]$Reverse, [switch]$OnlyFirst, [string]$LabelSuffix = '2', [int]$QuadContextFfr = -1, [int]$BridgeLeadMs = -1, [switch]$BilibiliScene, [switch]$ScreenOff, [ValidateSet(0,1)][int]$WaitFence)
$Compute=$true
$Replay=$true
$Quad=$true
$StandardOffset=$true
$Calibrated=$true
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/fold7-helpers.ps1"
$gate = "$PSScriptRoot/fold7-unattended-battery-paused"
$saved = @{}
$testProps = @('debug.cv10.pocket_fence_trace', 'debug.cv10.pocket_fence_wait', 'debug.xrt.XRT_LOG', 'debug.cv10.pocket_zero_copy', 'debug.pocketxr.cv10_ffr', 'debug.xrt.CV10_PRESENT_TRACE', 'debug.cv10.pocket_atw', 'debug.xrt.XRT_COMPOSITOR_COMPUTE', 'debug.cv10.pocket_quad', 'debug.cv10.pocket_quad_atlas', 'debug.xrt.CV10_FUSE_INSET', 'debug.xrt.U_PACING_APP_MIN_MARGIN_MS')
if ($QuadContextFfr -ge 0) { $testProps += 'debug.pocketxr.cv10_quad_ffr' }
if ($BridgeLeadMs -ge 0) { $testProps += 'debug.pocketxr.cv10_bridge_lead_ms' }
foreach ($key in $testProps) {
    $saved[$key] = (adb -s $s shell getprop $key).Trim()
}
if ($Replay) {
    $saved['debug.pocketxr.cv10_pose_trace'] = (adb -s $s shell getprop debug.pocketxr.cv10_pose_trace).Trim()
    $saved['log.tag.Cv10PocketFramePoses'] = (adb -s $s shell getprop log.tag.Cv10PocketFramePoses).Trim()
}
if ($StandardOffset) {
    $saved['debug.pocketxr.cv10_pose_offset_ms'] = (adb -s $s shell getprop debug.pocketxr.cv10_pose_offset_ms).Trim()
}
if ($Calibrated) {
    $saved['debug.xrt.CV10_SCANOUT_FEEDBACK'] = (adb -s $s shell getprop debug.xrt.CV10_SCANOUT_FEEDBACK).Trim()
}

function Require-Battery {
    $level = adb -s $s shell dumpsys battery | Select-String '^\s*level:\s*(\d+)' | Select-Object -First 1
    if (!$level -or [int]$level.Matches[0].Groups[1].Value -lt 20 -or (Test-Path $gate)) {
        adb -s $s shell am force-stop $pocket | Out-Null
        adb -s $s shell am force-stop $p | Out-Null
        throw 'Fold7 battery pause is active or required'
    }
}

function Record-State([string]$outputName) {
    $mode = (adb -s $s shell cmd display get-active-mode 0) -join "`n"
    if ($mode -notmatch '60\.00 Hz') { throw "Unexpected phone mode $mode" }
    @($mode; adb -s $s shell dumpsys display | Select-String 'DisplayDeviceInfo.*type (INTERNAL|EXTERNAL)';
        adb -s $s shell dumpsys thermalservice | Select-String 'Thermal Status|mName=SKIN,' | Select-Object -First 3) |
        Set-Content "$PSScriptRoot/$outputName.txt"
}

$variants = if ($Reverse) { @('0.5','2.0') } else { @('2.0','0.5') }
if ($OnlyFirst) { $variants = @($variants[0]) }
try {
    for ($i=0; $i -lt $variants.Count; $i++) {
        Require-Battery
        $kind = $variants[$i]
        $computeValue = $Compute.ToString().ToLowerInvariant()
        $prefix = if ($Reverse) { "pocket-margin-recovered-ba$LabelSuffix" } else { "pocket-margin-recovered-ab$LabelSuffix" }
        if ($QuadContextFfr -ge 0) { $prefix = "pocket-budgeted-fence-$LabelSuffix" }
        if ($BridgeLeadMs -ge 0) { $prefix = "pocket-bridge-lead-$LabelSuffix-$BridgeLeadMs" }
        if ($StandardOffset) { $prefix += '-default' }
        if ($Calibrated) { $prefix += '-calibrated' }
        $quadValue = [int]$Quad
        $label = "$prefix-$computeValue-$i-$kind"
        adb -s $s shell "setprop debug.cv10.pocket_fence_trace 0; setprop debug.cv10.pocket_fence_wait $WaitFence; setprop debug.xrt.XRT_LOG info; setprop debug.xrt.CV10_PRESENT_TRACE true; setprop debug.xrt.XRT_COMPOSITOR_COMPUTE $computeValue; setprop debug.cv10.pocket_quad $quadValue; setprop debug.pocketxr.cv10_ffr 1; setprop debug.cv10.pocket_atw 1; setprop debug.cv10.pocket_zero_copy 1; setprop debug.cv10.pocket_quad_atlas 1; setprop debug.xrt.CV10_FUSE_INSET 1; setprop debug.xrt.U_PACING_APP_MIN_MARGIN_MS $kind"
        if ($QuadContextFfr -ge 0) { adb -s $s shell setprop debug.pocketxr.cv10_quad_ffr $QuadContextFfr }
        if ($BridgeLeadMs -ge 0) { adb -s $s shell setprop debug.pocketxr.cv10_bridge_lead_ms $BridgeLeadMs }
        if ($Replay) { adb -s $s shell 'setprop debug.pocketxr.cv10_pose_trace 1; setprop log.tag.Cv10PocketFramePoses DEBUG' }
        if ($StandardOffset) { adb -s $s shell setprop debug.pocketxr.cv10_pose_offset_ms 0 }
        if ($Calibrated) { adb -s $s shell setprop debug.xrt.CV10_SCANOUT_FEEDBACK true }
        adb -s $s shell cmd deviceidle tempwhitelist -d 120000 moe.shizuku.privileged.api | Out-Null
        $at = Phone-Time
        $tags = 'monado.comp_renderer_draw monado.calc_pose_data monado.do_update_timings_google_display_timing monado.comp_target_swapchain_present monado.renderer_wait_for_present MonadoCV10 Cv10SpatialLauncher Cv10PocketHeadLink Cv10PocketFramePoses Cv10PocketXrPreview Cv10PocketXrDisplay PocketXR-CV10 PocketXR-Tracking FlipSpaces/Space AndroidRuntime libc'
        $trace = Start-Process -FilePath (Get-Command adb).Source -ArgumentList "-s $s logcat -v threadtime -T `"$at`" -s $tags" -RedirectStandardOutput "$PSScriptRoot/$label-submit.txt" -RedirectStandardError "$PSScriptRoot/$label-logcat-error.txt" -WindowStyle Hidden -PassThru
        $leasePid = $null
        try {
            & "$PSScriptRoot/open-optical.ps1" -Label $label -Direct | Select-String 'First virtual display frame available|CV10_STREAM|four-view atlas'
            $activePath = 1
            if (!(Select-String -LiteralPath "$PSScriptRoot/$label-submit.txt" -Pattern "layer=[1-9]\d+ fused_inset=$activePath" -Quiet)) {
                throw "$label did not produce the requested fused_inset=$activePath path"
            }
            Start-Sleep -Seconds 4
            if ($BilibiliScene) {
                $appLayer = adb -s $s shell dumpsys SurfaceFlinger --list |
                    Select-String 'tv\.danmaku\.bili/tv\.danmaku\.bili\.[^ ]+\$_\d+#'
                $displayed = adb -s $s logcat -d -T $at -s ActivityTaskManager |
                    Select-String 'Displayed tv\.danmaku\.bili/'
                @($appLayer; $displayed) | Set-Content "$PSScriptRoot/$label-bilibili-ready.txt"
                if (!$appLayer -or !$displayed) { throw "Bilibili has not drawn its own window for $label" }
            }
            adb -s $s shell date +%s.%N | Set-Content "$PSScriptRoot/$label-controls-at.txt"
            adb -s $s shell am start -W --display 0 -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n "$pocket/com.hayeco.flipspaces.MainActivity" |
                Set-Content "$PSScriptRoot/$label-controls-launch.txt"
            if ((Phone-Top) -notmatch 'org\.cv10\.pocketxr') { throw "Pocket XR controls failed to take focus: $(Phone-Top)" }
            if ($QuadContextFfr -ge 0) {
                $active = Select-String -LiteralPath "$PSScriptRoot/$label-submit.txt" -Pattern 'CV10 quad GLES FFR active' -Quiet
                if ($active -ne ($QuadContextFfr -eq 1)) {
                    throw "Quad GLES FFR activation mismatch for $label"
                }
            }
            if ($BridgeLeadMs -ge 0) {
                $active = Select-String -LiteralPath "$PSScriptRoot/$label-submit.txt" -Pattern 'CV10 direct draw lead:' -Quiet
                if ($active -ne ($BridgeLeadMs -gt 0)) { throw "Bridge draw lead activation mismatch for $label" }
            }
            adb -s $s shell 'dumpsys battery | grep -E "^ *level:|^ *temperature:"' | Set-Content "$PSScriptRoot/$label-battery.txt"
            Record-State "$label-state-before"
            if ($ScreenOff) {
                $leasePid = (adb -s $s shell 'setsid sh /data/local/tmp/fold7-cv10-ready-panel.sh </dev/null >/data/local/tmp/fold7-cv10-ready-panel.log 2>&1 & echo $!').Trim()
                if ($leasePid -notmatch '^\d+$') { throw 'Panel script did not return a valid PID' }
                Start-Sleep -Milliseconds 850
                $leaseLog = (adb -s $s shell cat /data/local/tmp/fold7-cv10-ready-panel.log) -join ' '
                if ($leaseLog -notmatch 'active pid=') { throw "Could not blank phone: $leaseLog" }
            }
            adb -s $s shell dumpsys SurfaceFlinger --scheduler | Select-String 'pacesetterDisplayId=|forcedPacesetterDisplayId=' | Set-Content "$PSScriptRoot/$label-mode.txt"
            adb -s $s shell dumpsys display | Select-String 'mCommittedState=' | Add-Content "$PSScriptRoot/$label-mode.txt"
            $seconds = if ($Replay) { 27 } else { 12 }
            python "$PSScriptRoot/../head-motion/collect.py" $s $label --seconds $seconds --cv10-only
            if ($LASTEXITCODE) { throw "Could not collect actual presents for $label" }
            Save-Display $label | Out-Null
            if ($env:CV10_CAMERA_NAME) {
                try { Save-Lens $label | Out-Null } catch { Write-Warning $_ }
            }
            Record-State "$label-state-after"
            if ($leasePid -match '^\d+$') {
                adb -s $s shell kill -TERM $leasePid
                Start-Sleep -Milliseconds 1700
                adb -s $s shell cat /data/local/tmp/fold7-cv10-ready-panel.log | Add-Content "$PSScriptRoot/$label-mode.txt"
                $restoredPanel = ((adb -s $s shell cat /data/local/tmp/fold7-cv10-ready-panel.log) -join ' ')
                if ($restoredPanel -notmatch 'restored-panel') { throw "Phone panel did not restore: $restoredPanel" }
                $leasePid = $null
            }
            Require-Battery
            adb -s $s shell input -d 0 keyevent BACK
            Start-Sleep -Milliseconds 3800
            "$label $(Phone-Top)"
        } finally {
            if (!$trace.HasExited) { Stop-Process -Id $trace.Id }
            if ($leasePid -match '^\d+$') {
                adb -s $s shell kill -TERM $leasePid
                Start-Sleep -Milliseconds 1700
                adb -s $s shell cat /data/local/tmp/fold7-cv10-ready-panel.log | Add-Content "$PSScriptRoot/$label-mode.txt"
                $restoredPanel = ((adb -s $s shell cat /data/local/tmp/fold7-cv10-ready-panel.log) -join ' ')
                if ($restoredPanel -notmatch 'restored-panel') { throw "Phone panel did not restore: $restoredPanel" }
                $leasePid = $null
            }
        }
        adb -s $s logcat -b main -b system -b events -d -v threadtime -T $at -s FreecessController FreecessHandler wm_set_resumed_activity wm_on_stop_called |
            Select-String 'org\.cv10\.pocketxr|SpaceActivity' | Set-Content "$PSScriptRoot/$label-freecess.txt"
        $crash = adb -s $s logcat -b crash -d -T $at | Select-String 'launcher_preview|fdsan|Fatal signal'
        if ($crash) { throw "$label crash $crash" }
        adb -s $s shell am force-stop $pocket | Out-Null
        adb -s $s shell am force-stop $p | Out-Null
        adb -s $s shell input -d 0 keyevent HOME
        Start-Sleep -Seconds 2
    }
} finally {
    adb -s $s shell am force-stop $pocket | Out-Null
    adb -s $s shell am force-stop $p | Out-Null
    foreach ($key in $saved.Keys) {
        adb -s $s shell "setprop $key '$($saved[$key])'" | Out-Null
    }
    adb -s $s shell cmd deviceidle tempwhitelist -r moe.shizuku.privileged.api | Out-Null
}
