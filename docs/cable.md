# 原厂手机线与 VL105

原厂线在 Fold7 上黑屏时，最新日志捕获了 DP 视频流启动后约 2.14 秒的 USB 根端口掉线。公司电脑接手所需的实测摘录、接线状态及下一项对照已一并归档。[11 月 26 日交接记录](cv10-original-cable-handoff-20261126/README.md) · [前一晚的测试与镜片照片](cv10-original-cable-overnight-20261126.md)

2026-11-25，在原厂手机线单独接入 Windows 的条件下，已读到线的 USB 描述符和四字节固件版本。通过 WinUSB 临时进入 VL105 ROM 模式后，已双读导出当前 PD 镜像。设备随后恢复运行态。

| 只读实测 | 结果 |
| --- | --- |
| Windows USB / 服务 | `2109:0105`，`WinUSB`，Billboard 类 `11/00/00` |
| 厂商、产品 | `VIA Technologies Inc.`，`USB 2.0 BILLBOARD` |
| USB 设备修订、BOS | `bcdDevice=0x0C49`，BOS 共 88 字节，4 个能力描述符 |
| VL105 版本响应 | `0c 09 49 06`。按十六进制与用户记录的 `C9.49.6` 相符。该值来自 PD 控制器的版本请求；单独的 USB 修订号只含其中两个字节 |
| 运行模式 | 模式寄存器返回 `0x81`，按 fwupd 定义为运行态 |
| P40 同时连接电脑时 | `12d1:107e` 复合设备总线描述为 `ELS-AN10`，实际属于手机 |

资料包第 07 个 APK 中，`VRUtils.isCableDevice` 匹配 `2109:0105`。fwupd 源码也将这个 ID 映射到 VL105。该 ID 可由其他品牌的 VL105 产品共用，采集时只将一根待测原厂线接入。[fwupd 2.1.9 设备映射](https://github.com/fwupd/fwupd/blob/2.1.9/plugins/vli/vli-noinst.quirk)

## Windows 图形工具

单独将原厂线标有“连接手机”的插头接电脑，打开 Windows x64 工具。[CV10-Cable-Tool.exe](../firmware_update/tools/windows/CV10-Cable-Tool.exe)

- **导出固件**只需选择保存目录。两次回读一致且 CRC 校验通过后，工具用镜像版本和时间戳生成文件名，例如 `CV10-cable-C9.49.6-20261126-142530-123456.bin`。
- **烧录固件**只需选择待烧录的 `.bin`。工具双读当前固件、比对写入区，并把原始镜像保存到 `%LOCALAPPDATA%\CV10-Cable-Tool\Backups`。预检显示当前版本、目标版本、差异扇区和备份路径。确认后才对差异扇区写入。若预检后目标或备份文件发生改动，工具会要求重新预检。
- **连接线诊断**读取线盒电量和温度缓存、VL105 端口状态原值、RT9471 身份字节，可随快照导出 JSON。电量原值超过 100 时显示“未知”，温度 `0000` 或 `FFFF` 同样显示“未知”。C9.49.6 的端口状态 `81 → 83` 曾随辅助 5 V 接入改变。充电芯片身份和端口状态均无法确认电芯正在充电。电芯电压、电流和充电阶段尚无经验证的读法。[回读证据](../research/evidence/fold7-original-firmware-retest-20261126.txt) · [线盒芯片及状态字分析](cv10-original-cable-handoff-20261126/vl105-pd-analysis.md#从实机身份字节识别充电芯片)
- **连接线诊断 → 寄存器**自动读取芯片与 GPIO、电池与供电、DP 与 HPD、PD 与端口以及 USB 回显。C9.49.6 有 38 项预设，C9.52.6 另含延迟脉冲状态。可输入 `0003, 2DFE-2E02` 单次读取指定地址。周期刷新采集预设，手动结果保留在表格顶部并记录时间。导出的 JSON 含数值地址、原值、解释和逐地址错误。自定义范围每次最多 64 个不同的十六进制地址，读取未知硬件地址时需考虑读后清除等寄存器副作用。[寄存器映射与验证](cable-firmware-research.md#运行态寄存器读数)

久置后按华为说明，通过线盒充电口用合规 5 V 电源充电半小时再试。RT9471 在满足电池通路、温度及充电条件时自行进入涓流、预充或恒流等阶段。当前 `FF/FFFF` 无法判断电芯是否亏电，也无法据此选择外加强制电流。本线曾按官方方式充电，之后仍复现黑屏。电芯是否恢复仍需独立的电压和充电状态证据。[华为供电与黑屏排查](https://consumer.huawei.com/cn/support/content/zh-cn00757290/) · [华为久置处理](https://consumer.huawei.com/cn/support/content/zh-cn00776811/) · [RT9471/D 充电流程](https://www.richtek.com/content/dam/richtek/data/en/resources/product-specifications/rt94/rt9471-rt9471d/product-data-sheets/pdf/DS9471D-04.pdf#page=25) · [本线充电对照](cv10-original-cable-overnight-20261126.md)

## 命令行操作

Windows 上查询本机线的版本、厂商及 BOS，仅需 Python 3 和已绑定的 WinUSB 驱动。每次用一根线记录型号、接法、手机界面版本，再执行下列命令。

```powershell
python tools/cable.py probe
```

将标有“连接手机”的插头单独接电脑，在 Windows 上用下面的命令读取电量、温度、端口状态和充电芯片原值。可接辅助 5 V 对照。命令在正常 Billboard 模式下通过 WinUSB 读取，支持已定位寄存器布局的 C9.49.6 和 C9.52.6。这台电脑的实机读数来自 C9.49.6。

```powershell
python tools/cable.py battery
python tools/cable.py registers 0003 2DFE-2E02
```

本线早期接回 5 V 后的 96 次采样均返回 `level_raw=255`、`temperature_raw=65535`、`temperature_c=null`。255 超出百分比范围，温度原值 `FFFF` 会被头显格式化成和 28.0 °C 相同的文字。接上头显后，Windows 上的线控 Billboard 接口退出，光学、USB 枚举和盒内计量需要分别记录。[固件的字段定义](firmware-resource-analysis.md#头显怎样解码连接线的回包) · [早期实机证据](../research/evidence/fold7-original-firmware-retest-20261126.txt)

2026-11-26 复测 C9.49.6 时保持接线不动。双读导出前为 `FF/FFFF`。从 ROM 恢复运行后，前 4 秒采样为 1% 和 25.1 °C，第 8 秒为 50% 和 25.1 °C，第 12、18 秒再次为 `FF/FFFF`。端口状态全程为 `83`，充电芯片身份全程为 `69`。短时变化表明电量缓存不稳定，电芯电压、充电电流与是否进入预充仍待测量。[带时间戳的实机记录](../research/evidence/cable-c9496-gauge-after-rom-20261126.json)

若有工作的同硬件版本线，可尝试双读导出。目标目录需已存在，文件名需未被使用。默认后端仅发设备到主机的查询。头部版本、两份数据、长度和 CRC 都通过后才发布结果。

```powershell
python tools/cable.py dump --maintenance donor-vl105.bin
python tools/cable.py inspect donor-vl105.bin
```

对使用 fwupd 原生支持且能枚举出目标线的系统，可通过 `dump --fwupdtool fwupdtool` 委托其执行维护模式切换及双读。也可指定工具的绝对路径。安装备有该线 OEM 元数据的官方 CAB 时，`flash` 接受提供方给出的 SHA-256，通过 `fwupdmgr local-install` 向明确匹配的 VLI 设备 ID 提交 CAB，由 fwupd 执行包匹配和更新。该入口需要可用的 fwupd 服务及支持 `local-install` 的客户端。同板型裸镜像可用下方的 Windows 原生入口预检。命令参数可用 `python tools/cable.py flash --help` 查看。

## 原生烧录与实机备份

本机导出文件为 `firmware_update/firmware/cable/stock/CV10-cable-C9.49.6.bin`，大小 49152 字节，CRC-16/USB 为 `1a69`，SHA-256 为 `f16057065c4c29d6d86901239371f2a6aab2bcf03c6976505c8f5971fba93e02`。备份覆盖 PD 镜像区。实机从零地址和上游 VL105 写入基址 `0x20000` 读取的整个镜像均与备份一致；两段地址是否映射到同一物理扇区仍未知。

先将目标线的当前固件导出为独立备份，再比较同板型候选镜像：

```powershell
python tools/cable.py flash-raw candidate.bin --backup current.bin
```

工具检查 CRC、镜像头 VID/PID、当前版本和两个地址区的内容，再报告有差异的 4 KiB 扇区数。确认镜像的板型与来源后，在同一命令末尾加 `--apply` 才会开始编程。每个有差异的扇区擦除后先查空，再以 32 字节写入并读回比较，随后校验整个写入区，重启并检查运行版本。供电中断时设备可能无法正常启动。

本机用刚导出的备份执行过真实预检，差异为零，重启后版本仍为 C9.49.6。内存模拟器使用三个扇区有差异的镜像，验证了比较、差异写入、全区回读和写入失败后的备份恢复。若写入期间设备仍可通信，工具会尝试恢复已动过的扇区并校验整个写入区；恢复失败时跳过主动复位并报错。断电或 USB 断线可能使恢复无法执行。

2026-11-26，Windows 双读确认这根线正在运行群友的 C9.52.6。用本线升级前的 C9.49.6 备份回刷了 12 个差异扇区。重启后设备报告 `0c 09 49 06`，再次双读的 49,152 字节与本线备份完全一致。

在同一台 Fold7、同一副 CV10 和同一套 5 V 电源上，两版均出现双眼黑屏和头显 USB 掉线。C9.49.6 下，手机先提交了左右眼图案，头显随后应答开屏 `OK`，约 1.15 秒后控制接口离线。临时让 Fold7 暂停给自身电池充电也复现了故障。Gen 2 C-C 直连时双眼可见测试图。[回刷与镜片对照记录](../research/evidence/fold7-original-firmware-retest-20261126.txt)

## 早期运行态及 fwupd 测试记录

- 已在本机运行 `probe` 并重复读取版本。运行态调用 fwupd 所用 SPI READ 从 `0x1003` 查询镜像头时，WinUSB 返回 `WinError 31`。没有生成镜像。随后重新查询，线仍返回相同运行态和固件版本。
- 在项目的私有研究目录解包并运行上游 Windows 发行版。2.1.9 的 MSI SHA-256 与 GitHub Release 提供的 `4a9d2b0a387c1fa5757a18d987b00738e5fbd75818a3564bca5c849420278a89` 一致。2.1.9 与 1.9.25 的 `--plugins vli --json get-devices` 都返回 `No detected devices`。2.1.9 的 `builtin.quirk.gz` 含 VL105 参数，但其中没有 `USB\VID_2109&PID_0105` 设备匹配。上游源码的通用 ID 位于 `vli-noinst.quirk`。另在两个解包副本的私有 quirks 目录中，将设备匹配限定到本机的 REV_0C49 再做只读枚举，结果相同。已移除该测试配置，设备始终保持运行态。[上游 Windows 说明](https://github.com/fwupd/fwupd/blob/2.1.9/docs/win32.md) · [2.1.9 发行包](https://github.com/fwupd/fwupd/releases/tag/2.1.9)
- 上游针对 VL105 声明 PD 镜像大小上限为 `0xC000`。其导出路径从 `0` 读取该长度，先切换到维护模式，再恢复运行，过程会改动易失性寄存器并可能触发 USB 重枚举。该版本的单镜像更新路径擦除后按 `VliPdOffset` 写入，VL105 默认偏移为 `0x20000`。缺少华为原厂线的板级分区资料，尚无依据将导出区域等同于可在此偏移回写的恢复镜像。[fwupd PD 实现](https://github.com/fwupd/fwupd/blob/2.1.9/plugins/vli/fu-vli-pd-device.c) · [VL105 参数](https://github.com/fwupd/fwupd/blob/2.1.9/plugins/vli/vli.quirk)
- 离线检查按上游格式读取 `0x1003` 处的固件版本和 VID/PID，验证 VL105 类型标签、完整大小及末尾的小端 CRC-16/USB，输出 SHA-256。有效的 CRC 只说明镜像内部一致，板型和供体来源需要独立确认。用合成有效镜像验证双读和 CRC，实测拒绝了头显的 `halliday.dfu`。`flash` 的 OEM CAB 路径通过了模拟设备列表的命令分发测试，兼容的 OEM 包仍待取得。`flash-raw` 的真机回刷结果见上节。[fwupd 镜像解析](https://github.com/fwupd/fwupd/blob/2.1.9/plugins/vli/fu-vli-pd-firmware.c)
