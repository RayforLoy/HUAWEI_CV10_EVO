# Moonlight XR CV10 实机记录

2026-11-27 香港时间。Fold7（SM-F9660）连接 HUAWEI VR Glass CV10、原厂手机线（读取版本 C9.53.6）及外部 5 V 供电。三星 DeX 处于镜像模式。Windows 端运行 [Sunshine v2026.914.233613](https://github.com/SunshineStream/Sunshine/releases/tag/v2026.914.233613)，通过同一局域网推送桌面测试卡。手机由 OpenXR 启动器会话交接，测试后已将设备交回，Broker 恢复至稳定包，系统 `min_refresh_rate` 读数为 `null`，电量 58%。

| 使用的 APK | 包名 | SHA-256 |
| --- | --- | --- |
| 上游 Moonlight XR 12.1-xr0.4.3 | `com.gilleece.moonlightxr` | `acb2221aff323b4da23e5acb04667797dc2043bd1e6895e1a2eb44119c4a1f99` |
| Moonlight XR CV10 12.1-xr0.4.3 | `org.cv10.moonlightxr` | `581e973086ef5a2a378a542c2d87d32a8d768dc078e9723868f1131948fbaf39` |
| Monado CV10 0.1.2 稳定包 | `org.cv10.monado.out_of_process` | `989c7b43ecd369ed5aa49776542db4511e02ac0d0257395d9c4fd40fdf9f26c5` |
| Monado CV10 Preview，含 `4fe230f` | `org.cv10.monado.out_of_process.launcher_preview` | `92dda4b0080e832d702a2704ab90efa08bb345b8e26e67a87b435f8156f30616` |
| Monado CV10 Preview，`dfd193e`，含卸载修复及 16 KiB 对齐 | `org.cv10.monado.out_of_process.launcher_preview` | `3b58266c44ed11add2a0667d3b4c27fdc3b7f0b4604b4d4e0cc875b26aea37d5` |

| Moonlight 和运行时组合 | 串流及显示 | 退出及重进 |
| --- | --- | --- |
| 上游 APK + 稳定包 | 配对及 HEVC 串流协商成功。00:19 OpenXR 初始化抛出 `NoSuchMethodError`，会话未进入 `FOCUSED` | 初始化失败后渲染线程崩溃 |
| CV10 APK + 稳定包 | 两次进入 `FOCUSED`。右镜片拍到测试卡，外显两半的计时器同步更新 | 00:37:49 和 00:40:15，各按一次系统返回键，两次均在 `xrDestroyInstance` 成功、运行时卸载后收到 `SIGSEGV`。第一次崩溃后重新启动应用能继续串流 |
| CV10 APK + 预览修复包 | 00:41:28 和 00:42:44 均进入 `FOCUSED`，两次右镜片都拍到同一张动态测试卡。ZipDepth 选择 GPU，交换链为 5120×1440，重进后眼镜 USB IMU 每 5 秒增加约 5,000 个有效样本 | 00:42:13 和 00:43:28 均正常返回应用界面，进程 PID 19375 全程保持。重进创建了新的 OpenXR 会话，检查时段内的 Android crash buffer 未出现该包的崩溃 |
| CV10 APK + 16 KiB 对齐预览包 | 00:55:29 和 00:56:39 均进入 `FOCUSED`。Sunshine 再次确认 2560×1440、90 fps、HEVC，首次和重进后右镜片均可读到测试卡计时器 | 00:56:27 和 00:57:18 均正常退出，重进前后 PID 均为 32285。该时段 crash buffer 中没有 Moonlight 条目 |

Sunshine 日志确认 RTX 3090 的 `hevc_nvenc`，串流配置为 2560×1440、90 fps。CV10 面板活动模式为 3200×1600、90 Hz。稳定包单次 SurfaceFlinger 窗口内，127 个不同的实际呈现时间戳从首帧到末帧跨度约 2.09 秒，合计约 60.3 次/秒。当时 Fold7 主屏为 60 Hz。

CV10 外显的 [第一帧](cv10-composite-a.png) 和 [第二帧](cv10-composite-b.png) 保留面板的原始双眼方向，测试卡计时器从 `00:40.77` 走到 `00:43.72`。[修复运行时首次右镜片实拍](right-lens.jpg) 和 [重进后右镜片实拍](right-lens-after-resume.jpg) 分别显示 `00:28.71` 和 `01:38.13`。

将两张外显帧的左右半图各旋转到正读方向后，按蓝圆和黄方块的颜色求像素质心。两帧分别测得蓝圆左右眼水平差约 18 像素、黄方块约 20.5 像素，垂直差均小于 1 像素。这项测量取自面板合成图。

用户报告测试期间碰到电源，导致两次断连。一次运行日志在 00:36:59 记录 USB 权限重请求，00:37:02 会话重新聚焦并再次开屏。退出测试另有独立的 `xrDestroyInstance` 和崩溃时间戳。

现有相机对准右镜片。左镜片光学实拍和佩戴转头待验，现有证据覆盖双眼外显帧、右镜片与眼镜 IMU。键盘回传没有在 PC 测试卡上取得读数。`4fe230f` 预览包曾显示系统 16 KiB ELF 兼容性提示。`dfd193e` 的五个 ARM64 原生库均通过 16 KiB ELF 段校验，APK ZIP 对齐和签名也通过。这轮从桌面启动运行时未再弹出该提示。Moonlight CV10 APK 自身通过 16 KiB ZIP 与全部七个原生库的 ELF 对齐检查。

`dfd193e` 回归留有[重进后的右镜实拍](aligned-right-lens-after-resume.jpg)和[静止状态姿态日志](aligned-stationary-pose.log.txt)。同一采集窗口取得七张外显帧、五个眼镜姿态四元数，角速度峰值约 0.007 rad/s。这里记录的是静止基线。上游原生测试 `xr_math` 的 169 项和 `xr_headaim` 的 1598 项在 Windows 主机均通过。需进行转头验收时，可在运行时启动前临时设置 `debug.xrt.XRT_LOG` 为 `info`，按 `monado.cv10_worker` 读取眼镜姿态，同时记录相应外显帧。这轮结束时已恢复日志级别与稳定 Broker，`min_refresh_rate` 为 `null`，电量 59%。

## 日志节选

以下时间为 Fold7 的本地时间，省略进程路径及无关日志。

```text
00:19:17.999  monado.android_lifecycle_callbacks_create: NoSuchMethodError: kotlin.jvm.internal.Intrinsics.checkNotNullParameter(Object, String)
00:19:18.000  moonlight-xr: xrCreateInstance failed: -51 XR_ERROR_RUNTIME_UNAVAILABLE

00:36:02.146  moonlight-xr: swapchain 5120x1440 format 35907, 3 images (stereo mode 6)
00:36:02.274  moonlight-xr: session focused for the first time
00:37:49.921  OpenXR-Loader: RuntimeInterface::UnloadRuntime - Unloading RuntimeInterface
00:37:49.924  libc: Fatal signal 11 (SIGSEGV), tid 14037
00:37:50.481  DEBUG: #01 libc.so (__cxa_thread_finalize+80)
00:40:15.512  OpenXR-Loader: RuntimeInterface::UnloadRuntime - Unloading RuntimeInterface
00:40:15.515  libc: Fatal signal 11 (SIGSEGV), tid 18581

00:41:28.464  moonlight-xr [pid 19375]: session focused for the first time
00:42:13.787  moonlight [pid 19375]: session ended
00:42:44.890  moonlight-xr [pid 19375]: session focused for the first time
00:42:49.514  MonadoCV10: CV10 valid IMU samples=5000
00:43:24.520  MonadoCV10: CV10 valid IMU samples=40000
00:43:28.631  moonlight [pid 19375]: session ended

00:55:29.421  moonlight-xr [pid 32285, dfd193e]: session focused for the first time
00:56:27.461  moonlight [pid 32285]: session ended
00:56:39.038  moonlight-xr [pid 32285, dfd193e]: session focused for the first time
00:57:18.258  moonlight [pid 32285]: session ended
```
