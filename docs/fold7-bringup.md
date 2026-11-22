# Galaxy Z Fold7 点亮 HUAWEI VR Glass CV10

本手册供下一阶段接入真机时使用。当前依据来自厂商文档、公开实机记录和离线分析，Fold7 与 CV10 的组合仍待实测。首个硬件目标是在三星原厂系统上，从 CV10 两个镜片中看到由 Fold7 输出的可辨认图案，并记录可重复的启动条件。

## 公开证据

| 项目 | 已有证据 | 对 Fold7 的意义 |
| --- | --- | --- |
| 手机线与供电 | CV10 无电池，原装手机线由主机供电，也可从其 USB-C 供电口接 5 V/2 A 电源。华为兼容清单包含 P40 Pro+ `ELS-AN10` 和 `ELS-TN10`。 | 用 P40 Pro+ 验证同一副眼镜和同一根手机线。将有无辅助供电视为两个独立配置。[华为供电说明](https://consumer.huawei.com/cn/support/content/zh-cn00757290/) · [华为兼容清单](https://consumer.huawei.com/cn/support/content/zh-cn00757272/) |
| Fold7 有线外屏 | 三星为 Fold7 列出有线 DeX。 | 先用已知可用的普通显示器验证手机有线视频输出。CV10 的模式协商和面板出图仍须单独测试。[三星 Fold7 规格](https://www.samsung.com/us/business/mobile/phones/galaxy-z-fold7/) |
| 三星平板外屏 | Globalka 作者在三星 `SM-X806B`、Android 16 上记录到 `HUAWEIAV03`、3200×1600、`FLAG_PRESENTATION` 和系统镜像。同一项目报告用 `Presentation` 输出自绘画面，并通过镜片确认左右眼需要不同方向。 | 以公开 Android 外屏 API 开始。记录 Fold7 实际报告的显示 ID、模式和两眼方向。[实机记录](https://github.com/samrat1games/huawei-vr-glass-globalka/blob/266dbe02e115c7aeed936dedc2d1924ae375bc8c/docs/verification.md) · [渲染实现](https://github.com/samrat1games/huawei-vr-glass-globalka/blob/266dbe02e115c7aeed936dedc2d1924ae375bc8c/app/src/main/java/org/vrglass/bridge/VrSceneRenderer.java) |
| PC 画面和 EDID | 华为给出 Windows 扩展桌面流程，有公开 Windows 10 用户实测 3200×1600 @ 90 Hz 出图。同一实验中的 Jetson 读到模式但冷启动黑屏。 | 分别记录显示器枚举、活动模式、镜片里实际看到的内容。[华为 PC 文档](https://consumer.huawei.com/cn/support/content/zh-cn00757271/) · [公开实测](https://forums.developer.nvidia.com/t/display-to-huawei-vr-glasses/169464) |
| USB 和 IMU | 公开 Jetson 枚举记录含 `12d1:1092` 和 `12d1:107e`。兼容项目在三星 Flip5 与 `CV10AC 10.0.1.357` 的组合上从 `107e` 取得带 ID 的 60 字节输入报告，约 160 Hz。 | 识别符和报告长度用作排查线索。记录本机实际枚举和固件，不按已有报告假定追踪或面板状态。[公开 USB 日志](https://forums.developer.nvidia.com/uploads/short-url/hkC4xAQ6gSqSanU18vHo3mrK2Kz.txt) · [Flip5 实测](https://github.com/EnYaoJingYa/huawei-vr-compat/blob/03bf1012493fd821f38114010e4b21fe20f1d4f1/docs/evidence/proximity-battery-2026-09-16.md) |

## 首轮连接顺序

每轮记录主机型号和系统版本、眼镜固件（可读时）、线缆型号和接法、辅助电源、接近传感器状态、屏幕模式以及插拔时间。冷插前从眼镜链路断开主机和辅助电源，再按同一顺序接线。保留首次自动响应，再操作 DeX 或 PCVR 助手。每次只调整一个条件。首轮保持 Fold7 原厂系统，使用系统镜像、DeX 和普通应用接口。

1. **P40 Pro+ 原厂对照。** 先在现有可用系统上解锁手机，连接 CV10 原装手机线，戴上眼镜或用手指遮住接近传感器，观察原厂界面。记下两眼画面和拔插恢复。检查辅助供电时，用原线的供电口接 5 V/2 A 电源，把供电配置独立记录。如果原厂对照失败，先核对线缆和眼镜，在恢复已知正常的基线后再用它判断 Fold7。[华为兼容清单](https://consumer.huawei.com/cn/support/content/zh-cn00757272/) · [华为供电说明](https://consumer.huawei.com/cn/support/content/zh-cn00757290/)
2. **Fold7 普通显示器对照。** 解锁 Fold7，用已知可用的有线外屏接法，实测镜像或有线 DeX，记录实际可见画面。优先用已知可工作的 USB-C DP Alt Mode 显示器或 USB-C 转 DP 路径，便于核对后续 CV10 的有线视频路径。记录使用的线材和转接器。[三星有线 DeX 说明](https://www.samsung.com/us/business/mobile/phones/galaxy-z-fold7/) · [VESA DP Alt Mode](https://vesa.org/dp-usb-type-c/)
3. **Fold7 与 CV10。** 用 P40 Pro+ 验过的原装手机线直接连接 Fold7，接近传感器保持触发。先观察系统自动镜像或桌面画面并抓取日志，再在系统提供切换入口时单独测试有线 DeX。单独冷插重测接有 5 V/2 A 辅助电源的配置，记录加电顺序以及活动模式。首轮以直连为准，通用集线器的 USB-C 口是否转发视频须以其规格和实测为准。[华为供电说明](https://consumer.huawei.com/cn/support/content/zh-cn00757290/) · [VESA DP Alt Mode](https://vesa.org/dp-usb-type-c/)
4. **Windows PC 对照。** Belkin `CAZ001` 的 DP 接独立显卡，两个 USB-A 都接电脑 USB 3.0 口，USB-C 接 CV10。若用官方文档列出的 FIBBR 线，将 `SOURCE` 接有视频输出的 PC USB-C，将 `DISPLAY` 接眼镜。华为的 Belkin 接法要求原生 DP 路径，HDMI 转 DP 不在其支持范围。解锁电脑并触发接近传感器，尝试 Windows 扩展屏，核对高级显示设置里的活动信号模式和刷新率。华为记载扩展桌面可呈 90°旋转。若冷插黑屏，再按官方说明查 NVIDIA 直连模式，在单独一轮记录 PCVR 助手切换前后差异。记录 Windows、GPU 驱动和助手版本。[华为 PC 接线](https://consumer.huawei.com/cn/support/content/zh-cn00757271/) · [直连与扩展模式](https://consumer.huawei.com/cn/support/content/zh-cn15856460/) · [Belkin 线缆规格](https://www.belkin.com/sg/support-article/?articleNum=316883)

PC 上可读取当前呈现给 Windows 的监视器和华为 USB 设备。直连模式下 Windows 可能隐藏 CV10 的监视器条目。设备管理器条目也可能只显示某个复合 USB 接口，因此同时保留高级显示设置和镜片观察结果。[华为直连模式说明](https://consumer.huawei.com/cn/support/content/zh-cn15856460/)

```powershell
Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorID |
    ForEach-Object {
        [pscustomobject]@{
            Name = -join ($_.UserFriendlyName | Where-Object { $_ -ne 0 } | ForEach-Object { [char]$_ })
            Active = $_.Active
            InstanceName = $_.InstanceName
        }
    }

Get-PnpDevice -PresentOnly |
    Where-Object { $_.InstanceId -match 'VID_12D1&PID_' } |
    Select-Object Status, Class, FriendlyName, InstanceId
```

## 安卓无线采集

在 Fold7 上启用开发者选项及无线调试，手机和 PC 接入同一网络。无线调试页面上分别读取配对端点和用于连接的端点，两处端口可能不同。替换示例端点，配对码通过终端交互输入。连接后用 `adb devices -l` 确认状态为 `device`，从列表复制完整序列标识。P40 Pro+ 如提供同样的无线调试入口，可沿用此流程。也可直接记录 P40 Pro+ 的系统界面、版本和镜片观察结果。[Android 无线 ADB](https://developer.android.com/tools/adb#wireless)

```powershell
adb pair 192.0.2.10:41835
adb connect 192.0.2.10:37123
adb devices -l
```

以下 PowerShell 示例在本机临时目录按轮次保存完整快照。把 `$Cv10Device` 改为设备列表中的序列标识，并为每次冷插修改 `$Cv10Round`。使用设备时钟的标记获取本轮 logcat，保留插入、显示模式变化和拔出三个时点。[Android adb 命令](https://developer.android.com/tools/adb) · [Android logcat](https://developer.android.com/tools/logcat)

```powershell
$Cv10Device = '192.0.2.10:37123'
$Cv10Round = 'fold7-direct-cold01'
$Cv10Capture = Join-Path $env:TEMP ('cv10-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + $Cv10Round)
New-Item -ItemType Directory -Path $Cv10Capture -ErrorAction Stop | Out-Null

function Save-Cv10Snapshot([string]$Phase) {
    Get-Date -Format o | Set-Content -Encoding utf8 (Join-Path $Cv10Capture "$Phase.pc-time.txt")
    adb -s $Cv10Device shell dumpsys display | Set-Content -Encoding utf8 (Join-Path $Cv10Capture "$Phase.display.txt")
    adb -s $Cv10Device shell dumpsys usb | Set-Content -Encoding utf8 (Join-Path $Cv10Capture "$Phase.usb.txt")
}

adb -s $Cv10Device shell getprop ro.product.model | Set-Content -Encoding utf8 (Join-Path $Cv10Capture 'model.txt')
adb -s $Cv10Device shell getprop ro.build.fingerprint | Set-Content -Encoding utf8 (Join-Path $Cv10Capture 'build.txt')
adb -s $Cv10Device shell getprop ro.product.cpu.abilist | Set-Content -Encoding utf8 (Join-Path $Cv10Capture 'abis.txt')
$Cv10StartRaw = adb -s $Cv10Device shell date '+%s'
if ($LASTEXITCODE -ne 0 -or -not $Cv10StartRaw) { throw 'Could not read the device clock.' }
$Cv10Start = $Cv10StartRaw.Trim() + '.000'
Save-Cv10Snapshot 'before'

# Connect the glasses and activate the proximity sensor.
Save-Cv10Snapshot 'connected'

# If switching from mirroring to DeX, capture each mode with its own phase name.
# Save-Cv10Snapshot 'dex'

# Disconnect the glasses and the auxiliary supply.
Save-Cv10Snapshot 'disconnected'
adb -s $Cv10Device logcat -d -b all -v threadtime -T $Cv10Start '*:V' |
    Set-Content -Encoding utf8 (Join-Path $Cv10Capture 'logcat.txt')
$Cv10Capture
```

把示例分段执行，在注释对应的位置完成接线和拔线。出现短暂黑屏或反复重连时，保留完整日志，用 `HUAWEIAV03`、`DisplayManager`、`SurfaceFlinger`、`UsbHostManager`、`107e` 和 `1092` 在副本中定位。若 USB 字段使用十进制，检查厂商 ID `4817` 和产品 ID `4222`、`4242`。保存系统可见的接口类、子类、协议和端点，分别与 P40 Pro+ 的串口及 HID 枚举对照。`dumpsys display` 优先查看物理显示器、活动 mode 和系统报告的支持 mode。记录观察结果及其时点，系统截图另注明为帧缓冲画面。

## 镜片验收和下一阶段的测试应用

开始真机阶段后，先用系统镜像做手动对照。在手机打开带明显方向的图案，验证眼镜内各镜片是否有清楚的可见画面，并记录裁切、旋转和花屏情况。系统镜像通常会给两个面板分配同一整帧的两半，镜片中能看清镜像说明视频链路可以工作。独立左右眼内容由测试应用验证。

测试应用最小规格如下。[Android `DisplayManager`](https://developer.android.com/reference/android/hardware/display/DisplayManager) · [Android `Presentation`](https://developer.android.com/reference/android/app/Presentation) · [窗口首选显示模式](https://developer.android.com/reference/android/view/WindowManager.LayoutParams#preferredDisplayModeId) · [Globalka 左右眼实现](https://github.com/samrat1games/huawei-vr-glass-globalka/blob/266dbe02e115c7aeed936dedc2d1924ae375bc8c/app/src/main/java/org/vrglass/bridge/VrSceneRenderer.java)

- 用 `DisplayManager.getDisplays(DISPLAY_CATEGORY_PRESENTATION)` 枚举，显示名称、ID、当前 mode 及支持的分辨率和刷新率。由操作者确认 CV10，再使用 `Presentation` 在目标屏显示。监听热插拔，移除后关闭旧窗口，新 ID 出现时重建。
- 一帧分成左右两个半幅，分别显示不同颜色、`L`、`R` 和向上箭头。全幅 3200×1600 时每半幅为 1600×1600。将每只眼的方向做成可调，优先尝试公开实机确认的相差 180°的配对，透过镜片核对图案朝向和眼别。
- 首次采用系统默认 mode。可在系统已报告的模式里请求 3200×1600 @ 70 Hz 或 90 Hz，用当前 mode 及 `dumpsys display` 核查实际结果。发生 `InvalidDisplayException` 或系统拒绝目标屏时，保存异常和热插拔记录。
- 选定一种 Fold7 配置后，在同一系统版本、线缆、供电和显示方式下做**三次独立冷插**。每轮通过要求是两只眼都能看清各自标记和向上箭头，持续观察期间画面稳定，且外屏活动模式已记录。结果写成 `3/3` 或实际通过次数，并记录每次未通过的环节。

建议每轮记录一行，可用 `有`、`无`、`未测` 描述枚举和观测状态。

| 轮次 | 主机与系统 | 线缆与供电 | 模式 | 外屏名、ID 和活动 mode | USB VID:PID | 左眼 | 右眼 | 结果与日志目录 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `fold7-direct-cold01` | 待填 | 待填 | 镜像、DeX 或 Presentation | 待填 | 待填 | 待填 | 待填 | 待填 |
| `fold7-direct-cold02` | 待填 | 待填 | 同上 | 待填 | 待填 | 待填 | 待填 | 待填 |
| `fold7-direct-cold03` | 待填 | 待填 | 同上 | 待填 | 待填 | 待填 | 待填 | 待填 |

## 根据观测定位下一步

公开的 `HUAWEIAV03` EDID 样本包含 3200×1600 @ 70 Hz 和 @ 90 Hz 的详细时序，像素时钟分别为 412.18 MHz 和 529.94 MHz。样本解码后的 256 字节二进制 SHA-256 为 `326e58b2d7c770af7d0006cd1932499904b26f6190639bf67e7b60f8838e3efb`。时序代表这台 CV10 宣告的模式，Fold7 实际选择的 mode 由本机快照确认。[公开 EDID 原始样本](https://forums.developer.nvidia.com/uploads/short-url/niUx4PoQcZ5L7nC2VMREqYcIvN3.txt) · [公开显示实验](https://forums.developer.nvidia.com/t/display-to-huawei-vr-glasses/169464)

| 观测 | 下一步 |
| --- | --- |
| 外屏与 USB 都无记录 | 先确认 P40 Pro+ 原厂对照和 Fold7 普通显示器对照。恢复已知可用的原装接线后，用 5 V/2 A 供电配置独立冷插，比较枚举和系统提示。 |
| 有 `107e` 或 `1092`，无外屏 | USB 枚举已成立。继续查 Fold7 有线外屏基线、DP Alt Mode、线缆和活动显示模式。VESA 允许 DP 使用四条高速通道并保留 USB 2.0，Fold7 的实际通道配置需实测。[VESA USB-C 上的 DisplayPort](https://vesa.org/featured-articles/vesa-brings-displayport-to-new-usb-type-c-connector/) |
| 有 `HUAWEIAV03`，镜片黑屏 | 触发接近传感器，确认外屏处于活动状态，独立测试辅助供电、镜像、DeX 和系统报告的不同 mode。在 PC 对照中另查驱动直连模式。公开 Jetson 实验发生过 EDID 可读而冷插黑屏。[公开实测](https://forums.developer.nvidia.com/t/display-to-huawei-vr-glasses/169464) · [华为 PC 模式说明](https://consumer.huawei.com/cn/support/content/zh-cn15856460/) |
| 系统镜像可见，应用外屏不可见 | 检查目标屏是否在 `DISPLAY_CATEGORY_PRESENTATION` 中，比较插拔前后 ID，保留应用异常及系统状态。若 DeX 占用目标屏，回到镜像条件复测应用可见性。[Android `Presentation`](https://developer.android.com/reference/android/app/Presentation) |
| 两眼可见，方向或眼别错误 | 用不同颜色、箭头和字母校正每只眼。面板方向按镜片观察记录，截图用于记录系统输出的原始帧。[Globalka 实机记录](https://github.com/samrat1games/huawei-vr-glass-globalka/blob/266dbe02e115c7aeed936dedc2d1924ae375bc8c/docs/verification.md) |
| 画面正常，USB 或 IMU 仍无数据 | 保留点亮结果，进入单独的追踪排查。比较 USB 接口、权限、报告 ID、长度、时间轴和眼镜固件。已有项目记录的报告长度随固件变化。[Android USB Host API](https://developer.android.com/develop/connectivity/usb/host) · [CV10 HID 静态记录](https://github.com/EnYaoJingYa/huawei-vr-compat/blob/03bf1012493fd821f38114010e4b21fe20f1d4f1/docs/HELMET_HID_PROTOCOL.md) · [Flip5 实测](https://github.com/EnYaoJingYa/huawei-vr-compat/blob/03bf1012493fd821f38114010e4b21fe20f1d4f1/docs/evidence/proximity-battery-2026-09-16.md) |

原厂 `vrservice` 样本的静态分析确认，Java 的 `handleHelmetUp` 有条件地调用屏幕开关 JNI。`setVrScreenOnNative` 经 `GetSimpleResultFromVcom` 访问 `/dev/ttyUSB0`，属于华为 VCOM 串口屏幕控制路径。`libWalleDev.so` 中的 HID 激活和 IMU 读取属于另一条路径。USB 枚举、DP 出图、VCOM 屏幕控制和 HID 姿态各自记录，Fold7 对 VCOM 的呈现及其冷插点亮是否需要该命令仍待验证。首轮在原厂系统上采集枚举、可读取的描述符、系统状态和镜片观察结果。[项目 APK 离线分析](apk-research.md) · [HID 离线分析](https://github.com/EnYaoJingYa/huawei-vr-compat/blob/03bf1012493fd821f38114010e4b21fe20f1d4f1/docs/HELMET_HID_PROTOCOL.md) · [社区串口和 HID 记录](https://github.com/EnYaoJingYa/huawei-vr-compat/blob/03bf1012493fd821f38114010e4b21fe20f1d4f1/docs/evidence/proximity-battery-2026-09-16.md)

## 从显示走到 OpenXR 和 Android XR

1. **CV10 头部姿态。** 点亮通过后，在手机固定时旋转 CV10，用有时间戳的样本验证眼镜自身的三轴旋转、坐标方向和断线恢复。之后再处理双眼光学参数、镜片畸变和渲染时序。公开 Flip5 报告可用作候选协议的交叉对照。[Flip5 HID 实测](https://github.com/EnYaoJingYa/huawei-vr-compat/blob/03bf1012493fd821f38114010e4b21fe20f1d4f1/docs/evidence/proximity-battery-2026-09-16.md)
2. **Monado 上的 OpenXR 兼容。** Monado 官方资料列出了 Android 手机内置 IMU 路径，CV10 专用驱动和向外屏提交画面的路径仍需实现和验证。以一个独立的 OpenXR 应用如 Khronos `hello_xr` 为验收。记录加载到的 runtime、`xrGetSystem` 和 `xrCreateSession` 结果，确认 CV10 两眼显示 OpenXR 提交的帧并随眼镜转动更新。[Monado 官方文档](https://monado.freedesktop.org/) · [Khronos `hello_xr` 构建文档](https://github.com/KhronosGroup/OpenXR-SDK-Source/blob/main/BUILDING.md#running-the-hello_xr-sample)
3. **Google Android XR。** 在 Fold7 原厂系统上记录 `adb shell pm list features` 返回的 `android.software.xr.api.openxr` 和 `android.software.xr.api.spatial` 项，并核对实际运行时来源。验收要求在目标设备上使用 Google Android XR 平台的运行时启动对应的官方 OpenXR 或 Jetpack XR 示例，建立设备支持的沉浸会话并在 CV10 镜片中看到画面。Google 公布的首款有线 Android XR 眼镜 XREAL AURA 使用专用计算单元，Fold7 与 CV10 的 Android XR 集成仍待平台证据。Monado 的结果记录为 OpenXR 兼容性里程碑。[Android XR OpenXR](https://developer.android.com/develop/xr/openxr/get-started) · [Android XR 设备特性](https://developer.android.com/develop/xr/package-and-distribute) · [Google 有线 Android XR 公告](https://developer.android.com/blog/posts/build-android-xr-devices-tools)
