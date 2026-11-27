# 华为 Windows 助手怎样让 CV10 进入 PC 模式

华为 PCVR 助手 10.0.0.10 的连接页面确实会发送一条名为充电协议的命令。目标是头显 `12D1:107E` 的 HID 接口。原厂手机线单独枚举时的控制器是 `2109:0105`，与这条命令的目标不同。

| 样本 | 从实际调用点观察到的行为 |
| --- | --- |
| 资料包的 3DoF 助手，主程序 `HwPCVRAssistant.exe` | 在初始页收到头显在线通知后，Qt 状态槽 RVA `0x68480` 在 `0x684D5` 传入来源 1。目的函数于 `0x3D319` 调用 Windows `HidD_SetFeature`，消息以 `04 02 0E 01` 开头。失败日志为 `Open Charge Protocol failed!`。函数忽略 HID 发送的返回值，因此需要另行核实传输。 |
| 本机 NOLO HOME 的 `huaweicv1pro` SteamVR 驱动 | 激活时先调用 `enableHmdImu` 发送 `04 02 05 02`。姿态有效位曾为假、随后变真时，驱动在 RVA `0x9B31` 调用 `Hmd.dll!setPCMode`，发送相同的 PC 来源报告。11 月 25 日的 SteamVR 日志有一次启用 IMU 成功，日志没有记录当时的线型。 |
| 眼镜固件 `CV10AC10.0.1.357` | 从 128 字节的 Windows Feature 报告取出长度 2 和负载 `0E 01`，把来源 1 写入 RAM，再发送系统消息 `13/2C`。该消息转为 ioctl 6，来源为 PC 时打印 `detect pc source,start charging`，随后直接返回。此分支没有访问充电器、GPIO 或 PD 控制器。其他任务可以读取这个来源值，例如佩戴时进入 PC 专用的音频回调。 |

对照用的 `AT^SETSOURCE=1` 写同一个来源字段。HID 比这条 AT 命令多走一次系统消息，故读取 `AT^GETSOURCE?` 只能核对来源标签。正常启动路径中没有找到一个由 Windows 助手直接发给原厂手机线盒的供电开关命令。[头显 HID、系统消息及 AT 调用链](legacy-host-protocol.md)

华为官方的电脑接法使用单独配售的 Belkin 或 FIBBR 计算机线，要求先在扩展屏模式遮挡感应窗，看见转过 90 度的 Windows 桌面，再启动 PCVR 助手。本项目测试的是带电池转接盒的随盒手机线。普通 C-C 线在这台电脑上有右眼实拍阳性对照。[华为电脑连接说明](https://consumer.huawei.com/cn/support/content/zh-cn00757271/) · [本机两根线的镜片对照](company-pc.md)

## 原厂手机线实测

11 月 26 日，电脑 XHC1、原厂线 C9.49.6、无辅助电源。仅重插眼镜端的那次未捕获到 USB 身份变化。随后冷插电脑端，头显与音频重新枚举。本轮通过 Windows HID API 复现两条原厂命令，按 Monado 的解析规则核对头显原始 IMU 样本，再在真实佩戴事件后发送一次 PCUI 开屏。完整 SteamVR 姿态解算及原厂 GUI 未参与本轮。[USB、DP、IMU 与逐帧镜片结果](../../research/evidence/pc-original-pcmode-20261126.txt)

| 时间 | 电脑观察 |
| --- | --- |
| 12:00:47.472–47.526 | 头显回复 CV10，线控回复 `10C094906255+280`。默认来源为 PC。启用 IMU 的 HID 调用成功。 |
| 12:00:47.850–47.867 | 收到三帧 60 字节 IMU 样本，眼镜时钟连续递增，重力幅值约 1 g。随后 PC 模式的 HID 发送成功，来源仍为 1，接近传感器启用成功。 |
| 12:00:47.964–59.165 | 先收到未佩戴，再恢复 Windows 原生 3200×1600、90 Hz 显示目标，最后收到已佩戴。 |
| 12:00:59.171–59.174 | 根端口读不到先前的集线器身份。PCUI 开屏读到空应答，事件串口读失败。佩戴事件到串口读失败约 9 ms。 |
| 12:01:02.382 | 眼镜集线器与第 5 口 VIA HID 恢复，音频与头显控制未随之恢复。12:02:01 对同一显示目标的三次 NVIDIA DDC 读取均失败。 |

右眼录像索引和解码均为 6,592 帧。没有一帧出现测试橙色或绿色。用同一算法处理此前普通 C-C 线的右眼阳性对照，两种颜色各覆盖约 71% 的图像。本轮前一次电脑单独供电测试在故障后仍可三读 EDID，这一轮却读失败，说明即便同样无辅助电源，故障后 DDC 表现也会变化。[上轮电脑单独供电对照](../../research/evidence/pc-original-host-power-20261126.txt)

这次已经确认原厂 PC 模式报告在佩戴前成功提交，IMU、接近事件与视频目标同时可用，仍未点亮。故障触发条件已收敛到视频有效时的佩戴唤醒。已有 Windows 数据不含眼镜端 VBUS 波形和 CC/PD 报文，仍不能判定首个异常发生在转接盒供电、Type-C 协商还是头显内部。

另核对了原生 Android 的休眠路径。服务 11.0.0.322 的 Binder 项 2002 可传入 0 或 1。桌面 11.1.0.337 在 DEX `0x181180` 所在的摘下处理函数内专门识别 Halliday（CV10），命中后记录 `halliday do not need go to sleep` 并跳过休眠。成对调用这项服务的 `0x192634` 和 `0x192A64` 属于 VR2 分支。因此本轮没有把 VR2 的休眠/恢复序列加到 CV10 的 Windows 启动试验中。

## 样本核验

| 样本 | SHA-256 |
| --- | --- |
| 资料包内 `HwPCVRAssistant_10.0.0.10` 安装程序 | `d482ddb0c29862b991b88324ba1882c15ba3dd4ba81c05554082eb4d88b500b9` |
| 该版本的 `HwPCVRAssistant.exe` | `fa3426ec12a65f0c72485cdc30b2036a66e371e6d261b3b814956811aafd2726` |
| NOLO 的 `driver_huaweicv1pro.dll` | `dbddd3c4b3dfcdaad953d08a0bea735422af72eda8d53916be28c858b41729c1` |
| NOLO 随附 `Hmd.dll` | `d29f7fe6b5abd0f354ef819e7b74f202290c91bf32939c4248b177fe2ea1815b` |
| 升级工具内头显镜像 `Dfu/halliday.dfu` | `85579969f7362cc9acf894cd351d54328763b1a6819c0953c64857a5d1aae7e8` |
