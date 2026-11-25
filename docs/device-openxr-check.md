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
| 头显接口 | `107e` 有三个厂商接口和两个 HID 接口。接口 3，class 3/subclass 0/protocol 0，端点 `0x84` 为 interrupt IN，最大包长 512、间隔字段 1。接口 4 有独立 IN 端点 `0x85`。下午的后续采样结果见文末。 |
| SurfaceFlinger | `HUAWEIAV03`，HWV port 21，HWC 外显 ID 1，活动模式 **640×480、约 60 Hz**。 |
| DisplayManager | 此次逻辑 ID 16，可用于 `Presentation`，具有 DeX hosting 标志。模式 34 为 640×480，派生的模式 35 为 640×533，两者都标记 `FLAG_SIZE_OVERRIDE`，均约 60 Hz。DeX 的逻辑覆盖为 **1600×900**。重新插拔后应重新枚举 ID。 |
| DP 识别 | 可读的三星 `/sys/class/dp_sec/monitor_info` 返回 `HWV,0x300,0x1`。Fold7 的普通 ADB shell 读取 DRM 的 `card0-DP-1/edid` 和 `modes` 均返回权限不足。本轮未得到手机侧原始 EDID，无法判断读取、模式过滤或链路训练中的哪一步导致不同模式集合。 |

Windows 注册表先前缓存了同型号 `DISPLAY\HWV0003` 的 256 字节 EDID，名称为 HUAWEIAV03，SHA-256 为 `326e58b2d7c770af7d0006cd1932499904b26f6190639bf67e7b60f8838e3efb`。两个 128 字节块的字节和模 256 均为 0。基本块两条 DTD 均为 3200×1600，像素时钟分别为 529.94 MHz、412.18 MHz，计算帧率分别为 90.000、70.001 Hz。CTA 扩展含 1920×1080、60 Hz 的 DTD。该记录说明 PC 端曾读到的候选时序；手机本轮向应用公开的模式表没有对应的 3200×1600 条目。

### 同一接线切换三星扩展和镜像

13:38，在 Fold7 依次打开 **设置 → 已连接的设备 → Samsung DeX → 连接的显示设备**，原先选中“已扩展”，其分辨率设置页显示 HD+（1600×900）。在保持眼镜、线缆及供电不变时选择“已镜像”，5 秒后采得以下结果。后续从同一菜单选“已扩展”可恢复原模式。[三星 DeX 镜像说明](https://www.samsung.com/uk/apps/samsung-dex/)

| 指标 | 已扩展 | 已镜像 |
| --- | --- | --- |
| 高通显示 HAL 的物理配置数 | 1 | 2 |
| 显示、混合器尺寸 | 640×480 | **3200×1600** |
| 活动时序 | 约 60 Hz，像素时钟 25.175 MHz，总长 800×525 | **90 Hz**，像素时钟 529.94 MHz，总长 3308×1780；Android 也公布 70 Hz |
| Android 外显 | 独立 DeX 桌面，逻辑覆盖 1600×900 | 本次 ID 25，显示组 0，逻辑像素 3200×1600 |

镜像模式的活动时序与 PC 缓存的 90 Hz DTD 一致。该 A/B 实测将问题缩小到**三星显示模式对物理时序的选择**。高通 HWC 在扩展模式下只公布一个物理配置，普通应用更改逻辑窗口大小无法选用未公开的原生模式。镜片是否发光、画面是否正确属于独立的光学验收。硬件合成器原始快照为 `attached-composer.txt` 与 `mirror-composer.txt`。

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

13:39 在上面的 3200×1600 镜像模式再次复测。以普通 ADB 直接指定当时的外显 ID 25 启动官方样例，ActivityTaskManager 返回 `Permission Denial ... launchDisplayId=25`。随后从默认屏 0 正常启动样例，13:39:22 会话进入 FOCUSED，双目交换链仍各为 1764×1512，合成器输出仍为 1080×2418。WindowManager 明确记录 `mDisplayId=0`。SurfaceFlinger 同时在手机内屏和 `HUAWEIAV03` 的物理输出列表中列出同一个 `hello_xr` SurfaceView 图层（本次标识 `#979358`）。

**CV10 左眼镜片中的 OpenXR 镜像画面已经拍到。** 摄像头实拍可见灰底蓝色方块，和同轮外显截图中的 `hello_xr` 双目方块相符。此前左眼也拍到了独立显示探针的蓝底箭头。当前确认了手机运行应用、Monado 合成、Android 镜像、CV10 左眼实际出图的链路。右眼光学画面、两眼方向和畸变，头显自身的 3DoF，以及 Monado 直接面向 CV10 的输出仍待验证。测试后保留“已镜像”以便复测。对应系统记录见本机 `.research/openxr-android/hello-mirrored*`。

## 头显 HID 输入

13:45，用普通 Android USB Host API 访问 `12d1:107e` 的接口 3，读取到与社区同款实机记录一致的 68 字节 HID 描述符。中断 IN 端点为 `0x84`。程序仅在这一接口被内核占用时临时 claim，结束后释放。两次独立运行的结果如下。

| 采样阶段 | 第一次 | 第二次 |
| --- | ---: | ---: |
| 激活前的 1.5 秒 | 0 帧 | 0 帧 |
| 发原厂传感器启用报告后的 1.5 秒 | 1177 帧 | 1188 帧 |
| 每帧实际字节数 / 首字节 | 60 / 0x01 | 60 / 0x01 |
| 首末报告间的主机接收频率 | 1000.1 Hz | 1000.1 Hz |

窄掩码 `02` 来自原厂 `Wallex::onSartGlass`。头显固件的普通 SET_REPORT 接收分支按负载首字节分派。试验实际发送 `05 02 00 00 00`，收完后以 `06 02 00 00 00` 关闭；两次启用、两次关闭都返回传输 5 字节。采样窗口包括开始出帧前的等待，按整窗计算分别为约 785、792 帧/秒。这里验证的是眼镜自己的传感器报告传输；轴、单位、时钟、姿态融合与 Monado 驱动接入仍待验证。手机测试应用中选择「采样头显 HID 输入」即可复测。[采样实现](../probe/HeadsetInput.java)
