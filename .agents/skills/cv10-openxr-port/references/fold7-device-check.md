# Fold7 与 CV10 实机验收

## 建立可比较的基线

从 Fold7 桌面启动未经修改的 Khronos OpenGLES `hello_xr`，再从目标应用的常用入口启动，保持线材、供电、Broker 和摄像头位置相同。记下手机型号、应用与运行时的包名和 APK SHA-256。稳定包和 Preview 可以共存，核对 Broker 实际选中的一项。活动显示 ID、USB 地址和无线调试端口都可能在重连后改变。[双眼样例基线](../../../../research/evidence/fold7-monado-cv10-session.log.txt)

在 PowerShell 先运行 `adb devices -l`，将本轮 Fold7 的序列号赋给 `$serial`。以下命令只读，适用于 P40 和 Fold7 同时在线的场合。

```powershell
adb -s $serial shell dumpsys usb
adb -s $serial shell dumpsys display
adb -s $serial shell dumpsys SurfaceFlinger --display-id
adb -s $serial shell dumpsys SurfaceFlinger --list
adb -s $serial logcat -d -v threadtime -s hello_xr MonadoView MonadoCV10 Cv10RefreshLease OpenXR-Loader
```

## 按第一处异常定位黑屏

| 观察 | 下一步 |
| --- | --- |
| Fold7 识别出显示器，活动时序只有 640×480、60 Hz | 在三星 DeX 的「连接的显示设备」选择「已镜像」，保持其他条件不变，重新读 `HUAWEIAV03` 的活动时序。本机普通 C-C 线在同一次对照中变为 3200×1600、90 Hz。另记逻辑桌面尺寸。[显示模式对照](../../../../docs/device-openxr-check.md#同一接线切换三星扩展和镜像) |
| 原版样例可见，目标应用在进入 XR 前退出 | 核对目标 APK 的实际 loader、Broker 可见性、必需扩展和初始化日志。已完成网络配对或视频解码的应用仍可能在 `xrCreateInstance` 失败。优先比较第一个失败调用。[Moonlight 实例创建记录](../../../../ports/moonlight-xr/README.md#兼容性修复) |
| 会话已 `FOCUSED`，系统外显截图有双眼画面，镜片仍黑 | 检查摄像头对位和实际佩戴状态，按同一时间线记录 USB 授权、开屏应答、IMU 计数、外显时序和镜片。原厂线上曾同时读到开屏 `OK`、约 90 次呈现/秒和持续 IMU，佩戴者及右眼相机均确认全黑。[对照记录](../../../../research/evidence/fold7-original-2a-openxr-20261126.json) |
| 原厂线重连后仍黑 | 记下线盒固件来源和辅助电源。本机曾用外接 5 V / 2 A 的 2 A 测试线盒，先接辅助电源，再接已解锁的 Fold7。保持手机端和供电不动，可只重插眼镜端约 5 秒，重新允许 USB 访问，对齐新外显、IMU 设备时钟与镜片首次出图。若同一 USB 地址被复用，检查运行时在重新取得 HID 后是否再执行线材识别、来源检查与开屏。记录是同一会话恢复，还是要重新启动应用。[重接与冷启动记录](../../../../research/evidence/fold7-original-2a-reattach-20261126.json) |

## 镜片、姿态和帧率分别取证

- **眼别与方向。** 先用显示探针的蓝色 L↑ 和橙色 R↑ 定位两台相机，按正常佩戴方向确认两侧字母正读。保持机位换到目标应用，两侧分别拍可识别的内容。播放或投屏可用连续变化的时间码。系统合成图用于量化视差，先将两半还原到佩戴方向，再比较同一前景物体的水平及垂直位置。只有一台相机时可换眼补拍，并注明两个采样时段。[双眼实拍与视差校验](https://github.com/RayforLoy/Monado_CV10/blob/11b9dcc1ea9cca535b29e2ef6f8f5cfb38964b7f/history/README.md#fold7-与-cv10-双眼实机验收2026-11-25)
- **头动来源。** 固定手机，只转动眼镜，记录同一时段的 CV10 USB IMU 计数、融合姿态和世界固定物体的运动；随后固定眼镜、只转手机作对照。`hello_xr` 的中央方块锁定在头部前方，转头时观察边缘方块。约 1 kHz 的有效样本说明驱动收到了数据，应用是否消费该姿态需用场景响应验证。将仅有静置采样、缺手机单独转动对照或仅验证 3DoF 的范围写入结果。[样例姿态日志](../../../../research/evidence/fold7-monado-cv10-motion.log.txt) · [Globalka 手机与电脑桌面实测](../../../../ports/globalka/README.md)
- **拖影与呈现频率。** 同轮记录手机主屏活动 Hz、CV10 面板活动 Hz，以及眼镜合成图层每秒不同的实际呈现时间戳数。用 `cmd display get-active-mode 0` 查主屏，从 `SurfaceFlinger --list` 选中本轮眼镜的 SurfaceView，用 `dumpsys SurfaceFlinger --latency` 加完整图层名取样。略过表头，取第二列的有效实际呈现时间，剔除 0、待呈现哨兵及重复值；纳秒时间戳的频率为 `(N-1) × 10^9 / (末值-首值)`。面板同为 90 Hz 时，本机分别测到图层约 60 与 90 次/秒。若在测 Shizuku 提频，核对该运行时授权和退出后的最低刷新率恢复值。串流另记内容帧率。[呈现间隔与等待时间](../../../../research/evidence/fold7-cv10-frame-pacing.json) · [Shizuku 授权对照](../../../../research/evidence/fold7-cv10-shizuku-reconnect.json)

交接时把应用与运行时版本、接线、普通入口操作、左右镜片证据、头动对照、退出与重进结果写在同一条记录里。例如只拍到右镜片时，写明「右眼已出图，左眼待拍」。换应用后重新验证该应用的镜片和姿态表现。
