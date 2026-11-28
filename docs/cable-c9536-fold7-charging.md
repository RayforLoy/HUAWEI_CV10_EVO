# Fold7 与 C9.53.6 原厂线的边用边充

2026-11-27，香港时间。用户报告 Fold7 搭配原厂线、C9.53.6 和标称 5 V / 2.4 A 的电源，使用中电量仍会下降。本文按手机电池净放电分析。主对话已识别到 C9.53.6 的 RT9471 输入限流和手机侧 PD 档位。本轮用同一份 CRC `D0DB` 的线盒镜像补做了 2.4 A 与 3 A 条件的离线对照。电脑当时没有检测到 Fold7 的 ADB 连接，手机侧电压、电流、温度与实际 PD 合同待测。 [C9.53.6 样本与原始研究](cable-c9536-vs-c9526.md) · [主对话回放记录](../research/evidence/cable-c9536-vs-c9526-offline.json)

## 供电瓶颈在哪里

| 测点 | 已知事实 | 对手机净电量的影响 |
| --- | --- | --- |
| 辅助充电器 | 5 V / 2.4 A 的铭牌约为 12 W。线盒如果能取到该功率，手机、眼镜和线盒共同使用这份预算。标准 USB-C 5 V / 3 A 电源的名牌预算为 15 W。 | 供电余量、线损和负载都在手机端之外。USB-A 版 2.4 A 电源经 A 转 C 接入时，上游没有 USB-PD 合同。实际取电要看接法和负载。 [华为供电说明](https://consumer.huawei.com/cn/support/content/zh-cn00757290/) · [USB Type-C 电源选项与 CC 通讯规范](https://www.usb.org/sites/default/files/USB%20Type-C%20Spec%20R2.0%20-%20August%202019.pdf) |
| 线盒 RT9471 | C9.53.6 启动先写 `IBUS=14`（1 A），再写 `1E`（1.5 A）。`AUTO_AICR=0`，这个支路的限流为固定配置。`SYS` 最低调节值为 3.9 V。 | 1.5 A 设置直接约束 RT9471 自己的输入。辅助口到手机端的旁路或共用路径还缺走线证据。 [RT9471 寄存器定义](https://www.richtek.com/content/dam/richtek/data/en/resources/product-specifications/rt94/rt9471-rt9471d/product-data-sheets/pdf/DS9471D-04.pdf#page=38) |
| 线盒给手机的 PD 源能力 | 常规回放给手机发布 5 V / 1.5 A（7.5 W），回退分支发布 5 V / 1 A（5 W）。前一版同样如此。 | 这是该分支的协议档位。手机实际输入可更低，电池得到的净电流还取决于运行负载、转换损耗和温控。 [原厂线 5 V 普通充电规格](https://consumer.huawei.com/cn/support/content/zh-cn00757290/) · [三星慢充与温控说明](https://www.samsung.com/us/support/troubleshoot/TSG10013245/) |
| Fold7 自身 | 三星列出的快充能力为 25 W 级有线超级快充。原厂 CV10 线盒已追到的路径只给手机端公布 5 V 固定档。 | 在原线后插 25 W 或更大的 PPS 充电器，常规固件分支仍按下表给手机公布 5 V。 [三星 Fold7 规格](https://news.samsung.com/global/samsung-galaxy-z-fold7-raising-the-bar-for-smartphones) · [三星 PD/PPS 适配器输出规格](https://www.samsung.com/us/mobile-accessories/25w-pd-power-adapter-black-sku-ep-t2510nbegus/) |

## 补充离线回放

确认归档镜像 SHA-256 为 `8e8d9d0df2809f2d3a673519834c83662acc5be6635060d75ef246133956843e`。用 emu8051 执行收到源能力后的导入入口 `0x6613` 和端口 0 发布入口 `0x5C23`，记录 `Source_Capabilities` 的 32 位 PDO。每次以 5 V 固定档开头，另外提供模拟的 9 V 和 PPS。`0x661E` 把导入对象计数压到 1。下表只记录构帧结果。 [Fixed PDO 单位](https://github.com/torvalds/linux/blob/v6.12/include/linux/usb/pd.h) · [主对话采用的入口与模拟条件](../research/evidence/cable-c9536-vs-c9526-offline.json)

| 离线场景 | 发布给手机的第一项 |
| --- | --- |
| 原版回退路径 | `26019064`，5 V / 1 A |
| 原版常规路径，上游 5 V / 2.4 A | `26019096`，5 V / 1.5 A |
| 原版常规路径，上游 5 V / 3 A | `26019096`，5 V / 1.5 A |
| 在模拟器内只把 RT9471 收尾写入改成 2.4 A，重复上述两组上游 PDO | 两组均为 `26019096`，5 V / 1.5 A |
| 在模拟器内把手机侧电流字段改为 2 A，上游 5 V / 3 A，常规路径 | `260190C8`，5 V / 2 A |
| 给原版模拟器预置 `XDATA[2A49]=3` 与 `XDATA[1205]=0x33`，同时提供 2.4 A 固定源能力 | `260190F0`，5 V / 2.4 A。该组合为人工构造，真实充电器能否触发仍待验证 |

RT9471 收尾限流写入的立即数在 `0xAE00`，2.4 A 编码为 `0x30`。常规分支覆盖手机 PDO 电流字段的立即数在 `0x6D3F`，单位为 10 mA。把两处分别替换可验证两项设置各自作用的阶段。目前只在模拟器内改字节，实际插接、供电、协商和发热需另测。无上游 PD 时另回放了默认表构造器 `0x557A`，分别从 `0x1205=0x33` 和 `0x77` 开始，两种情况下生成的第一项都为 5 V / 1 A。这组寄存器场景尚未和具体的 iPad 电源匹配。

## 2026-11-28 手机请求回放与实机读数

使用 C9.53.6 原版、条件式 2 A 供电测试版和群友 Pin C 版。执行端口 0 的 `0x5C23` 发布源能力，再把手机 RDO 注入接收缓存，经 `0x7AEB` 解析。固件在 `0x69DA–0x6A09` 将 RDO 工作电流与已发布档位比较，`0x32A1` 选择接受或拒绝分支。测试中的上游 PD 报文、发送就绪标志和计时器条件由模拟器提供。 [镜像摘要、入口参数与逐次读数](../research/evidence/cable-c9536-charging-followup-20261128.json)

| 镜像 | 辅助口模拟档位 | 给手机发布 | 手机模拟请求 | 写入手机侧发送寄存器 |
| --- | --- | --- | --- | --- |
| 原版 | 5 V / 3 A | 1.5 A | 1.50 A | `43 00` Accept，辅助口后续就绪后为 `46 00` PS_RDY |
| 原版 | 5 V / 3 A | 1.5 A | 2.00 A | `44 00` Reject |
| 供电测试版 | 5 V / 3 A | 2.0 A | 2.00 A | Accept，辅助口后续就绪后为 PS_RDY |
| 供电测试版 | 5 V / 3 A | 2.0 A | 2.01 A | Reject |
| 供电测试版 | 5 V / 2.4 A | 1.5 A | 2.00 A | Reject |
| 群友 Pin C 版 | 5 V / 3 A | 2.0 A | 2.00 A | Accept，辅助口后续就绪后为 PS_RDY |

在上述接受用例里，模拟辅助口收到重新协商的 Accept 后，线盒维持等待。接收辅助口 PS_RDY 后，`XDATA[2AD8]` 从 `01` 变为 `02`，在回放所设定的计时器条件下，线盒给手机写出 PS_RDY。证明范围覆盖报文处理和发送寄存器，实机合同和电流待测。

原厂较高电流分支可由 `0x557A` 的一个端口状态入口置 `XDATA[2A49]=3`。预置该状态后，端口寄存器 `0x1205=0x33` 的回放把输入列表中的 2.4 A 或 3 A 原样发布给手机。将 `0x1205` 改为 `00`、`03`、`30` 或 `FF` 时，本组回放均降到 1 A。该分支的实机进入条件和给眼镜分配的功率未知。按 5 V / 3 A 的总输入预算，手机若用满 3 A，眼镜和线盒没有功率余量。

Fold7 在现有接线上报告 `sink/host`、USB 供电开启，`HUAWEIAV03` 活动模式为 3200×1600 @ 90 Hz。01:34:54 至 01:37:56（香港时间）的 19 次只读采样中，电量显示 30%，电量计下降 8.8 mAh，折算平均净放电约 174 mA。瞬时净电流介于 −1.72 A 和 +0.31 A，共 6 次为正。Android 报告的最大充电电流和电压全程为 0，当前线盒的镜像摘要、上游合同及手机口的 VBUS 电流均未读出。采样不控制前台负载，电量计差值只能量化本次净变化。

Android 热状态曾到 4，缓存的 `SKIN` 传感器为 47.3 °C，后来回落到状态 3。手机另报 `batteryCurrentEvent=0x40008000`。较早公开的三星内核将其中 `0x8000` 命名为 AICL（输入限流），Fold7 当前版本的位定义尚未核对。该读数值得与手机口 VBUS 压降和实际合同同步验证。 [Android 热状态定义](https://developer.android.com/reference/android/os/PowerManager#THERMAL_STATUS_CRITICAL) · [较早三星内核电流事件定义](https://github.com/ianmacd/d2s/blob/master/drivers/battery_v2/include/sec_battery.h)

线盒若在 Android USB Host 中暴露 `2109:0105` 运行态接口，可沿用现有只读寄存器通道做快速筛查。离线已定位到 `0x294F–0x2950`（上游第一个 PDO 的电流）、`0x297C–0x297F`（上游 RDO 的工作和最大电流）、`0x286D–0x286E`（手机侧第一档电流）和 `0x289B–0x289E`（手机的 RDO 工作和最大电流），本组字段均为大端、单位 10 mA。连续读取要检查前后状态并保留时间戳，这些缓存会被后续协商改写。手机本次正常外显时未在 USB 诊断输出找到该接口。 [只读寄存器通道实现](../tools/cable.py)

后续台架先核对两个 5 V 合同，确认辅助口是否签了 3 A、手机是否请求并完成 2 A。若手机合同已成立而 VBUS 下陷，可同步检查 RT9471 的 `STAT1 (0x11)` 位 7、6、5，依次对应输入电压调节、输入电流调节与芯片热调节。若手机口电压稳定但取电偏低，优先对照相同负载下 Fold7 的热状态和电流事件。 [RT9471 状态寄存器](https://www.richtek.com/content/dam/richtek/data/en/resources/product-specifications/rt94/rt9471-rt9471d/product-data-sheets/pdf/DS9471D-04.pdf#page=44)

## 怎样判断能不能充得更快

1. **先做供电 A/B。** 维持 C9.53.6、同一眼镜亮度、同一 XR 应用和相同手机主屏设置，在相近的中段电量和温度下，分别试现有电源与标准 USB-C 5 V / 3 A 电源。每次先接辅助电源，再接已解锁的 Fold7。若 5 V / 3 A 组的手机净放电减少，说明供电链余量在当前用法有作用。若能确认手机仍为 `source/host`，应先排查辅助供电和电源角色切换。过去的 2 A 镜像成功记录曾读到 `sink/host`，本次 C9.53.6 要单独核对。 [Fold7 以往角色实测](../research/evidence/fold7-original-2a-openxr-20261126.json)
2. **区分总输入、手机输入和手机电池净变化。** 辅助口功率表读的是整套总取电。手机线上若要抓合同和功率，分析仪需保留 CC、DP Alt Mode 和 USB 数据直通。没有该仪器时，至少用无线 ADB 比较同样负载下 10 分钟的 `Charge counter` 变化和温度，连续下降能量化净放电。`Max charging current` 是系统上报的上限字段，电池 `Voltage` 是手机电池电压。Android 的 `BATTERY_PROPERTY_CURRENT_NOW` 如能读到，其符号定义为正值净充入、负值净放电。 [Android BatteryManager](https://developer.android.com/reference/android/os/BatteryManager.html) · [AOSP 电源诊断字段](https://android.googlesource.com/platform/frameworks/base.git/%2B/20f124b2b1a7e9b46ede64e2bfdd6a653ba2644a/services/core/java/com/android/server/BatteryService.java)
3. **根据测点选改动。** 若 RT9471 已碰到 1.5 A 的输入限制或出现输入降压，而手机还没取到现有约定的电流，可在 C9.53.6 上对照输入限流，保留 3.9 V SYS 和新版降压初始化。若手机已接近实际签订的 5 V 档位仍净放电，原线要提高手机取电需同时核对余量并提高手机侧源能力。5 V / 2.4 A 输入按铭牌仅 12 W，若给手机承诺 5 V / 2 A，理论上只余 2 W 给眼镜、线盒和损耗。用户此前转述技术核对为整板支持 5 V / 3 A 持续供电。手机支路额定值和眼镜带载功率仍待测。降低手机主屏亮度与不需要的独立 120 Hz，可作为保留原线时的负载对照，眼镜时序按读回单独记录。 [原厂线配电节点](cv10-original-cable-handoff-20261126/c9526-power-and-buses.md) · [三星关于负载与发热的说明](https://www.samsung.com/us/support/troubleshoot/TSG10013287/)

无线 ADB 已连接时，可从仓库电脑读以下状态。用实际 Fold7 序列号替换示例值，记录开始和结束的电池状态及时间。

```powershell
adb devices -l
$foldSerial = '<Fold7 无线 ADB 序列号>'
adb -s $foldSerial shell dumpsys usb | Select-String 'powerRole|dataRole|mode='
adb -s $foldSerial shell dumpsys battery
```

## 更高功率的接法

如果目标是在 XR 高负载下持续让 Fold7 电量上升，可将带 PD 供电的全功能 USB-C 转接器作为独立方案验证。验收点是手机侧获得更高档的 PD/PPS、维持 `sink/host`、眼镜收到 3200×1600 @ 90 Hz 且能枚举控制和 IMU。转接器上游标称的总功率只能作为选型信息，实际应核对它在手机口提供的档位。VESA 定义下游 USB-C 可以同时传 DP Alt Mode、USB 数据与供电。三星也说明，USB 口已接线时无线充电可能不可用。 [VESA DisplayPort Alt Mode FAQ](https://www.displayport.org/faq/) · [三星有线接入与无线充电说明](https://www.samsung.com/us/support/troubleshoot/TSG10013508/)
