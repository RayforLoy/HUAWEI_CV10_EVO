# CV10 固件升级

这里汇总华为原厂升级工具、头显 DFU、VL105 手机线固件、项目烧录工具和相应的实测记录。镜像按设备和验证状态归档。公开文件和本地留存样本均可用以下清单核验。 [SHA256SUMS](../firmware_update/SHA256SUMS)。

## 按设备选择升级入口

| 升级目标 | 工具和镜像 | 使用要点 |
| --- | --- | --- |
| **CV10 / AV02 头显** | 华为 Windows [HuaweiVRUpdater 10.0.0.312 原 ZIP](../firmware_update/official/windows/HuaweiVRUpdater_10.0.0.312.zip) 或 [已解包程序](../firmware_update/official/windows/HuaweiVRUpdater_10.0.0.312/HuaweiVRUpdater_10.0.0.312.exe) | 接入头显。在升级器中核对型号和目标版本，使用对应的 `.dfu`。运行解包程序时保留整个目录，其中包含驱动、两个 DFU 和页面资源。 [华为升级指南](https://consumer.huawei.com/cn/support/content/zh-cn00793390/) |
| **原厂手机连接线 VL105** | [项目 Windows x64 连接线工具](../firmware_update/tools/windows/CV10-Cable-Tool.exe) 和下方的 49,152 字节线缆 `.bin` | 只接线盒的「连接手机」端，眼镜端拔开，读取状态确认 `2109:0105`。先用「导出固件」备份，再用「烧录固件」选择目标镜像并核对预检。 [工具说明和回刷记录](cable.md) |
| **原厂手机连接线 VL105** | [项目 Android ARM 升级工具](../firmware_update/tools/android/CV10-Cable-Updater-2A-arm.apk) | 内置 **C9.49.6 2 A 观测版**，支持 `arm64-v8a` 和 `armeabi-v7a`，需要 Android 8.0 及 USB Host。先拔下 CV10，在线盒辅助口接 5 V / 2 A 电源，再接手机。应用会提示风险，要求确认接线，双读备份后才写入。 [Android 工具说明](../tools/android-cable/README.md) |
| **华为手机端线缆 OTA** | P40 参考组的[华为 VR 手柄](apk-archive.md)与[华为 VR 桌面](apk-archive.md) | 在华为 VR 环境中按版本提示更新。手机也可只接线盒，通过 USB 授权进入升级页。升级包由原厂流程在线提供。 [华为线缆 OTA 操作](https://consumer.huawei.com/cn/support/content/zh-cn11355237/) |
| **6DoF 定位器和左右手柄** | 华为 [PC VR 助手 11.0.0.105](../firmware_update/official/6dof/HwPCVRAssistant_11.0.0.105.exe)或华为 VR 桌面 | 设备接好并联网后，在「设备管理 → 固件升级」查看配件更新。 [华为 6DoF 升级指南](https://consumer.huawei.com/cn/support/content/zh-cn15856480/) |

Windows 连接线工具烧录时会在 `%LOCALAPPDATA%\CV10-Cable-Tool\Backups` 留一份自动备份。自选 C9.52.6 镜像使用 Windows 工具的「烧录固件」入口。项目 Android APK 已核对签名、架构和内置镜像，手机端实际写入待验证。工具可用「导出最近备份」保存原镜像。升级期间保持线盒供电和 USB 连接，恢复时优先使用本线刷前的双读备份。

## 华为原厂资料

### Windows 头显 DFU

华为升级器来自本地群资料归档。本机复核了解包程序的 Windows Authenticode 签名，发布者为 `Huawei Device Co., Ltd.`，状态为 `Valid`。ZIP 中的 28 个文件均与解包目录中的文件逐字节一致。驱动、辅助程序、许可文本和两份镜像随原包保留。 [随包中文使用说明](reference/华为VR升级工具使用说明.pdf) · [升级器解析](firmware-resource-analysis.md)

| 镜像 | 适用头显 | 固件版本 | DfuSe CRC |
| --- | --- | --- | --- |
| [halliday.dfu](../firmware_update/official/windows/HuaweiVRUpdater_10.0.0.312/Dfu/halliday.dfu) | **CV10** | `10.0.1.357` | `FBCCC50E` |
| [wallex.dfu](../firmware_update/official/windows/HuaweiVRUpdater_10.0.0.312/Dfu/wallex.dfu) | **AV02** | `C00B268` | `331ACC95` |

两份头显镜像共用 DFU 标识 `12D1:1093`，选择时以产品型号为准。本机旧日志记录了 CV10 从 `10.0.1.349` 写入 `.357` 并退出 DFU。随后独立的设备版本查询读到 `CV10AC10.0.1.357`。 [Windows 升级日志](reference/updater-logs/CSharp_log-2026-11-25.txt) · [实机版本与固件对照](firmware-resource-analysis.md#头显怎样解码连接线的回包)

### Android 与 6DoF 原厂样本

- P40 参考组七个 APK 见[提取包下载与校验](apk-archive.md)。手柄和桌面包含线缆 OTA 流程。
- 本机另留存五个不同版本的厂商历史样本。[历史样本来源、包名和签名](../research/evidence/cv10-legacy-apks-20261126.json)
- 6DoF PC VR 助手的签名也已核验为 `Huawei Device Co., Ltd.`。配套使用指导已移至参考资料目录。 [华为 PC VR 助手使用指导](reference/华为PCVR助手使用指导.pdf)

## VL105 线缆镜像

这些镜像用于 CV10 原厂手机线的线盒。版本字段相同的镜像用 CRC 或 SHA-256 区分。2 A 和 2.5 A 表示 RT9471 的输入限流设定，当前 C9.52.6 原版及两个改版的手机端 PD 离线回放均为 5 V 固定档。 [供电与 PD 回放报告](cv10-original-cable-handoff-20261126/c9526-power-and-buses.md)

| 固件 | CRC-16/USB | 验证状态 |
| --- | --- | --- |
| [原厂 C9.49.6](../firmware_update/firmware/cable/stock/CV10-cable-C9.49.6.bin) | `1A69` | 本线原始备份，原文件 `CV10-cable-20261125-210954.bin` 和多次升级前后双读内容相同。已实机回刷校验。 |
| 原厂 C9.52.6（本地样本） | `2DCB` | 群友备份，原文件 `CV10-cable-20261125-184049.bin`。已在线盒实测，随后回刷本线原版。 [P40 角色记录](../research/evidence/p40-original-c9526-power-roles.txt) |
| C9.53.6 来样（本地样本） | `D0DB` | 用户提供的线盒导出，来源描述为官方售后版。已核对 CRC、输入限流和 PD 离线回放。 [C9.53.6 与 C9.52.6 对照](cable-c9536-vs-c9526.md) |
| [C9.49.6 2 A 观测版](../firmware_update/firmware/cable/modified/C9.49.6-2A-input-observer.bin) | `27B9` | Windows 实机读回 `IBUS=28`，同一测试配置有 Windows、P40 和 Fold7 出图记录。此镜像已核对与项目 Android APK 内置固件相同。 [Windows 输入限流对照](../research/evidence/pc-original-2a-input-20261126.json) · [Fold7 和 P40 实测](../research/evidence/fold7-original-2a-openxr-20261126.json) |
| [C9.52.6 2 A](../firmware_update/firmware/cable/modified/C9.52.6-2A-input.bin) | `7E58` | `IBUS` 初始化为 `0x28`。通过镜像校验和 PD 离线回放，实机带载待验证。 |
| [C9.52.6 2.5 A](../firmware_update/firmware/cable/modified/C9.52.6-2.5A-input.bin) | `47DE` | `IBUS` 初始化为 `0x32`。通过镜像校验和 PD 离线回放，5 V / 2.4 A iPad 电源的带载表现待验证。 |

[`firmware/cable/experiments/`](../firmware_update/firmware/cable/experiments/) 另存七份试验镜像，包括充电 A/B、RT9471 状态和输入观测、两版 IRQ 记录以及端口动作追踪。`C9.49.6-input-event-v1.bin` 的空载总线应答校验未通过，后续带载实验使用 v2。试验版的用途、恢复记录与各自的 SHA-256 见报告。 [充电、输入限流与回刷实验](cv10-original-cable-handoff-20261126/charging-ab.md) · [端口追踪](cv10-original-cable-handoff-20261126/vl105-pd-analysis.md) · [C9.52.6 升级界面照片](../research/evidence/c9526-update-screen.png)

## 研究、源码与校验

| 内容 | 归档入口 |
| --- | --- |
| 头显 DFU 格式、PC 升级流程和线缆字段 | [头显与 PC 升级器](firmware-resource-analysis.md) |
| 线盒固件、Windows 诊断与预检 | [线缆逆向](cable-firmware-research.md) · [Windows 工具与实测](cable.md) |
| C9.52.6 电源轨、I²C 和 PD | [供电与总线](cv10-original-cable-handoff-20261126/c9526-power-and-buses.md) · [8051 离线回放源码](../tools/replay/c9526-pd-replay.c) |
| Fold7 使用 C9.53.6 时的充电功率 | [2.4 A / 3 A 离线对照与实机测点](cable-c9536-fold7-charging.md) |
| 跨主机实测、镜片照片和故障对照 | [原厂线交接报告](cv10-original-cable-handoff-20261126/README.md) · [原始证据](../research/evidence/) |
| 项目工具与构建入口 | [Windows 后端](../tools/cable.py) · [Windows GUI](../tools/cable_gui.py) · [Android 源码和构建](../tools/android-cable/README.md) |
| 上游及硬件资料 | 本机的 fwupd 安装包在 `firmware_update/tools/upstream/`。快速指南、群 FAQ 与拆机资料在[参考资料目录](reference/) |

在仓库根目录可对指定镜像做离线校验，输出中的版本、VID/PID、CRC 和 SHA-256 可与本页及 [校验清单](../firmware_update/SHA256SUMS) 核对。

```powershell
python tools/cable.py inspect firmware_update/firmware/cable/modified/C9.52.6-2.5A-input.bin
Get-FileHash -Algorithm SHA256 -LiteralPath firmware_update/official/windows/HuaweiVRUpdater_10.0.0.312.zip
```

原厂 C9.52.6 和 C9.53.6 导出在本机 `firmware_update/firmware/cable/stock/` 留存。接手时可按校验清单核对自行取得的样本。[跨电脑协作指南](../AGENTS.md)
