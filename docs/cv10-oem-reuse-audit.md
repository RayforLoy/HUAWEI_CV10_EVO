# 华为 VR 六个原厂 APK 二次逆向

2026-11-28 · 目标是为 Fold7 上的 Monado CV10、Pocket XR CV10 和 PiliPlus 找可复用的协议、算法和应用设计。01–06 的文件长度和 SHA-256 均与样本清单匹配。使用本地 APK、JADX/DEX、Unity 程序集及序列化资源、ARM ELF 符号和反汇编。Monado 发布对照为 `fedf56c`（v0.1.4-rc.2），手柄和启动器另核对本地 `1290fc9`。本轮为静态分析，未运行应用或连接设备。逐眼投影、RGB 畸变、软件 IPD、中心分区及锐化的既有结论见前期记录。[样本清单](../research/sources.json) · [APK 分析方法](apk-research.md) · [原厂渲染对照](cv10-oem-rendering.md)

| APK | 新增可复用项 | 适合接入的位置 |
| --- | --- | --- |
| 01 SDK Runtime `3.5.0.82` | 按真实 VSync 相位预测，后期重投影另取多个姿态；私有固定中心分区；定位套件安全区 | Monado CV10 帧调度、扫描补偿和分区合成；定位有效后再做安全区 |
| 02 华为 VR `12.2.1.301` | 商店场景也序列化了 High 固定中心分区；3DoF 有肩肘腕运动模型 | 分区渲染对照；手柄模型与射线原点 |
| 03 VR 视频 `8.2.0.300` | 视频 GPU 2× 超分和 HiAI 超分；逐片立体格式记忆及舒适单视图；SMB 桥接 | PiliPlus 等播放器的解码后、提交前 |
| 04 VR 手柄 `10.0.1.345` | 分阶段 GATT 超时、退避、清理及重订阅；校准状态位 | Monado CV10 的 `Cv10ControllerLink` 和外设诊断 |
| 05 VR 桌面 `11.1.0.337` | 独立双眼 UI 提交；定位器接入、位置跟踪、安全区和应用切换状态 | Monado 启动器与 6DoF 诊断 |
| 06 VR 手机投屏 `11.1.0.325` | 虚拟屏应用布局、采集像素尺寸和空间面板几何分开控制 | Pocket XR CV10 的面板清晰度；现有采集路径可继续使用 |

## 01 SDK Runtime · 帧时序、姿态和安全区

- **帧时序。** ARM64 `libvrsdk.so` 的 `VRRenderVsync::getPredictTimeMS`（`0x7dde4`）以单调时钟下的 VSync 锚点、序号及周期计算应用的目标时间。`RenderModule::Create`（`0x8b444`）把 `TYPE_HALLIDAY` 映射到枚举 2。该分支默认瞄准当前 VSync 相位向下取整再前移 3 个周期。以 90 Hz 举例，调用时刻到目标时刻相隔约 22.2–33.3 ms。`HxrCompositor::waitFrame`（`0xdcf80`）把 `getPredictTimeUs` 转为 `predictedDisplayTime`，另填固定的 `13,333,333 ns` 作为 `predictedDisplayPeriod`。这个字面值不能作为 CV10 的刷新率测量。Monado 此处已使用按外显模式确定的周期。[当前帧周期实现](../ports/Monado_CV10/src/xrt/compositor/main/comp_compositor.c#L223-L242)
- **后期重投影。** `VRRenderWalleImpl::getPositionAjustMatrix`（`0x89934`）另按合成缓冲模式取样。Halliday 的 `frontbuffPredictTimePointForWalleX`（`0x17c1ac`）为 `{1.5, 2.0, 2.0, 2.5}`，`swapbuffPredictTimePointForWalleX`（`0x17c1cc`）四项均为 `2.5`，单位为 VSync 周期。绘制循环每次取一对姿态矩阵并传给畸变着色器。Monado 已有逐扫描区间的首尾姿态补偿。当前 CV10 驱动未提供触发该算法的扫描方向和时长。适合先测 Fold7 实际呈现相位及扫描方向，再决定是否给 CV10 接入现有补偿。[Monado 扫描补偿](../ports/Monado_CV10/src/xrt/compositor/main/comp_renderer.c#L272-L355)
- **3DoF 预测。** `libvrpose.so!HelmetPose::getPose`（`0x152c0`）使用 `libWalleAlg.so!VrPoseState::predictPose`（`0x22d44`）。它以最后姿态和角速度构造增量旋转，按角速度及模式缩短外推时间，预计转角小于等于约 `0.004 rad` 时保持原姿态。这个 SDK JNI 入口经 `VrControllerManager` 接入控制器置中。原厂 OpenXR 的位姿接口经 IPC 取样。Monado CV10 当前使用姿态历史、陀螺外推和 50 ms 上限，可对同一段 IMU 记录比较静止抖动、慢转滞后和快速转向过冲。[Monado CV10 位姿读取](../ports/Monado_CV10/src/xrt/drivers/android/cv10_device.c#L181-L251)
- **定位套件安全区。** `service/f.java` 的 `generateSafeArea` 检查 USB 定位器、相机、位置跟踪、休眠和升级状态，满足条件才起 `GuardianArea`。该 Activity 接入 `libGuardianArea.so`。ARM64 `CreateFence::CreateFenceRunning`（`0x6bf88`）分派环境扫描、设地面、自动围栏和手绘围栏。`GuardianArea::ProcFenceUpdate`（`0x60d94`）更新监视器并触发越界检测。库依赖 `libarvr_slam.so`、`libVR6Dof.so` 及华为运行时模块。可借鉴位置有效性门槛、地面和边界记录以及越界反馈，实用前提是 Fold7 上先得到定位套件的有效 6DoF 位姿。[现有套件移植与待验证项](../controller/kit-6dof-protocol.md)
- **平面检测。** `libruntime_service_module.so` 的 `PlaneImpl::GetSlamPointCloud`（`0x10362c`）读取 SLAM 点云。`PlaneDetectionAdapter::PlaneProcess`（`0xfceb4`）把点和对应位姿送入平面管理。`PlaneImpl::GetGroundPlaneInfo`（`0x103d9c`）先查检测平面，再尝试用双手柄位置推断地面。现有套件适配已请求点云和锚点格式，当前向 CV10 设备输出的是位姿，后续可以独立实现点云到地面拟合并对接 Monado 的平面接口。原厂适配器使用其 C++ ABI。[现有 SLAM 适配](../ports/Monado_CV10/src/xrt/targets/openxr_android/src/main/cpp/cv10_kit_slam.cpp#L24-L38)

以上 ELF 位于 `com.huawei.hvrsdkserverapp/raw/assets/arm64-v8a`。`libvrsdk.so`、`libvrunityplugin.so`、`libvrpose.so`、`libWalleAlg.so`、`libruntime_service_module.so` 五个成员的 SHA-256 与 P40 已留样本一致。`libvrsdk.so` SHA-256 为 `5b95a82174d26b548829ff4fd8399603d5d791101eabfc35786276c3ddf7ae39`，`libGuardianArea.so` 为 `57f6c7c194d640c7bbe7724f34168c8edf0a3542ddeb8eda7b54f90c3b4cdf7`。

### 固定中心分区与 OpenXR 扩展

- 原厂 ARM64 `libvrsdk.so!hxr_xrEnumerateInstanceExtensionProperties`（`0xee8c4`）读设备信息，命中 `CV10` 时扩展表多出 `xrfoveatedHW` v1（`0x147b20`）。两张枚举表都无 `XR_FB_foveation`、`XR_FB_foveation_configuration`、`XR_FB_foveation_vulkan` 和 `XR_FB_swapchain_update_state`。SDK 的 `GazingHandleImp::getPostion`（`0x61ff8`）到 `ScheduleManager::GetGazePoint`（`0x66ab0`），后者直接返回 `-1`。校准和眨眼的相邻入口也直接返回 `-1`。
- **原厂 OpenXR 提交契约。** `hxr_xrCreateInstance` 在 `0xe7564–0xe75d4` 检查 `xrfoveatedHW` 名称。真正设置分区位的是 `HxrSwapchain::HxrSwapchain` 在 `0xe6728–0xe674c` 对 `arraySize == 2` 的检查。`HxrCompositor::beginRender` 在 `0xdce04–0xdcf50` 读取该位并传入固定比例约 `0.403195`，双层交换链的颜色和深度纹理经 GLES `glTexStorage3D` 分配。`HxrSession::endFrame` 在 `0xe2e80–0xe2e8c` 只接受一或两个投影视图。原厂这个 OpenXR 入口使用双层交换链承载双区，应用仍提交普通投影视图数量。当前的普通双目应用需要配合生成相应的中心内容才可利用这套机制。
- 官方 OpenXR SDK `3.5.0.79` 包的 `sdkDemo/HVRSDK_XrDemo/jni/openxr/openxr_hw.h:30` 也声明 `xrfoveatedHW`。同目录的 `xr_demo.cpp:475,977` 实际用 `arraySize = 1`、`imageArrayIndex = 0`。此前 SDK Demo 的运行日志覆盖普通双目。私有分区的实机行为仍待验证。[官方 SDK 样本位置](../research/sources.json)
- Unity 原生插件另有 `HVR_InitRenderFoveatedThread`（`0x1c1b4`）和 `HVR_FoveatedCameraEndFrame`（`0x1d560`）。它把输出写入颜色和深度的纹理数组。原厂合成 shader（`libvrsdk.so` 的 `0x121d5e`）在固定中心内采样中心高分层，外围采样全视场层，保留 R/G/B 独立畸变 UV。中心锐化仍由另一个开关和变体控制。[原厂渲染对照](cv10-oem-rendering.md)
- 当前 Monado CV10 分支的 OpenXR 扩展表没有上述四个 `XR_FB_*` 扩展，CV10 驱动声明两个视图，仓库里的 `XR_VARJO_quad_views` 路径还取决于编译和设备视图能力。华为的固定中心分区可作为独立实现的对照。面向现成应用提供 FB 接口还需要实现 profile、swapchain 状态和对应图形后端语义。[Monado 扩展表](../ports/Monado_CV10/src/xrt/state_trackers/oxr/extension_support/oxr_extension_support.py) · [CV10 视图数](../ports/Monado_CV10/src/xrt/drivers/android/cv10_device.c#L318-L325) · [Khronos swapchain 状态扩展](https://github.com/KhronosGroup/OpenXR-Docs/blob/main/specification/sources/chapters/extensions/fb/fb_swapchain_update_state.adoc)

## 02 华为 VR · 商店场景及 3DoF 手柄

- `assets/bin/Data/level0` 的 `HVRCamera` 对象使用路径 ID 32 的 `HVRRenderMgrCore` 组件，脚本在 `globalgamemanagers.assets` 内的 ID 85。序列化字段选择 `_highQuality`、24 位深度、关闭 single-pass，场景倍率为 `1.3333300352`。按该 APK 自带 `HVRCORE.dll` 的静态初始化，`1080 × scale` 截断并向下对齐为 1438，初建纹理为 `1438×1438`，使用 2× MSAA。支持分区时调用 `InitRenderThreadFoveated(40)`。`SetRenderRatio` 的 High 更新档上限为 `1280×1280`，温控告警时更新尺寸先乘 0.71。运行时可以覆盖尺寸。这提供第三个原厂 Unity 应用的分区对照，实际首帧纹理仍需测量。
- 商店程序集里的 `HVRController` 调用 `HVRArmModel.OnUpdateController` 算虚拟腕点。肩部参考头部水平朝向，肘腕随手柄角度偏移，左右手镜像。桌面已有同类模型记录。当前 CF20 驱动用固定的相对头部位置，若指向近物时偏移明显，可在 OpenXR 的 `grip`、`aim` 或手柄模型上对照这套几何。模拟出的位移只可作为推算位置。[原厂桌面手柄证据](../controller/oem-phone-controller.md) · [当前 CF20 驱动](../ports/Monado_CV10/src/xrt/drivers/android/cv10_controller.c#L130-L175)
- `WelcomeVRActivity.java:76` 的全景由 Google `VrPanoramaView` 与 `libpanorenderer.so` 实现。`VRDeviceInfoUtils` 的 `libvrinfo.so` 为设备序列号查询服务。商店对原厂 VR 应用的 `com.huawei.android.vr.application.mode=vr_only` 标签和 `com.huawei.android.vr.action.MAIN` 启动 action 可用于旧应用目录识别，是否能启动取决于各应用的原厂 SDK、ABI 和系统依赖。[当前 OpenXR 应用目录识别](../ports/Monado_CV10/src/xrt/targets/openxr_android/src/main/java/org/freedesktop/monado/openxr_runtime/Cv10AppCatalog.kt)

## 03 VR 视频 · 视频清晰度与播放体验

- **视频超分。** `assets/wiseplayer_plugins/video_super_resolution/5.0.5.315/` 同时带 GPU 和 HiAI 分支。ARMv7 `libSuperResFramework.so` 的 `GpuAdapter::InitGpuAlgorithm`（`0xa9d80`）、`CreateFilterSR`（`0xab0ca`）和 `FilterSR::InitFilterSrShader`（`0xaceb4`）对应 GLES 3.10 的 `HiCGFilterSR2x`。着色器按亮度梯度的 24 个方向、3 档强度、3 档相干性组合为 216 组，结合 2×2 子像素相位选择 7×7 滤波系数。低梯度区域回退到源亮度采样。包内另有 `FilterSRData.bin` 和 4 个 HiAI `fsr_*.om`。Unity 启动会尝试安装打包插件，完成设备能力检查和 `VIDEO_SR` 开关才可能走超分。本轮未定位 Unity 主播放链启用该开关的证据。建议在 PiliPlus 的解码纹理上对照同类 GPU 放大，缓存一次视频帧结果供双眼采样，再量画质和成本。[PiliPlus 现有锐化与色调映射](../ports/piliplus_monado/native/tone_mapper.cpp)
- **片源格式。** `VideoFormatSettingPanel.cs`、`HviPlayViewPresenter.cs` 和 `PluginInterface.cs` 贯通平面、180°、360°面型及单目、左右、上下布局，可记住单片设置。关闭 3D 效果可让双眼共用左或上半幅。PiliPlus 已有投影档和立体切换，优先补逐片记忆与舒适单视图。`DmpPlayer.cs:178` 在无已保存清晰度时对 360° 内容初始请求 `3840×2160`，普通内容请求 `1280×720`。`SetSurfaceSize.cs` 为在线 180° 与 360° 申请 `4096×4096` 的内容纹理，默认平面 `2048×1024`。视频选档、Unity 内容纹理和每眼渲染尺寸各自分配。[PiliPlus 播放器入口](../ports/piliplus_monado/java/com/example/piliplus/vr/VrPlayerActivity.java)
- **HDR。** WisePlayer 的 `cxe.java` 有软件 HDR Vivid PQ 色调映射着色器。Unity 的 `DmpPlayer.cs` 通过 `DmpViewClient.java:1456` 把 Surface 标成 VR 类型 3。`PowerPlayer.java:3969,4494` 明确屏蔽 VR 类型的软件 Vivid。这一算法可以作为实现 HDR Vivid 的参考，现有证据只覆盖软件分支。
- **其他应用资源。** `LocalVideoPresenter.cs:943` 把 NAS 文件交给局域网 SDK，后者经 SMB2 随机读和本机 HTTP Range 响应提供给 FFV 播放器，也独立加载字幕。H3DA 插件带 HRTF、BRIR 和空间音频处理接口，尚未确认头姿输入的实际调用。`WISE_DANMU` 有 HiAI 人物分割模型及带时间戳的 `HumanOutline` 回调，尚未确认 Unity 消费回调。前一项可复用播放器接口设计，另两项分别提供空间音频和弹幕遮挡的算法参考。

## 04 VR 手柄 · CF20 的分阶段重连

- 原厂 JADX `t0/s5.java` 的 `:281`、`:585`、`:844`、`:870`、`:982` 串起 GATT 重连状态机。连接与服务发现各有 20 s 看门狗，连接后延迟 1 s 开始发现，第一项 CCCD 确认成功后隔 500 ms 再订阅第二项。断连清理旧 GATT 和回调后对合格状态最多做三次快速重试，状态 133 等待 5 s，其他等待 1 s。主动断开、蓝牙状态和上一状态会影响重试资格。
- 当前 `Cv10ControllerLink` 使用 12 s 整体建链超时、固定 3 s 重试、连上立即发现，已做到按回调顺序订阅两项通知。适合独立实现原厂的分阶段超时、按错误退避和旧连接回调过滤，并记录 `connect → discovery → CCCD → first input` 各阶段耗时。原厂延迟可用作首轮对照值。Fold7 是否需要全部延迟仍需实测。[原厂 CF20 协议](../controller/cf20-protocol.md) · [当前 GATT 实现](../ports/Monado_CV10/src/xrt/targets/openxr_android/src/main/java/org/freedesktop/monado/openxr_runtime/Cv10ControllerLink.java)
- `VRHandleService.java:1297,1435,1583` 将蓝牙恢复、头显佩戴和 VR 会话状态接入扫描重试。Monado 可以用现有会话和蓝牙状态驱动重连。JADX `com/huawei/vrhandle/a.java:1019` 的另一处电量字段出现在 OTA 失败回传。常规使用可读取下述输入报告的电量字段。
- **校准状态。** CF20 固件 `4.0.5` 起，`z0/x.java:34`、`z0/y.java:6` 和 `z0/j.java:46` 走新版校准。对 20 字节输入报告按零起点索引，`byte[14] & 1` 代表画 8 完成，`byte[12] & 1` 代表静置完成。旧固件界面用加速度和角速度条件作判断。原厂 SDK 与 Monado 同时将完整的第 12、14 字节用作陀螺量，可先把两个低位按固件版本用于只读诊断。`byte[17]` 电量已在当前报告解析，适合直接显示为已知或未知。[当前报告解析](../ports/Monado_CV10/src/xrt/targets/openxr_android/src/main/java/org/freedesktop/monado/openxr_runtime/Cv10ControllerReport.java#L31-L36)

## 05 VR 桌面 · UI 图层和定位套件入口

- `assets/bin/Data/globalgamemanagers` 的 `TagManager`（路径 ID 3）注册了 `HVRVolumeUILayer` 和 `HVRUILayer`。`HVRRenderMgrCore.cs:244,275,771,945` 按注册表建 UI 纹理并用 `LeftEyeUILayer`、`RightEyeUILayer` 提交。尺寸取 Android 上 `Screen.width` 和 `Screen.height` 较短值的一半。`HVRLayoutCore.cs:664` 动态设置音量层，`HVRCamUICore.cs:114` 对较新的头显过滤普通 `HVRUILayer`。静态场景对象也以 Unity `UI` 等层为主，证据支持专用 UI 纹理机制，尚不能据此估算 CV10 上整套桌面菜单的锐度或成本。Monado 已有双眼 capture quad，可给固定尺寸的文字和菜单做独立图层对照。[当前启动器](../ports/Monado_CV10/src/xrt/targets/openxr_android/src/main/cpp/cv10_spatial_launcher.cpp#L1110-L1150)
- `TitleSceneManager.PrepareStartMainScene` 用 USB 定位器、系统能力和安全区状态决定初始路由。`SixDofInterface.SixDofViewSafeArea` 由 `VrRuntimeBridge` 委托 01 的安全区 Activity。`t1/d0.java` 的首次教学检查独立的 `com.kukrgame.OOBE`，可经商店跳到详情页。适合在现有启动器提示定位器未接、相机未就绪和追踪已就绪，按实际能力启用后续操作。教程和底层系统服务各有独立包依赖。

## 06 VR 手机投屏 · 采集、几何和回填

- `b/a/c/f/z.java:274,340` 在一块逻辑显示上运行 2D 应用，按源屏旋转、宽高、DPI 配置应用布局。`b/a/c/f/a0.java:79,95,137` 把内容交给单独的方形采集缓冲，在画质改变时保持逻辑连接并更新 `SurfaceTexture` 和 `VirtualDisplay` 尺寸。采集像素数由 `832/896/1024/1280/1536` 档选择。来帧置标志，绘制时才更新纹理。`b/a/c/h/b/y/q.java:400,542,585,857` 按源宽高比生成平面或弧面几何及 UV，再以普通线性过滤取样。触控坐标按目标屏尺寸还原，经华为的显示 ID 输入接口回填。[Android VirtualDisplay](https://developer.android.com/reference/android/hardware/display/VirtualDisplay#resize(int,int,int))
- Pocket XR 适配已保留虚拟 display ID 原地调尺寸，使用 `ImageReader` 独立接收帧和 mipmap 下采样，并特别处理 `SurfaceTexture` 堵塞显示生产端的情况。可以借鉴原厂显式区分应用 DPI、采集像素密度和面板视角的设计，独立控制文字和视频清晰度。采集档位和中心分区纹理不共享尺寸参数。[Pocket XR 调整窗口](../ports/pocket-xr-cv10/app/src/main/kotlin/com/hayeco/flipspaces/spatial/SpaceRenderer.kt#L2644-L2686) · [Pocket XR 帧接收](../ports/pocket-xr-cv10/app/src/main/kotlin/com/hayeco/flipspaces/spatial/PanelFrameThread.kt#L42-L51)

## 落地顺序

1. **CF20 重连。** 现有蓝牙入口可直接应用阶段状态机。结果以休眠唤醒、蓝牙恢复、连接丢失和主动断开的成功率、首个输入延迟衡量。
2. **头姿时序。** 先记录 Fold7 呈现相位及扫描方向，并离线比较慢转、快速反转和静止段。确认设备参数后再接入已有扫描补偿。
3. **视频或面板的局部清晰度。** 视频优先试播放器端超分，文字优先试独立菜单图层和面板像素密度。记录源分辨率、每帧 GPU 时间、丢帧及镜片实拍。
4. **位置跟踪与安全区。** 先完成定位器、外接 Y8、时钟和有效位置的设备验收，再加入地面、围栏和重定位交互。
