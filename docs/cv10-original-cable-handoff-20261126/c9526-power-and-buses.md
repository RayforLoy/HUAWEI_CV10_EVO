# CV10 原厂手机线 C9.52.6 供电与总线研究

2026-11-26，香港时间。**C9.52.6 能用 USB-PD 协商供电和切换角色。原版已追到的手机供电路径只发布 5 V 固定档，无法把充电器的 9 V 或 PPS 档透传给手机。** 线盒内的 VL105 管理三组 Type-C 端口寄存器，并通过同一 I²C 主控访问 RT9471 充电芯片和一颗高度吻合 RT9426 系列的电量计。华为也将原厂线的边玩边充定义为普通充电，辅助口使用 5 V / 2 A 规格的电源。 [华为供电说明](https://consumer.huawei.com/cn/support/content/zh-cn00757290/) · [VL105 芯片资料](https://www.via-labs.com/product_show.php?id=98)

样本为群友备份 `firmware_update/firmware/cable/stock/CV10-cable-C9.52.6.bin`，49,152 字节，版本字段 `0C 09 52 06`，CRC-16/USB `2DCB`，SHA-256 `1ebf1217d0dda526f64ed3b15504db409fbdf25bc866f0fbebb874adcd00485a`。反汇编使用 Ghidra SLEIGH 的 `8051:BE:16:default`，指令地址为裸镜像文件偏移。`XDATA` 表示 8051 `MOVX` 地址，`IRAM` 表示片内 RAM。本轮以离线机器码和模拟回放为主，实机信息引用既有接线记录。 [两版分析与样本](vl105-pd-analysis.md)

## 线盒控制的电源路径

| 电源路径或节点 | 固件和实机依据 |
| --- | --- |
| 手机端 VBUS | 辅助 5 V 接好时，刷原版 C9.52.6 的 P40 Pro+ 实报 `power sink / data host`，拔辅助电源再冷插时变为 `source / host`。固件也有构造 `PR_Swap`（`0x87AA–0x87B5`）与独立 `DR_Swap` 的路径。手机能在受电时维持数据主机角色。 [P40 接线与角色原始记录](../../research/evidence/p40-original-c9526-power-roles.txt) |
| 辅助口 VBUS | 华为定义为独立 5 V 输入，为手机与眼镜供电。线控固件在端口 1 分支设置 `XDATA[2DFF].1`（`0x221E–0x2229`）。C9.49.6 的线盒单接电脑时原值 `81`，插辅助 5 V 后变 `83`，支持将固件逻辑端口 1 对应到辅助口。该位反映端口事件。 [官方接法](https://consumer.huawei.com/cn/support/content/zh-cn00757290/) · [辅助输入实测](../../research/evidence/cable-external-input-20261126.json) |
| 眼镜端 VBUS | 逻辑端口 2 的分支可设置 `XDATA[2DFF].2`（`0x23BF–0x23CA`），源能力构造器也能给此端口生成 5 V 档。结合接线推定它对应眼镜端。辅口空置时整机可由手机或 PC 供电。光学或 USB 枚举只能确认各功能曾运行，眼镜端带载电压尚无波形。 [公司电脑与直连对照](company-pc.md) |
| RT9471 `VBUS/VAC` 输入 | `0xA24C–0xA263` 读回并将 `RT9471:04` 恢复到 `46`，即 MIVR 4.50 V、输入过压门限 6.35 V。`0xAE2F–0xAE38` 把 `RT9471:03` 配为 1.00 A 固定输入限流。6.35 V 适用于 RT9471 自己的输入，外部端口之间的直通、开关和隔离连线仍待确认。 [RT9471 寄存器](https://www.richtek.com/content/dam/richtek/data/en/resources/product-specifications/rt94/rt9471-rt9471d/product-data-sheets/pdf/DS9471D-04.pdf#page=38) |
| RT9471 `SYS/VSYS` 系统轨 | `0xAE17–0xAE1D` 写 `REGU=09`，配置系统最低调节电压 3.50 V、结温调节阈值 100 °C。按器件电源路径，系统轨可由输入降压供电，也可经 BATFET 从电池取电。3.50 V 是配置下限，板上负载归属及瞬态电压待测。 [电源路径与 VSYS_MIN](https://www.richtek.com/content/dam/richtek/data/en/resources/product-specifications/rt94/rt9471-rt9471d/product-data-sheets/pdf/DS9471D-04.pdf#page=26) |
| RT9471 `BAT` 单节电芯轨 | 启动写 `VCHG=32`、`ICHG=09`、`EOC=02`，分别为 4.40 V 调节目标、450 mA 恒流段设定、50 mA 终止门限且启用充电终止（`0xADFC–0xAE14`）。`0xA1C8–0xA1EB` 在电量 `<40` 时允许充电，在 `>60` 时清 `CHG_EN`，`FF` 会落入后者。保护分支还可写 `FUNCTION=81/A1`（`0x81F8–0x8207`），请求断开 BATFET，`A1` 另外置高阻位。现有可见写路径未见直接设 `OTG_EN` 或改 `PRECHG` 的指令。 [电芯轨与保护对照](vl105-pd-analysis.md#从实机身份字节识别充电芯片) · [RT9471 充电配置](https://www.richtek.com/content/dam/richtek/data/en/resources/product-specifications/rt94/rt9471-rt9471d/product-data-sheets/pdf/DS9471D-04.pdf#page=40) |
| 内部偏置与 VCONN | RT9471 另有 `REGN` 偏置 LDO、`PMID` 与 `SW` 开关电源节点。VL105 芯片定义有 5 V→3.3 V 与 3.3 V→1.8 V 两级 LDO，以及为线缆电子器件供电的 VCONN 开关。`0x87CE–0x87DC` 构造 `VCONN_Swap`。这些器件级节点的实际接线和负载仍待测。 [RT9471 引脚与电路](https://www.richtek.com/content/dam/richtek/data/en/resources/product-specifications/rt94/rt9471-rt9471d/product-data-sheets/pdf/DS9471D-04.pdf#page=4) · [VIA 功能表](https://www.via-labs.com/product_show.php?id=98) |

三组 VL105 端口寄存器从 `XDATA[1000]`、`[1200]`、`[1400]` 开始，步长 `0x200`，启动时可以看到并列写入（如 `0xA4D6–0xA51A`）。`0x3B40` 起的六状态流程能在逻辑端口 1 和 2 各控制一组寄存器位，分别为 `XDATA[0003].3` 和 `XDATA[011B].2`。C9.52.6 还有一条单独延迟后脉冲 `XDATA[0003].3` 的路径（`0xA337–0xA3A5`）。这些位与真实开关管、放电和复位信号的对应关系需要线盒 PCB 走线或示波测量。已有 C9.49.6 的带载掉线记录中，两组已布置的端口脉冲与 BATFET 写入追踪均未命中。 [两版脉冲和 C9.49.6 追踪](vl105-pd-analysis.md)

## 手机侧 PD 档位

### 原版怎样处理充电器的能力列表

1. `0x2BBE` 调用 `0x65EE` 导入另一端口的 `Source_Capabilities`，准备给手机侧使用。`0x65F7` 将对象数量写入 `IRAM[43]`，下一条 `0x65F9` 立即执行 `MOV 43h,#01h`。随后 `0x663A–0x6745` 按此数量解码 PDO，只处理第一个。合规的电源将 5 V Fixed PDO 放在首位。普通分支在 `0x2BF1–0x2BFA` 向供电端选第 1 个 PDO 并构造 `Request`。 [PDO 定义](https://github.com/torvalds/linux/blob/v6.12/include/linux/usb/pd.h) · [Linux USB PD ABI 对首个 PDO 的说明](https://github.com/torvalds/linux/blob/v6.12/Documentation/ABI/testing/sysfs-class-usb_power_delivery)
2. `0x5BFE` 给逻辑端口 0 构造 `Source_Capabilities`。`0x5C67` 调用 `0x6C52` 转换导入表，`0x5DA4–0x5DB2` 经 `XDATA[1020–1022]` 写发送寄存器。转换器里留有筛除 APDO 和保留第二个 **9 V Fixed PDO** 的代码。`0x6D53–0x6D73` 要求已导入至少两个对象，且第二项为固定电压、字段等于 `0x00B4`（180 × 50 mV）。原版在上一步已把导入数量压到一项。C9.49.6 同样在 `0x661C–0x6620` 先写读到的数量，再把它改为 1。
3. 首次供电与导入后的电流字段取决于状态机。`0x5CBD–0x5CD9` 的端口 0 回退档为 5 V / 1 A，端口 2 构造器有独立的 5 V / 0.9 A 回退档（`0x64A6–0x64CA`）。这些值是指定分支算出的协议字段。实机记录只确认 P40 电源角色，手机和眼镜实际分得的电流、手机端 `Request / Accept / PS_RDY` 和最终合同仍缺原始 CC 记录。 [P40 角色记录](../../research/evidence/p40-original-c9526-power-roles.txt)

### 离线回放结果

用 emu8051（提交 `5dc681275151c4a5d7b85ec9ff4ceb1b25abd5a8`）执行原镜像中的导入和发送函数。供电端能力数组模拟三档 `0001912C`（5 V / 3 A）、`0002D12C`（9 V / 3 A）和 `C0DC213C`（PPS）。在端口 1 的接收对象缓存 `XDATA[2AF8]` 放入小端 PDO，令 `XDATA[2A54]=3`，以 `R7=1` 调用 `0x65EE`。端口就绪标志由回放设置，捕获其后的发送寄存器写入。表中是固件写入的头和数据，硬件自动填充、CC 传输和真实电源均不在模拟范围内。 [emu8051 开源实现](https://github.com/jarikomppa/emu8051)

| 回放条件 | 写入帧头 | 数据与含义 |
| --- | --- | --- |
| 端口 0 回退分支 | `41 10` | `26019064`，只发布 5 V / 1 A |
| 模拟充电器给出 5 V、9 V、PPS，原版完成导入后给端口 0 发布 | `41 10` | `26019096`，只发布 5 V / 1.5 A。导入计数从 3 变为 1 |
| 按初始分支向模拟充电器请求 | `42 10` | `1304B12C`，请求对象 1，即输入列表的 5 V |
| 端口 2 回退分支 | `41 10` | `2601905A`，只发布 5 V / 0.9 A |
| 模拟器手动预置 9 V 项和 APDO 类型，并令转换器收到三项 | `41 20` | `26019096`、`0002D12C`，得到两个固定 PDO，APDO 被滤掉。这一行验证代码分支，条件由模拟器注入 |

对 `C9.52.6-2A-input.bin` 重跑全部用例，PD 发送寄存器结果逐字节相同。原版与 2 A 版的差异为 `0xAE30` 的立即数 `14→28` 和最后两个 CRC 字节。`0xAE30` 控制 RT9471 的 `IAICR`，修改后输入上限为 2.00 A。已有 5 V / 2 A 供电点亮记录来自另一个以 C9.49.6 为基线的观测镜像，C9.52.6 2 A 版的 PD 结论来自离线回放。 [Windows 输入限流与镜片记录](../../research/evidence/pc-original-2a-input-20261126.json) · [Fold7 与 P40 对照](../../research/evidence/fold7-original-2a-openxr-20261126.json)

## 各条总线上的设备

| 总线或接口 | 已识别的端点及证据 |
| --- | --- |
| 线盒 I²C 主控 | `0x89CE` 读、`0x994A` 单字节写和 `0x999F` 双字节写使用同一组 `XDATA[0060–0067]`。`0x95C5` 将 7 位地址左移后加入读写位。追踪到两种从地址 `0x53`、`0x55`，目前无其他板载从地址的正证据。 |
| I²C `0x53` 充电芯片 | `0xA193–0xA19C` 读 `INFO 0B` 存入 `2E00`。本机 C9.49.6 实读 `69`，其中设备 ID `0D` 对应 **Richtek RT9471**。C9.52.6 对同地址写入的配置和初始化序列一致。另见电源路径、温度状态与 IRQ 读取。 [型号识别和实机读数](vl105-pd-analysis.md#从实机身份字节识别充电芯片) |
| I²C `0x55` 电量计 | 同时匹配 RT9426/RT9426A 的 7 位地址、`2C` SOC、`66/67` 平均温度、`0A/0B` 与 `0C/0D` 状态标志、`36/37` IRQ、`3E/3F` 扩展控制与 `40` 段扩展寄存器访问。C9.52.6 的采样在 `0xA100–0xA175` 及 `0xA188–0xA1B0`，配置路径在 `0xA7D6–0xA887` 和 `0xAB32` 起的写辅助函数。型号定位到 **RT9426 系列**，具体变体待芯片丝印或有效身份读数。资料表还列出电芯电压、实际电流和容量寄存器，现有线控普通诊断只有固件已缓存的字段。 [RT9426 寄存器表](https://www.richtek.com/assets/product_file/RT9426/DS9426-02.pdf#page=18) · [RT9426A 寄存器表与设备 ID](https://www.richtek.com/content/dam/richtek/data/en/resources/product-specifications/rt94/rt9426a/product-data-sheets/pdf/DS9426A-01.pdf#page=18) |
| 三路 Type-C CC/PD | 线盒在手机或 PC、辅助充电器、头显之间分别终结对应端口的 CC 事务。固件内有 PD 请求、角色交换、DP 结构化 VDM 和线缆身份消息，端口 0 为手机或 PC 侧，端口 1 与 2 的物理对应见上表。当前缺少三端同步抓包。 [DP 和线缆身份机器码](../cable-firmware-research.md#手机与线缆之间的-usb-pd-和-dp-alt-mode) |
| USB 2.0 | 线盒独立接主机可见 VL105 的 `2109:0105` Billboard 和 EP0。接 CV10 后，眼镜一侧的 `2109:2211` 下挂 `12D1:1092` 音频（口 1）、`12D1:107E` 控制及 PCUI（口 2）、`2109:8888` VIA HID（口 5）。普通 C-C 直连也枚举到这三个子设备。 [本线 Billboard 快照](../../research/evidence/cable-c9496-diagnostics.json) · [眼镜 USB 拓扑](company-pc.md) |
| DP 主链路及 AUX | 主机为显示源，眼镜是 `HUAWEIAV03` 显示端。C9.52.6 镜像包括 DP SVID `FF01` 的发现、状态和配置 VDO。Fold7 原厂线和普通 C-C 的对照均记录配置 C、四条通道和训练成功。眼镜端 AUX/DDC 曾返回 EDID 片段。线盒板级有源高速开关的料号和接线仍待核实。 [Fold7 DP 训练记录](../../research/evidence/fold7-original-vs-direct-dp.txt) · [AUX/DDC 对照](pd-proximity.md) |
| 固件存储与 UART | VL105 型录支持外部 SPI Flash 或与 VIA Hub 共用 Flash，维护态已能从线盒双读镜像。实物的 Flash 型号、独占或共用接法、UART 焊盘及串口日志仍待确认。现有 USB 枚举给出了 Billboard 接口。 [导出实测](../cable.md) · [VIA 芯片资料](https://www.via-labs.com/product_show.php?id=98) |

## 固件研究小结

- **线盒负责连接与供电协同。** VL105 做 Type-C/PD、DP Alt Mode、线缆信息交换和 USB Billboard 维护，RT9471 执行电芯充电及电源路径控制，`0x55` 电量计提供电量、温度与保护相关读数。镜片显示、背光、光感、头显音频与 PCUI 的实现分属头显自身。 [头显固件与佩戴事件](headset-pd-analysis.md) · [运行态诊断总表](../cable-firmware-research.md)
- **电量和温度的未知值来自同一条计量链。** `55:2C` 和 `55:66/67` 直接进入 `2DFE` 及 `2E01/2E02`，运行态读回无独立 I²C 应答标志。历史 C9.49.6 样本恢复运行后短暂出现 1% 和 25.1 °C，之后回到 `FF/FFFF`，同期 `53:0B` 仍为 `69`。未知值可以与电量计供电、应答或状态异常相容，现有测点无法判定电芯电压或过放程度。充电许可位、BATFET 和 OTG 升压也各有独立条件。 [维护前后原始样本](../../research/evidence/cable-c9496-gauge-after-rom-20261126.json) · [充电阶段与输入限流对照](charging-ab.md)
- **C9.52.6 与 C9.49.6 的共同策略和新增行为都有定位。** 两者共有 1 A 默认输入限流、单 PDO 导入、RT9471 与电量计路径及端口切换。C9.52.6 增加独立延迟端口脉冲，原厂更新界面写明散热背夹适配。两者的已知差异和改动功能有各自的证据，具体哪条路径对应散热背夹仍待验证。C9.53.6 目前只有售后和群记录线索，缺可校验镜像。 [原厂更新界面与版本比较](../cable-firmware-research.md) · [两版端口状态机](vl105-pd-analysis.md)

若要把板级供电图和协议结果补全，缺的直接测量是手机侧与辅助口的 CC 合同、眼镜端带载 VBUS、RT9471 `VAC/SYS/BAT` 与两组端口控制位的实际接线。现有 EP0 和头显 PCUI 可以提供辅助时间点，必要的电压与协议证据仍来自电气测量。 [现有测点和判别条件](vl105-pd-analysis.md#对下一次实测的判别预测)
