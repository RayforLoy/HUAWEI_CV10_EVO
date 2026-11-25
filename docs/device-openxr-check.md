# Fold7、P40 Pro+ 与 CV10 真机记录

2026-11-25，香港时间。用户确认 P40 Pro+ 普通 C-C 直连可见画面，Windows 上 HiSuite、NOLO Home、SteamVR 的 C-C 接法也能出图。P40 Pro+ 换原厂连接线后能识别 VR，镜片黑屏。以下 Fold7 记录来自普通 C-C 直连。

## 两台手机与无线调试

| 设备 | 实测系统与 ABI | 无线调试 |
| --- | --- | --- |
| P40 Pro+，ELS-AN10 | 系统版本 4.2.0.121(C00E121R6P3)，兼容接口报告 Android 12 / API 31，支持 ARM64、ARMv7 | `cmd adb is-wifi-supported` 与 `is-wifi-qr-supported` 均为 true，`adb_wifi_enabled=0`。实机 Settings 主 APK 的开发者设置 XML 可找到 `enable_adb` 与 `clear_adb_keys`，未找到无线 ADB 条目。基础服务报告支持，华为此版设置界面是否有动态或其他入口仍未证实。 |
| Galaxy Z Fold7，SM-F9660 | Android 16 / API 36，构建 BP4A.251205.006.F9660ZCSCBZI1，仅 arm64-v8a | 两项能力均为 true，`adb_wifi_enabled=1`。从已获授权的电脑通过 TLS 无线 transport 成功执行 shell，并在拔下电脑 USB 后继续采集。 |

电脑运行的 ADB 客户端和服务端均来自同一套 Platform Tools 37.0.3。Fold7 的 mDNS 同时列出同一地址的两个 `_adb-tls-connect._tcp` 端点。一项在短 TCP 探测中超时，另一项可达。对可达端点运行 `adb connect` 成功，再以该无线序列号读取型号得到 `SM-F9660`。本轮无需重新配对。原始报错发生时使用的命令和端口未知，无法断定历史错误成因。重连时用本次无线调试页面显示的连接端口；仅对屏幕上的配对端口使用 `adb pair`。[Android 的无线 ADB 说明](https://developer.android.com/tools/adb#wireless)

P40 实机的 `com.huawei.vrservice` 为 **13.0.0.300**，系统分区路径为 `/hw_product/region_comm/china/app/VRServiceX/VRServiceX.apk`。资源目录中的 07 号包是 12.0.0.302。其余六个已安装包报告的版本号均与资源 01–06 相符，版本号比对未涉及已安装包的逐字节校验。

## Fold7 普通 C-C 直连

13:23:22 插入。系统显示服务在约 0.2 秒后把外屏切到 ON，用户确认该轮**镜片黑屏**。USB 和显示捕获同时完成。

| 层级 | 本轮证据 |
| --- | --- |
| USB 主机 | `12d1:1092` 为 HUAWEI GLASS CV10，带音频及 HID；`12d1:107e` 为 HUAWEI GLASS HID。二者 USB 描述符版本字段均为 2.00。 |
| 头显接口 | `107e` 有三个厂商接口和两个 HID 接口。接口 3，class 3/subclass 0/protocol 0，端点 `0x84` 为 interrupt IN，最大包长 512、间隔字段 1。接口 4 有独立 IN 端点 `0x85`。本轮尚未采样 IMU 报告。 |
| SurfaceFlinger | `HUAWEIAV03`，HWV port 21，HWC 外显 ID 1，活动模式 **640×480、约 60 Hz**。 |
| DisplayManager | 此次逻辑 ID 16，可用于 `Presentation`，具有 DeX hosting 标志。模式 34 为 640×480，派生的模式 35 为 640×533，两者都标记 `FLAG_SIZE_OVERRIDE`，均约 60 Hz。DeX 的逻辑覆盖为 **1600×900**。重新插拔后应重新枚举 ID。 |
| DP 识别 | 可读的三星 `/sys/class/dp_sec/monitor_info` 返回 `HWV,0x300,0x1`。Fold7 的普通 ADB shell 读取 DRM 的 `card0-DP-1/edid` 和 `modes` 均返回权限不足。本轮未得到手机侧原始 EDID，无法判断读取、模式过滤或链路训练中的哪一步导致不同模式集合。 |

Windows 注册表先前缓存了同型号 `DISPLAY\HWV0003` 的 256 字节 EDID，名称为 HUAWEIAV03，SHA-256 为 `326e58b2d7c770af7d0006cd1932499904b26f6190639bf67e7b60f8838e3efb`。两个 128 字节块的字节和模 256 均为 0。基本块两条 DTD 均为 3200×1600，像素时钟分别为 529.94 MHz、412.18 MHz，计算帧率分别为 90.000、70.001 Hz。CTA 扩展含 1920×1080、60 Hz 的 DTD。该记录说明 PC 端曾读到的候选时序；手机本轮向应用公开的模式表没有对应的 3200×1600 条目。

完整的设备快照与 Windows EDID 在本机 `.research/device/2026-11-25-fold7/`。复查时将下列变量改为本次实际值。

```powershell
$Fold = '手机无线地址:当前连接端口'
adb -s $Fold shell dumpsys display
adb -s $Fold shell dumpsys SurfaceFlinger --display-id
adb -s $Fold shell dumpsys usb
adb -s $Fold shell cat /sys/class/dp_sec/monitor_info
```

## OpenXR 运行时

Fold7 暴露 `android.hardware.usb.host` 和 Vulkan 能力。系统和可安装版 Khronos Android runtime broker 的 ContentProvider 查询均返回找不到 provider。对 `/product/etc/openxr`、`/system/etc/openxr`、`/vendor/etc/openxr` 和 `/odm/etc/openxr` 的查询也均返回目录不存在。OpenXR 应用仍需一个能驱动 CV10、能向外屏提交画面的运行时。[Khronos Android Runtime Broker](https://github.com/KhronosGroup/OpenXR-Android-Broker)

13:26 用 Khronos 官方 OpenGLES `hello_xr` 1.1.65 在 Fold7 上实测。APK 的 SHA-256 为 `29ae01ef6a4fea41d67816f7051698f2694ab08ced4c16c02bdd978e62975962`，与官方发布资产的摘要相同，APK 签名验证通过。日志显示已进入 `xrInitializeLoaderKHR`；随后 `xrEnumerateInstanceExtensionProperties` 查询两个 Broker 均得到空 cursor，loader 未找到活动运行时，样例返回 **`XR_ERROR_RUNTIME_UNAVAILABLE`**。该次执行停在创建实例之前。样例已保留在 Fold7 上，可在安装运行时后用同一包复测。[Khronos OpenXR SDK 1.1.65 官方发布](https://github.com/KhronosGroup/OpenXR-SDK-Source/releases/tag/release-1.1.65)

```powershell
adb -s $Fold shell am start --display 0 -n org.khronos.openxr.hello_xr.opengles/android.app.NativeActivity
adb -s $Fold logcat -d -s OpenXR-Loader:V hello_xr:V
```

### 安装 Monado 后复测

13:29，将 Khronos OpenXR Runtime Broker 1.0.0 与 Monado 官方 Android CI 的独立运行时安装到同一部 Fold7，在 Broker 的 Installed Runtimes 中选中 **Monado XR**。没有授予相机、悬浮窗等额外权限。两个 APK 的 SHA-256 分别为 `010e67bdd196ab156e0d4a689c9ba5a65b927526a5f1f57319548e64ff495330` 和 `df1158af4edf59d5fc41267d1488fd7b03460cdb5f2f0845d67e52a378cf827b`。[Khronos Broker](https://github.com/KhronosGroup/OpenXR-Android-Broker) · [Monado 源码与 CI](https://gitlab.freedesktop.org/monado/monado)

| 检查点 | 同一份 OpenGLES `hello_xr` 实际结果 |
| --- | --- |
| 发现与加载 | Khronos loader 经 Broker 找到 `libopenxr_monado.so`，协商 OpenXR API 1.1，`xrCreateInstance` 成功。运行时返回 Monado(XRT) 25.1.0，构建 `v25.1.0-1183-gce2b721eb`。 |
| 会话与双目交换链 | 两眼分别创建 1764×1512 的颜色与深度交换链；会话依次进入 READY、SYNCHRONIZED、VISIBLE、**FOCUSED**。 |
| 追踪来源 | `xrGetSystemProperties` 报告 `Monado: Android Sensors`、方向追踪 true、位置追踪 false。校准文件缺失时，日志记录采用 Cardboard V1 的默认光学参数。该次样例使用手机传感器，CV10 的 USB HID 与光学标定仍需接入。 |
| 实际输出 | 启动目标为默认屏 0。实测当时 SurfaceFlinger 只列出手机内置屏；合成器 Vulkan 输出交换链为 1080×2418。CV10 镜片上的 OpenXR 双目画面仍待验证。 |

本地日志保存在 `.research/openxr-android/hello-monado.log`。复测后已恢复显示测试应用，手机上保留 Broker、选中的 Monado 运行时及官方样例。
