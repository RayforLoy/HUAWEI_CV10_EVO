# 原厂手机线与 VL105

2026-11-25，在原厂手机线单独接入 Windows 的条件下，已读到线的 USB 描述符和四字节固件版本。导出尝试停在首次读镜像头，尚无该线的可恢复备份，也没有执行擦除或写入。

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

若有工作的同硬件版本线，可尝试双读导出。目标目录需已存在，文件名需未被使用。默认后端仅发设备到主机的查询。头部版本、两份数据、长度和 CRC 都通过后才发布结果。

```powershell
python tools/cable.py dump donor-vl105.bin
python tools/cable.py inspect donor-vl105.bin
```

对使用 fwupd 原生支持且能枚举出目标线的系统，可通过 `dump --fwupdtool fwupdtool` 委托其执行维护模式切换及双读。也可指定工具的绝对路径。安装备有该线 OEM 元数据的官方 CAB 时，`flash` 接受提供方给出的 SHA-256，通过 `fwupdmgr local-install` 向明确匹配的 VLI 设备 ID 提交 CAB，由 fwupd 执行包匹配和更新。该入口需要可用的 fwupd 服务及支持 `local-install` 的客户端。供体导出的裸镜像只用于离线检查。命令参数可用 `python tools/cable.py flash --help` 查看。

## 本机验证与边界

- 已在本机运行 `probe` 并重复读取版本。运行态调用 fwupd 所用 SPI READ 从 `0x1003` 查询镜像头时，WinUSB 返回 `WinError 31`。没有生成镜像。随后重新查询，线仍返回相同运行态和固件版本。
- 在项目的私有研究目录解包并运行上游 Windows 发行版。2.1.9 的 MSI SHA-256 与 GitHub Release 提供的 `4a9d2b0a387c1fa5757a18d987b00738e5fbd75818a3564bca5c849420278a89` 一致。2.1.9 与 1.9.25 的 `--plugins vli --json get-devices` 都返回 `No detected devices`。2.1.9 的 `builtin.quirk.gz` 含 VL105 参数，但其中没有 `USB\VID_2109&PID_0105` 设备匹配。上游源码的通用 ID 位于 `vli-noinst.quirk`。另在两个解包副本的私有 quirks 目录中，将设备匹配限定到本机的 REV_0C49 再做只读枚举，结果相同。已移除该测试配置，设备始终保持运行态。[上游 Windows 说明](https://github.com/fwupd/fwupd/blob/2.1.9/docs/win32.md) · [2.1.9 发行包](https://github.com/fwupd/fwupd/releases/tag/2.1.9)
- 上游针对 VL105 声明 PD 镜像大小上限为 `0xC000`。其导出路径从 `0` 读取该长度，先切换到维护模式，再恢复运行，过程会改动易失性寄存器并可能触发 USB 重枚举。该版本的单镜像更新路径擦除后按 `VliPdOffset` 写入，VL105 默认偏移为 `0x20000`。缺少华为原厂线的板级分区资料，尚无依据将导出区域等同于可在此偏移回写的恢复镜像。[fwupd PD 实现](https://github.com/fwupd/fwupd/blob/2.1.9/plugins/vli/fu-vli-pd-device.c) · [VL105 参数](https://github.com/fwupd/fwupd/blob/2.1.9/plugins/vli/vli.quirk)
- 离线检查按上游格式读取 `0x1003` 处的固件版本和 VID/PID，验证 VL105 类型标签、完整大小及末尾的小端 CRC-16/USB，输出 SHA-256。有效的 CRC 只说明镜像内部一致，板型和供体来源需要独立确认。用合成有效镜像验证双读和 CRC，实测拒绝了头显的 `halliday.dfu`。写入入口只用模拟设备列表验证了命令分发，尚无已核实的兼容 OEM 包进行真机验证。[fwupd 镜像解析](https://github.com/fwupd/fwupd/blob/2.1.9/plugins/vli/fu-vli-pd-firmware.c)
