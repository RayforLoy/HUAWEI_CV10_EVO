param([Parameter(Mandatory)][string]$MonadoSource, [switch]$Restore)
$ErrorActionPreference = 'Stop'
$source = Join-Path (Resolve-Path -LiteralPath $MonadoSource) 'src/xrt/targets/openxr_android/src/main/java/org/freedesktop/monado/openxr_runtime/Cv10UsbReader.java'
$backup = "$source.cv10-replay-original"
if ($Restore) {
    if (!(Test-Path -LiteralPath $backup)) { throw 'Replay source backup is missing' }
    [IO.File]::WriteAllBytes($source, [IO.File]::ReadAllBytes($backup))
    Remove-Item -LiteralPath $backup
    return
}
if (Test-Path -LiteralPath $backup) { throw 'Restore the previous replay source before applying again' }
$original = [IO.File]::ReadAllBytes($source)
$encoding = [Text.UTF8Encoding]::new($false)
$inputText = $encoding.GetString($original)
$lineBreak = if ($inputText.Contains("`r`n")) { "`r`n" } else { "`n" }
$field = '    private long nextOpen, deadline, frames;'
$call = '            if (!BuildConfig.inProcess) Cv10PocketImu.publish(ns, imu);'
$simulation = @'
            // Local benchmark artifact only: identical rotations reach the runtime and Pocket XR.
            long replayNowNs = System.nanoTime();
            if (replayStartHostNs == 0) {
                replayStartHostNs = replayNowNs;
                Log.i(TAG, "CV10_BENCH start=" + replayStartHostNs);
            }
            double t = (replayNowNs - replayStartHostNs) * 1.0e-9;
            double omega = 2.0 * Math.PI / 3.0;
            float yawRate = t >= 9.0 && t < 29.0
                    ? (float) (Math.toRadians(17.0) * omega * Math.sin(omega * (t - 9.0))) : 0.0f;
            imu[0] = 0.0f;
            imu[1] = 9.80665f;
            imu[2] = 0.0f;
            imu[3] = 0.0f;
            imu[4] = yawRate;
            imu[5] = 0.0f;
'@
if (!$inputText.Contains($field) -or !$inputText.Contains($call)) { throw 'Unexpected USB reader source' }
$inputText = $inputText.Replace($field, "$field${lineBreak}    private long replayStartHostNs;")
$simulation = $simulation.TrimEnd() -replace '\r?\n', $lineBreak
$inputText = $inputText.Replace($call, "$simulation$lineBreak$call")
[IO.File]::WriteAllBytes($backup, $original)
[IO.File]::WriteAllText($source, $inputText, $encoding)
Write-Host 'Replay enabled in this disposable checkout. Build the Android preview, then run this script with -Restore.'
