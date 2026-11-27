# C9.53.6 群友 Pin C 固件核查

2026-11-28，香港时间。用户提供的 `C9.53.6-cur-4lane-pinC.bin` 为 49,152 字节的 VL105 镜像，版本字节 `0C 09 53 06`，CRC-16/USB `A5CB`，SHA-256 `c9d88fcc5205bfb6f9aa6cdd93839c0bfb056522f542132d9ef028efe1c129f6`。对照镜像为 C9.53.6 原版 `D0DB` 和供电测试版 `7EF0`。三份镜像的 CRC 均通过重算。 [样本摘要与回放输出](../research/evidence/cable-c9536-pin-c-offline.json)

## 字节差异与构帧回放

相对原版共改动 112 字节，分布在 `0x6000`、`0x9000`、`0xB000` 三个 4 KiB 扇区。原版的 `0x6D38` 改为跳转至 `0x9AED`，两段机器码与供电测试版逐字节一致。相对供电测试版只有以下三字节不同。 [供电测试版生成脚本](../tools/patch_c9536_charging.py)

| 偏移 | 供电测试版 | 群友版 | 用途 |
| --- | --- | --- | --- |
| `0xB8C5` | `0C` | `04` | Discover Modes 的引脚能力位图从 C、D 改为仅 C |
| `0xBFFE–0xBFFF` | `F0 7E` | `CB A5` | 小端 CRC-16/USB |

用 emu8051 执行 `0x4240–0x4251` 的 Discover Modes VDO 拷贝循环。原版和供电测试版在 `XDATA[0x2B50]` 生成 `05 0C 00 00`，群友版生成 `05 04 00 00`。另执行 `0x0376–0x0388` 的 DP Configure VDO 拷贝循环，三版在 `XDATA[0x1026]` 均生成 `06 04 00 00`，即小端 `0x00000406`，对应 Pin C。 [DP VDO 字段定义](https://github.com/torvalds/linux/blob/v6.12/include/linux/usb/typec_dp.h)

电源路径回放覆盖 14 组条件，群友版与供电测试版的构帧结果相同。已满足上游 5 V / 3 A 固定档协商条件时，手机侧发布 `0x260190C8`（5 V / 2 A）。模拟上游 2.4 A 时，或提供 3 A 但未收到 Accept 时，均为 `0x26019096`（5 V / 1.5 A）。无上游 PD 时为 `0x26019064`（5 V / 1 A）。RT9471 收尾输入限流写值仍为 `0x1E`（1.5 A）。实际 PD 合同和手机净电流未在本轮测量。 [充电路径和测点](cable-c9536-fold7-charging.md)

## 对显示和 USB 的影响

Pin C 把四条高速通道分配给 DP，USB 2.0 和 USB-PD 可同时工作。群友版去掉了 Pin D 的能力声明，保留 DP、USB Billboard 和供电协商。固件证据不支持「纯充电 C2C」的说法。此前 Fold7 用原厂线已记录过 `DP_LINK_CONF<C>`、`lane_count=4` 和训练通过。普通 C-C 与原厂线接法都枚举到眼镜的 USB 音频、控制及 HID 接口。 [VESA 通道图](https://www.vesa.org/wp-content/uploads/2014/09/DP-Alt-Mode-Overview-for-VESA-v1.pdf#page=11) · [原厂线 DP 日志](../research/evidence/fold7-original-vs-direct-dp.txt) · [USB 拓扑](cv10-original-cable-handoff-20261126/c9526-power-and-buses.md#各条总线上的设备)

在原先选择 Pin D 的主机上，这项能力改动可能让显卡建立四通道视频链路。SteamVR 的头显身份由已安装的驱动注册，原厂线已有经 NOLO 进入 NVIDIA 90 Hz 直连的实测记录。群友机刷写前后的链路状态缺少日志，群友版此次仅做离线核查。 [原厂线 SteamVR 实测](device-openxr-check.md#windows-原厂手机线与-nolo-steamvr) · [Valve OpenVR 驱动文档](https://github.com/ValveSoftware/openvr/blob/master/docs/Driver_API_Documentation.md)
