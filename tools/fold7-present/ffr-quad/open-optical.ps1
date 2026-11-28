param([string]$Label, [switch]$Direct)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/fold7-helpers.ps1"
if (Test-Path "$PSScriptRoot/fold7-unattended-battery-paused") { throw 'Fold7 battery pause is active' }

function Find-Node([string]$selector) {
    for ($attempt = 0; $attempt -lt 6; $attempt++) {
        if (Test-Path "$PSScriptRoot/fold7-unattended-battery-paused") { throw 'Fold7 battery pause is active' }
        if ($attempt % 2 -eq 0) { Ensure-HidAllowed }
        $node = (Read-PhoneUi).SelectSingleNode($selector)
        if ($node) { return $node }
        Start-Sleep -Milliseconds 350
    }
    throw "Cannot find $selector with $(Phone-Top)"
}

adb -s $s shell am start --display 0 -n 'moe.shizuku.privileged.api/moe.shizuku.manager.MainActivity' | Out-Null
Start-Sleep -Milliseconds 1200
$entrySelector = '//node[@text="Pocket XR 外显预览" or @text="Pocket XR display preview"]'
$overflowSelector = '//node[@content-desc="更多选项" or @content-desc="More options"]'
Open-About
for ($attempt = 0; $attempt -lt 3; $attempt++) {
    Ensure-HidAllowed
    $ui = Read-PhoneUi
    $entry = $ui.SelectSingleNode($entrySelector)
    if ($entry) { break }
    $overflow = $ui.SelectSingleNode($overflowSelector)
    if ($overflow) { Tap-Node $overflow }
    Start-Sleep -Milliseconds 350
}
if (!$entry) { $entry = Find-Node $entrySelector }
if ($entry.bounds -match '\[(\d+),(\d+)\]\[(\d+),(\d+)\]' -and ([int]$Matches[4] - [int]$Matches[2]) -lt 24) {
    $x = [int](([int]$Matches[1] + [int]$Matches[3]) / 2)
    $from = [int]$Matches[2] - 59
    adb -s $s shell input -d 0 swipe $x $from $x ($from - 490) 500
    Start-Sleep -Milliseconds 250
    $entry = Find-Node $entrySelector
}
Tap-Node $entry
$selector = '//node[contains(@text,"VPN") and @checkable="true"]'
$head = Find-Node $selector
if ($head.checked -ne 'true') { Tap-Node $head }
$ui = Read-PhoneUi
$head = $ui.SelectSingleNode($selector)
if ($head.checked -ne 'true') { throw "VPN head tracking was not checked. $(Phone-Top)" }
$optical = if ($Direct) { Find-Node '//node[contains(@text,"直接渲染实验") or contains(@text,"with direct rendering")]' }
    else { $ui.SelectSingleNode('//node[contains(@text,"CV10 光学视场") or contains(@text,"at CV10 optical FOV")]') }
$time = Phone-Time
adb -s $s shell am unfreeze moe.shizuku.privileged.api | Out-Null
Tap-Node $optical

for ($i = 0; $i -lt 30; $i++) {
    if (Test-Path "$PSScriptRoot/fold7-unattended-battery-paused") { throw 'Fold7 battery pause is active' }
    $ready = adb -s $s logcat -d -T $time -s Cv10PocketXrPreview | Select-String 'First virtual display frame available|display preview failed' | Select-Object -Last 1
    if ($ready) { break }
    if ($i % 4 -eq 0) { Ensure-HidAllowed }
    Start-Sleep -Milliseconds 500
}
$records = adb -s $s logcat -d -T $time -s Cv10PocketXrPreview Cv10PocketHeadLink Cv10SpatialLauncher Cv10RefreshLease PocketXR-CV10 Cv10PocketXrDisplay
$records | Set-Content "$PSScriptRoot/$Label-open.log"
$records
if (!$ready -or $ready -notmatch 'First virtual display frame') { throw "Pocket XR $Label did not start" }
