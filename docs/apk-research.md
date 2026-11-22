# CV10 APK 离线分析

华为原厂服务有一条经 VCOM 串口控制屏幕的路径。头显 HID 初始化、姿态读取、DP 显示枚举和华为 VR 应用路由各有自己的入口。Fold7 可以先用原厂手机线验证 DP 外屏输出。如果系统识别到外屏却始终黑屏，再查接近传感器、供电、实际时序及是否出现 VCOM 接口。

## 样本来源与复现

固定下载地址、字节数和 SHA-256 见[样本清单](../research/sources.json)。官方 Unity `3.5.0.68` ZIP 附带 `3.5.0.68.apk`。官方 OpenXR `3.5.0.79` ZIP 包含 loader、SDK 及示例，示例构建配置选择 `armeabi-v7a`。另外七个 APK 来自固定社区镜像。镜像维护者记录 `vrservice` 来自 HMA-AL00、EMUI 11.0.0.155 的 `hw_product` 分区 `/region_comm/china/app/VRServiceX/VRServiceX.apk`。这个来源对应 Mate 20，用户的 P40 Pro+ 仍需在真机阶段核对包版本及系统服务。[华为 Unity SDK](https://developer.huawei.com/consumer/cn/doc/graphics-Library/unity-sdk-download-0000001142315529/) · [华为 OpenXR SDK](https://developer.huawei.com/consumer/cn/doc/graphics-Library/openxr-sdk-download-0000001148849243/) · [社区样本基线](https://github.com/EnYaoJingYa/huawei-vr-compat/blob/03bf1012493fd821f38114010e4b21fe20f1d4f1/docs/BASELINE.md) · [固件提取记录](https://github.com/EnYaoJingYa/huawei-vr-compat/blob/03bf1012493fd821f38114010e4b21fe20f1d4f1/docs/FIRMWARE_HMA11_EMUI11.md)

在仓库根目录使用 Windows 自带的 `curl.exe`、Python 3.11 或更新版本、Java 和 Android SDK Build-Tools `36.0.0`。本次环境使用 JDK 27。脚本按清单获取固定版本的 JADX `1.5.7`，并在 PATH 中找到 `readelf` 时导出指定 ARM ELF 的架构、依赖和动态符号。如果 SDK 位于其他位置，可在 `inspect` 后加 `--android-sdk` 指定 SDK 根目录。[JADX 1.5.7](https://github.com/skylot/jadx/releases/tag/v1.5.7)

```powershell
python tools/inspect_samples.py fetch
python tools/inspect_samples.py inspect
```

下载物按实际字节比对 SHA-256，命中缓存时也重新核验。SDK 展开到 `.research/archives/`。每个 `.research/apk/<样本>/` 下有 ZIP 成员清单、原样解包的 `raw/`、Android Manifest、签名日志、JADX 输出和逐工具状态。JADX 使用 `--no-res`，二进制资源原样保存在 `raw/`，Manifest 由 AAPT 单独解码。这样可绕开社区基线记录的 SDK service 和系统服务重复资源项。JADX 返回部分反编译错误时，脚本保留 Java 输出，并把 APK 的 `classes*.dex` 用 `dexdump -d` 转储到同一样本的 `dexdump/`，供逐条核对。[社区解包偏差](https://github.com/EnYaoJingYa/huawei-vr-compat/blob/03bf1012493fd821f38114010e4b21fe20f1d4f1/docs/BASELINE.md#解码方式与偏差)

## APK 核验结果

八份 APK 均已解包，已核对文件 SHA-256，并通过 Android Build-Tools `apksigner` 的 v2 签名校验。下表 ABI 指 APK 标准 `lib/` 目录，证书仅显示 SHA-256 前 12 位。完整证书摘要可在各样本的 `signature.txt` 中复查。

| 样本 | 包名 | 版本 | min / target SDK | `lib/` ABI | 签名证书前缀 |
| --- | --- | --- | --- | --- | --- | --- |
| 华为 VR | `com.huawei.appmarket.vr` | `12.2.1.301` | 26 / 29 | `armeabi-v7a` | `a9436644e0bd` |
| 华为 VR 视频 | `com.huawei.himovie.vr` | `8.2.0.300` | 26 / 29 | `armeabi-v7a` | `186cffecf55f` |
| Unity SDK 内附 runtime | `com.huawei.hvrsdkserverapp` | `3.5.0.68` | 26 / 26 | `armeabi-v7a` | `1e3eee2a88a6` |
| 社区镜像 runtime | `com.huawei.hvrsdkserverapp` | `3.5.0.82` | 26 / 26 | `armeabi-v7a` | `1e3eee2a88a6` |
| 华为 VR 手柄 | `com.huawei.vrhandle` | `10.0.1.345` | 26 / 31 | `armeabi-v7a` | `6566026fa4e2` |
| 华为 VR 桌面 | `com.huawei.vrlauncherx` | `11.1.0.337` | 26 / 29 | `armeabi-v7a` | `fee6bf68c201` |
| VR 手机投屏 | `com.huawei.vrvirtualscreen` | `11.1.0.325` | 26 / 29 | `armeabi-v7a` | `124e5c23e2e4` |
| 华为 VR 系统服务 | `com.huawei.vrservice` | `11.0.0.322` | 28 / 28 | `arm64-v8a` | `603ac6a57e20` |

官方 `3.5.0.68` 和社区 `3.5.0.82` 的签名证书完整摘要相同。两个 runtime 均声明 `android.uid.system`，对外声明 `.service.ArvrRuntimeService`，并在 `assets/` 中带有 ARMv7 和 ARM64 的客户端库。用 Fold7 的 `ro.product.cpu.abilist` 和系统签名条件评估安装兼容性时，应以 APK 的实际装载 ABI、共享 UID 和权限要求为依据。华为也明确记载 SDK 3.5 依赖其手机系统层。[华为 SDK FAQ](https://developer.huawei.com/consumer/cn/doc/graphics-Guides/faq-0000001097358506/)

华为 VR、视频、手柄、桌面和手机投屏的部分 Java 方法仍有 JADX 转换错误。系统 `vrservice` 和两份 SDK runtime 的 Java 反编译完成，关键系统方法另用 DEX 指令交叉核对。所有原始 DEX 均可从解包目录复查。

## USB 插入、显示枚举与原厂路由

1. **USB 接入等待外显。** 在社区 `com.huawei.vrservice` `11.0.0.322` 的 `classes.dex` 中，`UsbReceiver.onReceive`（DEX `0xe304c`）处理 `USB_DEVICE_ATTACHED`，读取 VR 开关和机主用户条件，通过 `VRUtils.isHelmetDevice` 过滤，再启动 `VRService`。样本的正常接入路径匹配华为 `12d1:1092` 和相应产品名，固件升级状态另用 `12d1:1093`。`onStartCommand` 将事件交给 worker，`handleUsbChanged` 把正常接入交给 `handleGlassIn`（`0xe4058`），其中等待显示闩锁最多 5 秒。`VRService.onDisplayAdded`（`0xe4b10`）核对 `HUAWEI VR Display`，记录显示 ID 并释放闩锁。初始化后绑定 `com.huawei.vrlauncherx` 内的 `com.huawei.client.vrservice.VRService`，通过 Messenger `1001` 传递系统服务 Binder。桌面回调 `2202` 进入服务的头显准备路径。
2. **接近事件与屏幕开关走两条 VCOM 通道。** 上述 APK 的 `lib/arm64-v8a/libvrservice.so` SHA-256 为 `f00920a701a2781daac55b1e2f8dbcad20b12e0ac1eeea6004f7afd2f5f430d2`。`readGlassNodeNative`（ELF VA `0xbe88`）从 `/dev/ttyUSB1` 读取事件，经 JNI 回到 `VRDeviceNodeMonitor.analyzeVcomBuffer`。`processProximity` 把接近值 `1` 转成事件交给 `handleHelmetUp`（DEX `0xe4418`），只有需要初始化且尚未进入 VR 模式时才调用屏幕开启 JNI。`VRHelmetUtils_setVrScreenOnNative`（ELF VA `0xa04c`）经 `GetSimpleResultFromVcom`（`0x8e3c`）配置 `/dev/ttyUSB0`、写 `AT^SWITCHSCREEN=1` 并读回确认。关屏入口（`0xa238`）走同一命令通道。Fold7 的接口呈现和冷插是否依赖这条路径，仍需实测。
3. **外显先由 Android 注册。** 公开的 P40 HarmonyOS 2.0 开发版框架里，`DisplayManagerService` 在添加逻辑显示后把 `DisplayInfo` 交给 `setVrDisplayInfo`。`HwVrServiceManagerImpl` 查询名为 `vr_system` 的 Binder 服务，以 `3200×1600` 或旋转后的 `1600×3200` 识别 Halliday 显示。`LocalDisplayAdapter` 为匹配设备命名 `HUAWEI VR Display`。这些代码说明华为 VR 界面路由依赖显示枚举，手机和眼镜的 DP 协商发生在哪个固件步骤仍有待真机采证。[框架显示回调](https://github.com/dstmath/HWFramework/blob/672bb34094b8780806a10ba9b1d21036fd808b8e/P40_HarmonyOS_2.0.0_Developer_Beta1/src/main/java/com/android/server/display/DisplayManagerService.java#L891-L900) · [Binder 服务发现](https://github.com/dstmath/HWFramework/blob/672bb34094b8780806a10ba9b1d21036fd808b8e/P40_HarmonyOS_2.0.0_Developer_Beta1/src/main/java/android/vrsystem/HwVrServiceManagerImpl.java#L88-L97) · [外显尺寸匹配](https://github.com/dstmath/HWFramework/blob/672bb34094b8780806a10ba9b1d21036fd808b8e/P40_HarmonyOS_2.0.0_Developer_Beta1/src/main/java/android/vrsystem/HwVrServiceManagerImpl.java#L636-L646)
4. **头显 HID 提供独立的初始化和姿态路径。** 社区 `hvrsdkserverapp` `3.5.0.82` 的 `assets/arm64-v8a/libWalleDev.so` SHA-256 为 `edda15ad3494932873c600d28b36c571f276e3807ba3ab248b09484567affd15`。`openDev`（ELF VA `0x16584`）使用 `/dev/hwvr1`。`ioGetVendorInfo`、`ioActiveDev`、`ioDeactiveDev` 各有 HID ioctl 调用，读取循环以 `poll` 和 `read` 取数据。`Walle::onGlassSensorEvent`（`0x19574`）把 IMU 消息分派给 `processImuEvent`（`0x19098`），后者做轴变换和缩放后回调上层。库里还存在光学参数与偏移查询。社区记录的 `setLcdMode`、`setLowPersistence`、`getVsyncTimeStamp` 属于另一组平台显示 HAL 接口。Flip5 上的 HID 查询结果随固件有所差异，移植时应以实际端点和报告为准。[社区 HID 与显示 HAL 记录](https://github.com/EnYaoJingYa/huawei-vr-compat/blob/03bf1012493fd821f38114010e4b21fe20f1d4f1/docs/HELMET_HID_PROTOCOL.md) · [Flip5 HID 实测](https://github.com/EnYaoJingYa/huawei-vr-compat/blob/03bf1012493fd821f38114010e4b21fe20f1d4f1/docs/evidence/proximity-battery-2026-09-16.md)

上述 DEX 锚点可用 `dexdump -d .research/apk/com.huawei.vrservice/raw/classes.dex` 查看。原生锚点用 `readelf -W -l` 找到承载相应 ELF 虚拟地址的 `LOAD` 段，再用 AArch64 Capstone 5.0.7 或支持 AArch64 的 `llvm-objdump` 查看同一段指令。例如在 `libvrservice.so` 上使用 `llvm-objdump -d --start-address=0xa04c --stop-address=0xa238` 可复核开屏 JNI 到 VCOM helper 的调用。[Capstone 5.0.7](https://pypi.org/project/capstone/5.0.7/) · [LLVM objdump](https://llvm.org/docs/CommandGuide/llvm-objdump.html)

## OpenXR 与项目参照

| 项目 | 已有证据与用途 |
| --- | --- |
| HuaweiVRGlass-ALVR | 华为 LYA-AL00、HarmonyOS 4.2、CV10 和旧 Huawei runtime 上的实机串流。`hvrbridge.jar` 与 `LibUpdateClient` 说明客户端怎样从已安装的华为 SDK 服务装载 runtime。适合作为原厂应用入口、渲染方向和 ALVR 对照。[构建文档](https://github.com/LHT02/HuaweiVRGlass-ALVR/blob/a4e75760ababc10a6686f52585207c85253429a7/scripts/huawei/README.md) |
| huawei-vr-glass-globalka | 三星 SM-X806B、Android 16 上的系统外显和双眼渲染实测。`Presentation` 与可调眼别/方向是 Fold7 测试应用的参考。[实机记录](https://github.com/samrat1games/huawei-vr-glass-globalka/blob/266dbe02e115c7aeed936dedc2d1924ae375bc8c/docs/verification.md) |
| HuaweiVRGlass-ALVR-Android | OnePlus 7T 的自研 OpenXR shim、双目外显与姿态实验，依赖 Magisk 系统适配。可参考与 Fold7 不同的加载和设备接入实现，仓库的兼容性证据以作者测试设备为限。[固定版本](https://github.com/niceqwer55555/HuaweiVRGlass-ALVR-Android/tree/0a7cc2625db16732e38863a419d4aaeb2cdb1322) |
| huawei-vr-compat | 七包及华为平台接口台账，含 Flip5 实测和原厂调用锚点。可据此缩小 APK、HID、显示路由和 VCOM 的检索范围。[固定版本](https://github.com/EnYaoJingYa/huawei-vr-compat/tree/03bf1012493fd821f38114010e4b21fe20f1d4f1) |
| Monado 与 Android Runtime Broker | Monado 提供开放的 Android OpenXR runtime，Khronos Broker 提供 runtime 发现机制。Fold7 仍需验证 CV10 HID、外屏与帧提交。Google Android XR 的验收另用系统 runtime 和官方样例。[Monado](https://monado.freedesktop.org/) · [Khronos Broker](https://github.com/KhronosGroup/OpenXR-Android-Broker) · [Android XR OpenXR 要求](https://developer.android.com/develop/xr/openxr/get-started) |

### `huawei-vr-compat` 二次校验

本阶段用 `huawei-vr-compat` 的固定提交定位原包和分析线索，提交的解包脚本独立编写。USB 接入、显示等待、VCOM 和 HID 主链路均回到原始 DEX 或 ELF，以 `dexdump` 和 Capstone 的结果核对。社区报告里的设备现象以其测试机型和固件为限。[固定版本](https://github.com/EnYaoJingYa/huawei-vr-compat/tree/03bf1012493fd821f38114010e4b21fe20f1d4f1)

后续若考虑采用其中某段代码，先记录来源提交、文件、适用设备和使用许可。用原厂字节码、原生库或对应的平台接口文档核对实现，再在 Fold7 上按已知正常的基线独立复测该行为，记录现象与日志。两层证据齐备后再决定是否采用。
