# 六个华为 VR 历史 APK 与原厂线插入流程

2026-11-26。按 P40 本地资料的 01 至 06 编号，取得了六个不同包名的 Android 安装包。四项早于本机已有版本，两项采用与 P40 资料逐字节相同的公开样本。它们来自不同年份，尚无六个首发版本同时配套的证据。原始 APK 保存在本机 `.research/legacy-vr/verified-six/`。清单为每个包记录了文件名、字节数、SHA-256、签名指纹、来源和 REA 证据 ID。六个 APK 都通过 Android SDK `apksigner verify`，并用 REA 6.7.0 的 JADX 0.7.1 提供程序读取了 Manifest。[六个样本的可复核清单](../../research/evidence/cv10-legacy-apks-20261126.json)

| 编号和应用 | 实际取得的版本 | 历史版本证据与限制 |
| --- | --- | --- |
| 01 华为 VR SDK 服务端 | 3.5.0.68 | 华为开发者站 2021 年 Unity SDK 压缩包内的独立 APK。旧版官方教程以 HVR SDK 3.0.0.17 为最低开发版本，尚未取得可核验的该版服务端 APK。[华为下载来源](https://developer.huawei.com/consumer/cn/doc/graphics-Library/unity-sdk-download-0000001142315529/) · [旧版 Codelab](https://developer.huawei.com/consumer/cn/codelab/HUAWEI-VR-SDK/index.html) |
| 02 华为 VR 应用市场 | 12.2.1.301 | 与 P40 资料相同。2019-06-28 有同包名 9.0.0.301 的归档条目，普通 Chrome 访问本次返回 403。该版只有网站公布的指纹，未纳入本地样本。[历史条目](https://www.apkmirror.com/apk/huawei/huawei-vr/huawei-vr-9-0-0-301-release/huawei-vr-9-0-0-301-android-apk-download/) · [已取得的公开样本](https://github.com/EnYaoJingYa/huawei-vr-compat/tree/03bf1012493fd821f38114010e4b21fe20f1d4f1) |
| 03 华为 VR 视频 | 8.0.4.303 | 2019-12-27 的下载页取到实包。更早的 8.0.3.302 在 2019 年 11 月已有归档，本轮未取到该版文件。8.0.4.303 的签名与本机 8.2.0.300 的签名不同。[归档来源](https://m.jb51.net/softs/656057.html) |
| 04 华为 VR 手柄 | 10.0.0.374 | 明确包含 CV10 原厂线型号和升级实现。APK 的签名与本机 10.0.1.345 相同。2021-03-31 的公开目录已列此版本，首发构建号未确定。[下载来源](https://www.ddooo.com/softdown/160818.htm) · [历史目录](https://www.itmop.com/key/huawei/) |
| 05 华为 VR 桌面 | 11.1.0.337 | 与 P40 资料相同。标作 2019 年桌面 10.0.0.325 的下载，其 MD5 与网页相符，实解为前代 `com.huawei.vrlauncher` 1.2.0；CV10 的包名为 `com.huawei.vrlauncherx`。[标注有误的条目](https://www.aiskycn.com/az/1154972.html) · [华为列出的桌面版本](https://consumer.huawei.com/cn/support/content/zh-cn00776811/) |
| 06 VR 手机投屏 | 9.1.0.301 | 2019-06-24 下载条目列 Mate 10、P20 等机型，早于 CV10 上市。该包和 P40 参考版包名一致，证书不同，仅作前代协议对照。[下载来源](https://m.itmop.com/downinfo/342662.html) |

第七项系统 VR 服务单独保存为 `.research/legacy-vr/service/VRServiceX-11.0.0.322.apk`，SHA-256 为 `317c09957c6bf35edc9f4bca258a7aedbb81cebedfd212244f2776e82491f41e`，与本地 12.0.0.302 的证书不同。华为的排障页面把其中五个用户应用列为连接所需软件；SDK 和系统服务在本项目单独编号。此批样本用于静态分析，未装入 P40 或 Fold7。[EMUI 11 分区提取记录](https://github.com/EnYaoJingYa/huawei-vr-compat/blob/03bf1012493fd821f38114010e4b21fe20f1d4f1/docs/FIRMWARE_HMA11_EMUI11.md) · [华为排障说明](https://consumer.huawei.com/cn/support/content/zh-cn00776811/)

## 旧手柄 APK 究竟在何时访问线控

下表偏移为 10.0.0.374 的 `classes.dex` 方法 code_item 文件偏移。REA 的方法反编译已用 Android SDK dexdump 指令复核；Manifest 引用的 XML 过滤器用 aapt 解码。

| 可复查的位置 | 实际行为 |
| --- | --- |
| `CableActivity` 的 Manifest 与 `res/xml/usb_device_filter.xml`；`b.a.e.m.c.e.w.a(Context)`，`0x182C34` | 拥有 USB 接入过滤器的页面位于 `otaupgrade.cableupgrade`。XML 精确匹配 VIA `2109:0105`。枚举函数也只选择该 VID/PID；权限申请可在 `0x183D64` 复核。 |
| `b.a.e.o.Wa.onReceive`，`0x18B02C`；`VRHandleService.b(SafeIntent)`，`0x18C98C`；`b.a.e.f.Pb.a(UsbDevice)`，`0x14E620` | 常驻手柄服务的这条接收路径处理 USB 拔出和蓝牙状态变化。拔出分支识别华为 `12D1` 的头显设备，并清理服务状态。它没有把 VIA Billboard 当作普通头显开屏目标。 |
| `b.a.e.m.c.c.b.r.run`，`0x17646C`；`b.a.e.m.f.q.a(Context)`，`0x186584` | 可读取和记录线控当前版本。后者标出产品 `C-CV10-Cable-C2C01`。因此看到 USB 通信不等于正在写固件，也不能单凭读取版本推断已经开启了供电开关。 |
| `b.a.e.m.c.c.b.q.run`，`0x175FE0` | 固件更新线程持有升级上下文和固件文件名，读取当前线控版本和运行状态，区分已在 ROM 模式、需要切入 ROM 模式及异常状态。直接调用 Android `controlTransfer` 的九个 DEX 位置均在 `b.a.e.m.c.e.w`。在已追到的普通接入、版本读取和更新路径中，未发现佩戴前必须执行的独立线控供电写入。 |

**已证实手柄参与原厂线协议，仍缺少“普通启动时由手柄打开线内供电开关”的证据。** 此判断只覆盖取得样本里的调用，以及已分析的头显固件，不排除未取到的旧桌面、EMUI 内核或 Type-C 控制器参与协商。

华为还列出了 2019-01-04 的 Unreal 开发包 2.0.0.28。归档条目给出的是插件 ZIP 的摘要，现有资料不足以确认内含同版 Android 服务 APK。本次取到的 SDK 3.5.0.68 中，`ArvrRuntimeService.onCreate` 先检查系统是否已经处于 VR 模式，条件不满足便停止服务。头显 .357 固件还能区分查询线缆身份和切换 USB 维护模式使用的两种 DP Attention 标志。三项证据可分别用于追踪应用、系统及线控。[华为 Unreal 归档](https://developer.huawei.com/consumer/cn/doc/graphics-Library/unreal-sdk-download-0000001102329402/) · [旧版 SDK、视频及头显协议的逐项核验](legacy-host-protocol.md)

## 哪一层实际点屏

- EMUI 11.0.0.322 系统服务的 `handleHelmetUp`、`handleHelmetDown`（DEX `0xE4418`、`0xE4210`）对应头显 `AT^SWITCHSCREEN=1/0`。`getPlugUsb`（`0xEC174`）经 `FileInputStream` 读海思 USB 状态节点，调用者检查 `USB_STATE_HOST`。这几条路径没有写主机的 VBUS 开关。12.0.0.302 的对应实现和 P40 运行日志可交叉比对。[系统服务与桌面调用链](android-cable-analysis.md)
- 11.1.0.337 桌面的原生库可以查询线控信息、控制头显面板，并在升级状态且显示移除时请求 `AT^CABLESWITCHUSB`。华为的升级指南也将佩戴启动、摘下进入更新列为不同阶段。[桌面和固件分析](android-cable-analysis.md) · [华为升级指南](https://consumer.huawei.com/cn/support/content/zh-cn00793390/)
- P40 对应的公开 ELS 内核在获得 EDID 后识别 `HUAWEIAV02/03`，具备优先选取 70 Hz 原生时序的逻辑。EMUI 10.1.1 的框架按 3200×1600 或反向尺寸识别 Halliday，设置 VR 显示 ID。只能据此描述相应代码树；本机 P40 实装二进制、CC 线上实际消息都需要各自的证据。[ELS 内核](https://github.com/Supersonic/android_kernel_huawei_els/blob/8d308aeb271a0a8113f2e9f5433c601a693b7b84/drivers/video/fbdev/hisi/dss/dp/link/dp_irq.c#L1533-L1559) · [EMUI 显示识别](https://github.com/dstmath/HWFramework/blob/672bb34094b8780806a10ba9b1d21036fd808b8e/DVC-AN20_EMUI10.1.1/src/main/java/android/vrsystem/VRSystemServiceManager.java#L400-L416)
- 本机原厂线在 70 Hz 和 90 Hz 都复现掉线。换独立 PD 电源后，同一轮 90 Hz 视频在未佩戴时保持约 190 秒，只遮挡感应窗即可触发故障。先保持已佩戴再送视频也失败。要判断线内开关是否先断，最有区分度的证据是一根已确认能亮的同型号原厂线在相同条件下的插线至佩戴记录，或眼镜端 VBUS 与 CC/PD 的同步测量。[带新 PD 电源的交叉试验](pd-proximity.md)
