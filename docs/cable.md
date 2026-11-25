# 原厂手机线与 VL105

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

## 操作

Windows 上查询本机线的版本、厂商及 BOS，仅需 Python 3 和已绑定的 WinUSB 驱动。每次用一根线记录型号、接法、手机界面版本，再执行下列命令。

```powershell
python tools/cable.py probe
```

将标有“连接手机”的插头单独接电脑，在 Windows 上读取线控缓存的电量字节和温度原值可以运行下面的命令。可接辅助 5 V 对照。命令在正常 Billboard 模式下通过 WinUSB 读取，支持已定位寄存器布局的 C9.49.6 和 C9.52.6。这台电脑的实机读数来自 C9.49.6。

```powershell
python tools/cable.py battery
```

本线返回 `level_raw=255`、`temperature_raw=65535`、`temperature_c=null`。在接回 5 V 后的 96 次采样中保持一致。255 超出百分比范围；温度原值 `FFFF` 会被头显格式化成和 28.0°C 相同的文字。接上头显后，Windows 上的线控 Billboard 接口退出，光学、USB 枚举和盒内计量需要分别记录。[固件的字段定义](firmware-resource-analysis.md#头显怎样解码连接线的回包) · [实机证据](../research/evidence/fold7-original-firmware-retest-20261126.txt)

若有工作的同硬件版本线，可尝试双读导出。目标目录需已存在，文件名需未被使用。默认后端仅发设备到主机的查询。头部版本、两份数据、长度和 CRC 都通过后才发布结果。

```powershell
python tools/cable.py dump --maintenance donor-vl105.bin
python tools/cable.py inspect donor-vl105.bin
```

对使用 fwupd 原生支持且能枚举出目标线的系统，可通过 `dump --fwupdtool fwupdtool` 委托其执行维护模式切换及双读。也可指定工具的绝对路径。安装备有该线 OEM 元数据的官方 CAB 时，`flash` 接受提供方给出的 SHA-256，通过 `fwupdmgr local-install` 向明确匹配的 VLI 设备 ID 提交 CAB，由 fwupd 执行包匹配和更新。该入口需要可用的 fwupd 服务及支持 `local-install` 的客户端。同板型裸镜像可用下方的 Windows 原生入口预检。命令参数可用 `python tools/cable.py flash --help` 查看。

## 原生烧录与实机备份

本机导出文件为 `resources/CV10-cable-C9.49.6.bin`，大小 49152 字节，CRC-16/USB 为 `1a69`，SHA-256 为 `f16057065c4c29d6d86901239371f2a6aab2bcf03c6976505c8f5971fba93e02`。备份覆盖 PD 镜像区。实机从零地址和上游 VL105 写入基址 `0x20000` 读取的整个镜像均与备份一致；两段地址是否映射到同一物理扇区仍未知。

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
- 离线检查按上游格式读取 `0x1003` 处的固件版本和 VID/PID，验证 VL105 类型标签、完整大小及末尾的小端 CRC-16/USB，输出 SHA-256。有效的 CRC 只说明镜像内部一致，板型和供体来源需要独立确认。用合成有效镜像验证双读和 CRC，实测拒绝了头显的 `halliday.dfu`。写入入口只用模拟设备列表验证了命令分发，尚无已核实的兼容 OEM 包进行真机验证。[fwupd 镜像解析](https://github.com/fwupd/fwupd/blob/2.1.9/plugins/vli/fu-vli-pd-firmware.c)
