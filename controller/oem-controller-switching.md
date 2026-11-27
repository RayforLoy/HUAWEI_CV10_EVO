# 华为 VR Glass 手机与 CF20 的控制切换

对照华为 VR SDK 3.5.0.82、华为 VR 手柄 10.0.1.345 和华为 VR 桌面 11.1.0.337 的 APK。本文记录 3DoF 模式的静态结果。6DoF 和 NOLO 共用控制器管理器，另有接管分支。

## 输入源选择

| 时机 | 触发条件及原厂动作 |
| --- | --- |
| VR SDK 首次选择输入源，CF20 可用 | `DefaultController` 绑定手柄服务并注册设备状态回调。服务刚绑定时，`getUsedDeviceList()` 中有 `activeState=1` 且 `connectState=2` 的设备才返回有效索引 `0`，随后报告 SDK 状态 `5`。管理器选中 `DefaultController` 并锁定。 |
| VR SDK 首次选择输入源，CF20 不可用 | 已绑定手柄服务但无有效设备时，`DefaultController` 报告 `-6`。管理器在来源未锁定时回退到 `PhoneController`。手柄服务绑定本身失败时，初始化也有直接尝试手机的分支。手机模式等 `VrTouchService` 就绪后上报 `5`，并启用触控与手机姿态。 |
| 手机操控中，CF20 连上 | 手柄 Binder 回调的设备状态 `2` 被映射为 SDK 状态 `5`。即使手机已锁定，管理器仍会把当前来源更新为 `DefaultController`，发送切换通知，关闭手机交互显示并注销触控捕获。无需等待 CF20 按键或首包输入。 |
| CF20 使用中突然掉线 | 手柄 Binder 回调的设备状态 `3` 被映射为 SDK 状态 `6`。已选中 CF20 时，管理器保留当前来源和锁定状态，记下断连并发出 `8192`。同一管理器内看不到由这条掉线回调直接切回手机的分支。 |
| 同一个 CF20 重连 | 再次收到状态 `5`，若它仍是锁定来源且先前记过断连，管理器发出 `4096` 并提前返回。手柄服务另有重连扫描路径，可通过桌面的 `VrHandleReconnectService` 按地址触发扫描。 |

`mUsingCtrl` 是当前输入来源，`getData()` 只从该来源取样。SDK 还用 `UsingCtrl` 保存选中的类名，后续由尚未锁定的管理器在手柄服务绑定时读取。该键在手柄服务的进程内 `HashMap` 中，`onVrModeChanged()` 会尝试清空它。已有管理器实例的 `mUsingCtrl` 和锁定状态是另一层状态，该方法未直接清除它们。`-5` 对应 2 秒的服务连接超时，和产生回退的 `-6` 是不同分支。

在这些样本中未找到保持 CF20 在线同时强制切回手机的桌面开关。华为公开说明也要求先断开手柄再排查手机操控，但未说明正在运行的原厂桌面何时重新建立控制器管理器。主动断开或取消配对后，何时重新进入手机模式仍待原厂真机验证。[华为手机操控说明](https://consumer.huawei.com/cn/support/content/zh-cn00776840/) · [华为触控排查](https://consumer.huawei.com/cn/support/content/zh-cn00776856/)

## 手机电源键与桌面显示

进入手机操控后，桌面包内的 `VrTouchService` 载入 SDK 的触控服务实现。SDK 通过 `IVrTouchManager` 开启手机模式，服务再通过华为系统接口 `VrTouchInterfaceEx` 捕获手机主屏输入。电源键 `KEYCODE_POWER=26` 的抬起事件翻转 `mIsDisplayPowerOn`。闭屏时停止取新的手机姿态，触控事件停止转发。对于贴近检测有效、手机交互显示开启且超过 120 秒未触控的情况，`PhoneController` 也会调用同一闭屏路径。这两条路径都保留手机作为当前来源。

| Java 通知中的参数 | `HVRCORE.dll` 与 `Assembly-CSharp.dll` 的处理 |
| --- | --- |
| `2097153` 开启交互显示 | `HVRNoticeCore.GetDialogueMessageIndex()` 置 `mIsScreenOn=true`。`HVRController.UpdateControllerMode()` 显示手机模型与射线。 |
| `2097154` 关闭交互显示 | 置 `mIsScreenOn=false`，隐藏手机模型与射线。 |
| `2097155` 切换到实体手柄 | 置 `mIsSwitchToController=true`，桌面将当前模型换成 CF20 并启用射线。SDK 还设置内部键 `swithToDefaultCtrl`，让随后的手机闭屏回调跳过普通的 `2097154` 通知。 |

手机触控经 `PhoneController` 转换为同一套控制器数据，中央触控区提供坐标和确认，侧边向内滑提供返回，底部上滑提供主页。位姿来自 `getPhoneControllerPose()` 的四元数，位置和模拟扳机值为零。可以用这些字段区分手机模拟输入与 CF20 的 [蓝牙报告](cf20-protocol.md)。

具体手势分区、手机姿态和桌面射线见[原厂手机操控逆向](oem-phone-controller.md)。

## 复核位置

| APK 与版本 | SHA-256 | 入口 |
| --- | --- | --- |
| `com.huawei.hvrsdkserverapp` 3.5.0.82 | `e0af366239d1c9c8ad384651a3173dfdfccac9ba221768f4db6c5349101d1444` | JADX 查看 `classes.dex` 和单独解出的 `assets/hvrframework.dex`。复核 `com.huawei.vrframework.VrControllerManager` 的 `init`、`chooseController`、`onStatusChanged`、`deviceConnetedProcess`，以及 `DefaultController.onServiceConnected`、`DefaultController.onDeviceConnectionStateChanged`、`PhoneController.onPhoneControllerMode`、`VrTouchService.VrInputEventCb`。两个 DEX 的相关分支一致。 |
| `com.huawei.vrhandle` 10.0.1.345 | `e947fc358e9692358ac42cfe4a565c112f7fc9349da693643f863d08af98b3d2` | `com.huawei.vrhandle.g.a.onTransact` 的 `14` 和 `15` 分别写读 SDK 键值。`com.huawei.vrhandle.service.VRHandleService.Z2` 写入 `f808w`，`r1.x.b0` 用 `deviceAddress` 请求重连扫描。符号名来自本次 JADX 输出。 |
| `com.huawei.vrlauncherx` 11.1.0.337 | `1e91f00d596c636c3f52dddc494ee6b745cdf90bb3a0838ff203f9ae54b92dd3` | ILSpy 查看 `assets/bin/Data/Managed/HVRCORE.dll` 的 `HVRNoticeCore.GetDialogueMessageIndex` 和 `HVRPluginCore.IsSwitchToController`，以及 `Assembly-CSharp.dll` 的 `HVRController.ActivateAvailableController` 和 `HVRController.UpdateControllerMode`。 |
