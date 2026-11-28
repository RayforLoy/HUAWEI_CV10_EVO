$s = $env:CV10_ADB_SERIAL
if (!$s -or (adb -s $s get-state) -ne 'device') { throw 'Set CV10_ADB_SERIAL to an online Fold7 from adb devices -l' }
$p='org.cv10.monado.out_of_process.launcher_preview'
$hello='org.khronos.openxr.hello_xr.opengles'
$pocket='org.cv10.pocketxr'
$displayLine = adb -s $s shell dumpsys SurfaceFlinger --display-id | Select-String 'Display (\d+) .*HUAWEIAV03' | Select-Object -First 1
if (!$displayLine) { throw 'CV10 physical display is unavailable' }
$display = $displayLine.Matches[0].Groups[1].Value
$about="$p/org.freedesktop.monado.android_common.AboutActivity"
$evidence=$PSScriptRoot
function Read-PhoneUi {
    $remote = '/data/local/tmp/cv10-handoff-ui.xml'
    try {
        adb -s $s shell uiautomator dump $remote | Out-Null
        if ($LASTEXITCODE) { throw 'Android UI dump failed' }
        return [xml]((adb -s $s shell cat $remote) -join '')
    } finally {
        adb -s $s shell rm -f $remote | Out-Null
    }
}

function Tap-Node($node) {
    if ($null -eq $node -or $node.bounds -notmatch '\[(\d+),(\d+)\]\[(\d+),(\d+)\]') {
        throw 'Expected Android UI control is unavailable'
    }
    adb -s $s shell input -d 0 tap ([int](($Matches[1] -as [int]) / 2 + ($Matches[3] -as [int]) / 2)) ([int](($Matches[2] -as [int]) / 2 + ($Matches[4] -as [int]) / 2))
    if ($LASTEXITCODE) { throw 'Android tap failed' }
}

function Phone-Time { (adb -s $s shell date '+%m-%d_%H:%M:%S').Trim().Replace('_',' ') + '.000' }
function Phone-Top { (adb -s $s shell dumpsys activity activities | Select-String 'topResumedActivity=' | Select-Object -First 1).Line }
function Save-Display([string]$name) {
    $path=Join-Path $evidence "$name-external.png"
    python -c 'import pathlib,subprocess,sys; data=subprocess.check_output(["adb","-s",sys.argv[1],"exec-out","screencap","-p","-d",sys.argv[2]]); pathlib.Path(sys.argv[3]).write_bytes(data[data.index(bytes.fromhex("89504e470d0a1a0a")):])' $s $display $path
    if ($LASTEXITCODE) { throw 'Android external screenshot failed' }
    Get-Item -LiteralPath $path | Select-Object Name,Length
}
function Save-Lens([string]$name) {
    $path=Join-Path $evidence "$name-right.jpg"
    if (!$env:CV10_CAMERA_NAME) { return }
    $ffmpeg = (Get-Command ffmpeg -ErrorAction Stop).Source
    & $ffmpeg -hide_banner -loglevel error -y -f dshow -rtbufsize 32M -video_size 1280x720 -framerate 30 -vcodec mjpeg -i "video=$env:CV10_CAMERA_NAME" -an -ss 0.7 -frames:v 1 -q:v 3 -update 1 $path
    if ($LASTEXITCODE) { throw 'Right lens camera capture failed' }
    Get-Item -LiteralPath $path | Select-Object Name,Length
}
function Ensure-HidAllowed {
    if ((Phone-Top) -match 'UsbPermissionActivity') {
        $ui=Read-PhoneUi
        if (!$ui.SelectSingleNode('//node[contains(@text,"HUAWEI GLASS HID") and contains(@text,"Monado CV10")]')) {
            throw 'Unexpected USB permission dialog'
        }
        Tap-Node ($ui.SelectSingleNode('//node[@resource-id="android:id/button1" and (@text="确定" or @text="允许" or @text="OK" or @text="Allow")]'))
        'Allowed Monado CV10 access to the connected HUAWEI GLASS HID'
    }
}
function Tap-Text([string]$label) { Tap-Node ((Read-PhoneUi).SelectSingleNode("//node[@text='$label']")) }
function Open-About { adb -s $s shell am start -W --display 0 --activity-clear-top -n $about | Out-Null }
