param([ValidateSet('AB','BA')][string]$Order='AB', [ValidatePattern('^[A-Za-z0-9_-]+$')][string]$RunId='pair1', [Parameter(Mandatory)][string]$ApkDir)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/fold7-helpers.ps1"
$gate = Join-Path $PSScriptRoot 'fold7-unattended-battery-paused'
$monadoOriginal = 'Monado-CV10-0.1.4-rc.2-direct-atw-arm64-v8a.apk'
$pocketOriginal = 'Pocket-XR-CV10-1.6.33-gpu-timer-arm64-v8a.apk'
$monadoFixture = 'Monado-CV10-0.1.4-rc.2-pocket-budgeted-fence-replay-arm64-v8a.apk'
$pocketFixture = 'Pocket-XR-CV10-1.6.33-context-1280-bili-portrait-arm64-v8a.apk'
function Test-Battery {
    $sample = adb -s $s shell dumpsys battery | Select-String '^\s*level:\s*(\d+)' | Select-Object -First 1
    return ($sample -and [int]$sample.Matches[0].Groups[1].Value -ge 20 -and !(Test-Path -LiteralPath $gate))
}
function Assert-Ready {
    if (!(Test-Battery)) { throw 'Fold7 battery gate active' }
    if (((adb -s $s shell cmd display get-active-mode 0) -join ' ') -notmatch '60\.00 Hz') { throw 'Fold7 is not at 60 Hz' }
    if ((Phone-Top) -notmatch 'com.sec.android.app.launcher') { throw "Phone is in use: $(Phone-Top)" }
}
function Set-TestPackage([string]$file) {
    adb -s $s install -r (Join-Path $ApkDir $file)
    if ($LASTEXITCODE) { throw "Could not install $file" }
}
function Assert-Package([string]$package, [string]$file) {
    $installed = (adb -s $s shell pm path $package | Select-Object -First 1).Trim().Substring(8)
    $actual = ((adb -s $s shell sha256sum $installed) -split '\s+')[0]
    $expected = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $ApkDir $file)).Hash.ToLowerInvariant()
    if ($actual -ne $expected) { throw "Installed $package differs from $file" }
}
Assert-Ready
$ApkDir = (Resolve-Path -LiteralPath $ApkDir).Path
Assert-Package $p $monadoOriginal
Assert-Package $pocket $pocketOriginal
$monadoTouched = $false
$pocketTouched = $false
try {
    adb -s $s push "$PSScriptRoot/test-pocket-ready-panel.sh" /data/local/tmp/fold7-cv10-ready-panel.sh
    if ($LASTEXITCODE) { throw 'Could not stage the expiring panel control' }
    $monadoTouched = $true
    Set-TestPackage $monadoFixture
    Assert-Package $p $monadoFixture
    $pocketTouched = $true
    Set-TestPackage $pocketFixture
    Assert-Package $pocket $pocketFixture
    $arms = if ($Order -eq "AB") { @("lit-0","lit-1","off-1","off-0") } else { @("off-0","off-1","lit-1","lit-0") }
    foreach ($arm in $arms) {
        Assert-Ready
        adb -s $s shell am force-stop tv.danmaku.bili | Out-Null
        & "$PSScriptRoot/compare-pocket-budgeted-fence.ps1" -OnlyFirst -QuadContextFfr 1 -LabelSuffix "$RunId-$arm" -BilibiliScene -ScreenOff:($arm -like "off-*") -WaitFence ([int]$arm[-1].ToString())
        $prefix = "$PSScriptRoot/pocket-budgeted-fence-$RunId-$arm-default-calibrated-true-0-2.0"
        $atlas = Select-String -LiteralPath "$prefix-open.log" -SimpleMatch 'context 1600, center 1280 per eye'
        if (!$atlas) { throw "Wrong Pocket XR atlas for $RunId-$arm" }
        if (!(Select-String -LiteralPath "$prefix-submit.txt" -SimpleMatch 'CV10 benchmark layout: tv.danmaku.bili, one centered window' -Quiet)) {
            throw "Bilibili benchmark layout did not load for $RunId-$arm"
        }
        $atlas.Line
    }
} finally {
    adb -s $s shell rm -f /data/local/tmp/fold7-cv10-ready-panel.sh /data/local/tmp/fold7-cv10-ready-panel.log | Out-Null
    adb -s $s shell am force-stop $pocket | Out-Null
    adb -s $s shell am force-stop $p | Out-Null
    adb -s $s shell am force-stop tv.danmaku.bili | Out-Null
    if (Test-Battery) {
        $restoreErrors = @()
        if ($pocketTouched) {
            try { Set-TestPackage $pocketOriginal; Assert-Package $pocket $pocketOriginal }
            catch { $restoreErrors += $_ }
        }
        if ($monadoTouched) {
            try { Set-TestPackage $monadoOriginal; Assert-Package $p $monadoOriginal }
            catch { $restoreErrors += $_ }
        }
        if ($restoreErrors) { throw "Restore the original APK pair: $restoreErrors" }
        adb -s $s shell input keyevent HOME
    } else { Write-Warning 'Battery gate active. Restore APKs after recovery.' }
}
