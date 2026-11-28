# Fold7 presentation toolbox

Use PowerShell 7, Python 3.11+, Android platform tools and the paired Fold7. Use `python -m pip install perfetto` for the trace analyzers. Lens capture is optional on a Windows machine with FFmpeg and a DirectShow camera. Set `CV10_CAMERA_NAME` to its device display name. Keep output and extracted packages in local scratch.

## Read-only cadence

After the XR app presents, select the Fold7 from `adb devices -l` and run from the repository root.

```powershell
$env:CV10_ADB_SERIAL = 'copy-the-current-Fold7-serial'
$serial = $env:CV10_ADB_SERIAL
adb -s $serial shell dumpsys SurfaceFlinger --display-id
adb -s $serial shell dumpsys SurfaceFlinger --scheduler
adb -s $serial shell cmd display get-active-mode 0
adb -s $serial shell dumpsys display | Select-String 'mCommittedState='
adb -s $serial shell dumpsys thermalservice | Select-String 'Thermal Status|mName=SKIN'
python tools/fold7-present/head-motion/collect.py $serial hello-lit --cv10-only --seconds 20 --output-dir ./cv10-local
```

The raw layer dump holds the three reported nanosecond timestamps. The pipeline analysis in this handoff matches the third column exactly to Vulkan actual feedback on the measured Fold7 build. The collector also prints the rolling second-column cadence, which is useful as a quick check. Compare deduplicated timestamps, the start/end of the sampling window, matched Vulkan timestamps and the physical display mode when moving to another build. Save image or lens proof separately.

## Ordinary Pocket XR

Extract the APK archive and check its `SHA256SUMS`. The `company-freeze` Monado APK uses real IMU and the preview package ID. Use the ordinary `quad-ffr` Pocket XR CV10 build to test a normal workspace. The Broker, Android USB access and Shizuku setup are in the Monado and Pocket XR READMEs. Check the signing certificates before attempting an in-place upgrade and preserve the existing app data and installation.

Enable the optional four-view and late-projection settings before reopening the direct preview. Record whether the glasses get fresh frames at the negotiated atlas size.

```powershell
adb -s $serial shell 'setprop debug.cv10.pocket_zero_copy 1; setprop debug.cv10.pocket_quad 1; setprop debug.cv10.pocket_quad_atlas 1; setprop debug.xrt.XRT_COMPOSITOR_COMPUTE true'
adb -s $serial shell 'setprop debug.xrt.CV10_FUSE_INSET 1; setprop debug.pocketxr.cv10_quad_ffr 1; setprop debug.cv10.pocket_atw 1; setprop debug.xrt.CV10_SCANOUT_FEEDBACK true; setprop debug.cv10.pocket_fence_wait 0'
```

Save prior properties with `getprop` and restore them after the run. Open **Pocket XR display preview → Open Pocket XR with direct rendering (experimental)** with VPN head tracking enabled. On the original Fold7 build, a successful fast path logged `CV10 producer four-view atlas 3200x2880: context 1600, center 1280 per eye`, a hardware buffer import and fused inset draws. `CV10 quad GLES FFR active` confirms draw-rate foveation.

## Exact replay comparison

The APK archive contains the measured replay and the measured restore pair. `pocket-budgeted-fence-replay` replaces USB yaw with a software sweep. It is for repeatable timing only. The Pocket APK with `bili-portrait` in its name forces one Bilibili window. Install and launch Bilibili separately on the device before using the fixture. The test does not bundle Bilibili. The connected Fold7 must be idle at the One UI launcher, lit at 60 Hz, at least 30% charged when resuming after a battery pause, and have the original `direct-atw` Monado and `gpu-timer` Pocket XR APKs from the package installed. Verify HID access, Broker, Shizuku and VPN access before the test. The runner checks the original APK hashes before swapping and restoring them. Use a writable copy of this toolbox.

```powershell
.\ffr-quad\run-pocket-budgeted-fence.ps1 -RunId office1 -Order AB -ApkDir C:\work\cv10-apks
```

Order AB runs lit/no wait, lit/wait, off/wait, off/no wait, while BA reverses this order. The OFF runs blank only the phone panel, after the runtime is already supplying the external clock. The device-side panel helper expires after at most 55 seconds. After a disconnect, reconnect and inspect state. If a test override persists, restore display 0 with `cmd display power-reset 0` and clear the experimental clock with `sfdo reset-forced-pacesetter`. Recheck the original APK hashes before starting another run. The independent [timed screen-off control](../../ports/Monado_CV10/history/fold7-cv10-screen-off.sh) can be used with Hello XR without Shizuku. Its restore behavior and preflight are documented with the [present analysis](../../ports/Monado_CV10/history/fold7-independent-present.md).

To reproduce the exact simulation, use a disposable Monado checkout at `5ab543f`. Apply `ffr-quad/set-pocket-yaw-replay.ps1 -MonadoSource <checkout>`, build the preview APK with the Monado Gradle instructions and run the same script with `-Restore` to put the original USB reader back. The matching Pocket layout patch and build instructions live in the Pocket XR submodule.

## Analyze and trace

```powershell
python ffr-quad/analyze-pocket-pipeline.py <prefix> --logs <evidence>/ffr-quad --surfaceflinger <evidence>/head-motion
```

Record a new Perfetto trace while the same scene is presenting.

```powershell
Get-Content ./ffr-quad/display-trace.pbtxt -Raw | adb -s $serial shell 'perfetto --txt -c - -o /data/misc/perfetto-traces/cv10.pftrace'
adb -s $serial pull /data/misc/perfetto-traces/cv10.pftrace .
adb -s $serial shell rm /data/misc/perfetto-traces/cv10.pftrace
python ffr-quad/inspect-fold7-connection-lock.py cv10.pftrace
```

Measure both DRM retire streams over the same steady-state or head-turn interval. Run from `tools/fold7-present` and use the CRTC IDs confirmed in the current trace. `288` and `301` were the phone and CV10 on SM-F9660 build F9660ZCUDBZJ9. These DRM object IDs come from the trace worker names. Android logical and physical display IDs use different identifiers.

```powershell
python ffr-quad/dual-display-retire.py cv10.pftrace --phone-crtc 288 --cv10-crtc 301 --start-s 1 --duration-s 20
```

`--start-s` is relative to the trace start. Select the head-turn interval before comparing runs. The report counts unique completed `signal_retire_fence` timestamps in the shared interval, then prints one-second counts, gap p95 and max, and gaps longer than 1.5 nominal periods. The command exits with status 2 if Perfetto reports trace loss, an ftrace CPU buffer overran, or the chosen CV10 has no retire events. Confirm display power and active modes separately. If the lit phone must sustain 60 new presents/s during the test, run a continuous animation on the phone to produce damage. A static phone image can legitimately produce fewer retire events. For Pocket XR, keep the existing pipeline and optical measurements to check the source frame cadence and the view through the lens. [Perfetto data loss checks](https://perfetto.dev/docs/concepts/buffers#debugging-data-losses)

Use Monado's `history/fold7-pocket-acquire-fence.py --help` to join Android frame events to Vulkan present IDs and the raw SurfaceFlinger file. Ftrace probes can depend on the system build. The sanitized numeric evidence archive keeps the markers needed to rerun the pipeline analysis. `reduce-capture.py` records the extraction used for the included comparison runs and is optional for new runs.

`ffr-quad/ahb-probe/run.ps1 -Serial $serial` builds the independent EGL/AHB/Vulkan sample using NDK 27.0.12077973. It uses the Windows default SDK location. The DPU sample requires the same NDK, Android SDK Platform 35, Build Tools 36.0.0, JDK 17, and a local H.264 MP4 such as a generated 1080p90 test card passed as `-VideoFile`. Build it with `fold7-dpu-probe/build.ps1`, then run `fold7-dpu-probe/run.ps1 -Serial $serial`. The retire-guard test C++ includes the extracted helper. The adjacent generator documents the source location used with the experimental Qualcomm patch. Those probe results do not install or validate a replacement HAL.
