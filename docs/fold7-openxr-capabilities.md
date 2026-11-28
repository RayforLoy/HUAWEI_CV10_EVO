# Fold7、CV10 和 CF20 的 OpenXR 接口

**v0.1.4-rc.3 更新**　下列早期候选中的四项已在 Fold7 接入。第三方客户端收到华为手柄动作、真实手柄当前电量、旋转角速度，以及 CV10 摘下和戴上的事件。下表的 66 项扩展与 `supportsUserPresence=0` 来自旧安装包。[新版实测、调用方式和设备边界](fold7-dual-controller.md)

2026-11-28 在 Galaxy Z Fold7 上用独立 OpenXR 客户端查询了嵌入 CF20 模型的 Monado CV10 Preview。头显使用原厂线及 5 V / 2 A 辅助电源，手柄通过 BLE 接入。客户端通过系统 Broker 找到 `Monado: Huawei VR Glass CV10 (USB IMU)`。PiliPlus 从同一运行时枚举到 66 个实例扩展。设备能力取自 `xrGetSystemProperties`。[设备查询与完整扩展列表](../research/evidence/fold7-openxr-capabilities-20261128.json)

| 当前系统查询项 | 返回值 |
| --- | --- |
| 核心 `orientationTracking` / `positionTracking` | 1 / 0 |
| `supportsUserPresence` / `supportsEyeGazeInteraction` / `supportsHandTracking` | 0 / 0 / 0 |
| HTC 眼部表情 / 唇部表情 | 0 / 0 |
| `maxLayerCount` | 32 |

能力查询在修复 CF20 首帧姿态复用之前执行。最终安装包在 PiliPlus 中仍枚举到相同的 66 项扩展。[最终安装包与实测](../research/evidence/fold7-cf20-model-20261128.json)

## 现有硬件可以继续接入的接口

| 优先顺序 | 接口 | 已有信号、缺口与验收方法 |
| --- | --- | --- |
| 1 | `XR_HUAWEI_controller_interaction` | 华为已有注册的 `/interaction_profiles/huawei/controller`。CF20 报告含触控板 XY、按压、扳机、Home、返回和音量键。驱动可补上物理输入，并保留现有 simple controller 绑定供旧应用使用。用同一个客户端逐项验证触摸边界、按键边沿及长按 Home 的系统回正。扳机目前能提供 0 和 1 两个状态。[CF20 报告字段](../controller/cf20-protocol.md#输入报告) · [华为交互配置](https://registry.khronos.org/OpenXR/specs/1.1/man/html/XR_HUAWEI_controller_interaction.html) |
| 2 | `XR_EXT_user_presence` | 此扩展已枚举。驱动打开 USB 时能读接近状态，仍需将变化传到 HMD 的 presence 输入并设置支持位。验证会话开始时的初始事件，以及摘下、戴上、重连的事件顺序。[USB 佩戴传感器](../ports/Monado_CV10/src/xrt/targets/openxr_android/src/main/java/org/freedesktop/monado/openxr_runtime/Cv10UsbReader.java) · [佩戴事件规范](https://registry.khronos.org/OpenXR/specs/1.1/man/html/XrEventDataUserPresenceChangedEXT.html) |
| 3 | `XR_EXT_interaction_profile_battery_state_display` | CF20 已解码输入报告偏移 17 的电量字段。先验证量程、失联和无效值，随后可按右手当前交互配置返回电量及有效位。手柄接电、手柄充电分别需要设备证据。辅助 5 V 接在线盒上。[CF20 电量字段](../controller/cf20-protocol.md#输入报告) · [电量接口](https://registry.khronos.org/OpenXR/specs/1.1/man/html/XrBatteryStateDisplayEXT.html) |
| 4 | 核心 `XrSpaceVelocity.angularVelocity` | 头显已有角速度，CF20 蓝牙报告也带陀螺仪三轴。可把手柄陀螺仪换算为 rad/s，校验手性、坐标系与时间戳后，经 `xrLocateSpace` 一并返回。实测可与同段四元数的旋转差分比较，覆盖水平、俯仰和翻转三个方向。[报告格式](../controller/cf20-protocol.md#输入报告) · [空间速度定义](https://registry.khronos.org/OpenXR/specs/1.1/man/html/XrSpaceVelocity.html) |

## 已经开放的接口和硬件边界

- 右手 `grip/pose`、`aim/pose`、`select/click`、`menu/click` 已供核心 simple controller 应用使用。新增的模型扩展提供静态网格、贴图和独立的模型空间。[CF20 模型的调用方式](../controller/cf20-openxr-model.md)
- `XR_FB_display_refresh_rate` 已可枚举和请求 CV10 外显模式。请求成功之后，仍要用外显图层不同的实际呈现时间戳核对帧率。原厂线有 3200×1600、90 Hz 且图层实呈 89.96 次/秒的记录。[原厂线实测](device-openxr-check.md) · [请求刷新率](https://registry.khronos.org/OpenXR/specs/1.1/man/html/xrRequestDisplayRefreshRateFB.html)
- CF20 的旋转由手柄 IMU 测得。普通接线下，头部和手柄的平移由模型估算。六自由度追踪需要另接定位硬件和有效的空间追踪结果。现有眼镜与手柄也没有已验证的眼动、手部骨骼或面部表情观测源。[头显驱动](../ports/Monado_CV10/src/xrt/drivers/android/cv10_device.c) · [位置估算](../ports/Monado_CV10/src/xrt/drivers/android/cv10_pose_models.c)
- 原厂 CF20 SDK 的 `startVibrate` 返回 `-1`，现有驱动没有振动输出。华为 profile 和运行时枚举的 haptic 扩展均不能证明这只手柄能执行振动。[手柄协议记录](../controller/cf20-protocol.md#搜索配对与订阅)
