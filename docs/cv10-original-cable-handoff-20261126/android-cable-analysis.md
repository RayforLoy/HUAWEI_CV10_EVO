# 华为 Android 上位机如何识别原厂线和处理掉线

2026-11-26 离线复核。原厂 P40 在 VR 系统服务和桌面客户端均已启动的情况下，仍可复现原厂线接入后音频和头显控制消失。同一台电脑以相同原生时序驱动同一副眼镜时，普通 C-C 能显示交替图案，原厂线开启视频后约两秒丢失 USB 下游。现有证据足以排除“仅因电脑缺少华为 Android 服务”这一解释。哪段硬件链路先复位、带载电压如何变化，尚无同步电气记录。[P40 服务与 USB 时间线](../../research/evidence/p40-direct-original-usb-vr-20261126.txt) · [P40 原厂线供电角色](../../research/evidence/p40-original-c9526-power-roles.txt) · [Windows 对照](company-pc.md)

## 对照 Windows COM19 的上行事件

07 号 VRService 的 `VRDeviceNodeMonitor.analyzeVcomBuffer` 位于 DEX `0x1D8234`。它调用 `verifyData`（`0x1D8134`）后，把缓冲区第 8 字节按无符号数分派。从 DEX 文件偏移 `0x1D8320` 的 packed-switch 表直接复算，得到下表。所有偏移从一条完整帧的第 0 字节计算，用于识别的头字段为 `b[0]=01, b[1]=42, b[2]=00, b[4]=01, b[5]=01`。读取串口时须跨 read 拼接帧；读取 b[12] 之前至少须有 13 个实际字节。PC 的 COM 编号随安装映射变化。

| b[8] | 字段 | 07 号系统服务的具体动作 |
| --- | --- | --- |
| 02 接近 | b[12] | 值 1 报佩戴，0 报摘下，其余记无效。满足 VR 状态条件时 `handleHelmetUp` / `handleHelmetDown` 会分别发面板开启 / 关闭命令，检查完整应答。摘下关屏的 JNI 调用在 DEX `0x1D2AE8` 的方法内。 |
| 03 心跳 | 无额外字段参与处理 | `processHeartbeat`（`0x1D8834`）记录手机 uptime。此前判为掉线时发送恢复消息，最终通知桌面 1008。 |
| 04 头显异常 | 服务不读取异常子码 | `processException`（`0x1D86A8`）发工作消息 20；`handleHelmetException`（`0x1D2C08`）向桌面发 1010。 |
| 05 电量 | b[12]，无符号 | `processBattery`（`0x1D8610`）把 0–4 转为工作消息 18，服务再向桌面发 1007；5–19 转为 17，再向桌面发 1006。20–255 在这段告警逻辑中不触发上述两种通知。05 号桌面处理这两个通知均先通知监听者，并可在 5000 ms 后再排同号消息。 |
| 06 耳机插拔 | **b[10]** | `processHeadset`（`0x1D86E0`）读取华为音频参数并按耳机状态处理音频路由。 |
| 07 过热 | b[12]，无符号等级 | `processOverHot`（`0x1D88C8`）发工作消息 24。`handleHelmetOverHot`（`0x1D2C2C`）将等级透传给桌面 1012；仅在收到整数等级 2 时另排 30000 ms 后的退出消息 11。 |

两秒心跳的方向可由两端调用直接确认。`VRHeartBeatMonitor`（`0x1D8AA4`）在接到第一次上行心跳后检查自上次上行的经过时间。超过 2000 ms 且满足当前状态条件时发消息 10，`handleHeartbeatDisconnect`（`0x1D2AC4`）只向桌面 Messenger 发 1009；超过 10000 ms 在相应状态下才通知退出。该线程没有写往线控或头显的保活包。另一个 2000 ms 定时在 `doHelmetPrepare`（`0x1D2610`），作用是等待显示添加闩锁，随后用 Messenger 1002 向桌面报告准备完成。COM19 上出现 03 帧，说明到该时刻头显的事件通道可读。

电量需要按来源分开读。初始查询 `initGlassBattery`（`0x1D8368`）收到负数就返回；成功返回的数才送给 `processBattery`。P40 的一次记录在原厂亮度写入成功后报出电池读取 EPIPE。这个失败、线控独立 Billboard 的 FF、电缆信息字符串中的 255、以及事件 05 的 b[12] 都是不同读数。当前证据不能把它们换算成同一个电量或认定某次必定触发了关机。[P40 初始化记录](../../research/evidence/p40-original-c9526-power-roles.txt) · [线缆字段来源](../firmware-resource-analysis.md)

### 把线缆回包中的 255 替换成 100 的离线对照

取实机 `^CABLEINFO=10C094906255+280`，复制一份，仅在副本将三位电量文本换成 `100`。按 P40 实装桌面 11.1.0.337 的 `CableInfo` 构造函数回放，两个输入都解析为线型 1、版本 `0C094906`。该构造函数按固定宽度截取末尾两段，实测文本得到 `25` 和 `5+28`，模拟文本得到 `10` 和 `0+28`。在已检查的桌面 DEX 中，这两字段只有写入，未找到直接读取它们的指令。独立的 VRService 电量事件走上文的 `processBattery`，将 100 和 255 分别代入该分支，均记录日志并返回，不发低电量消息。两种输入来源不同。这一对照只覆盖上述安卓路径，未向设备发送模拟值。[原始回包与客户端版本](../../research/evidence/fold7-original-firmware-retest-20261126.txt)

Windows 的同次实机记录先读到 255，随后开屏命令仍收到 `OK`；约 10 ms 后第一次串口读取失败。该返回值证明头显接受了命令，未确认面板供电或镜片成像。当前证据无法把掉线归因于 VL105 软件主动切断供电。[同次开屏与串口事件](../../research/evidence/pc-original-wear-reply-20261126.txt)

## 设备初识、换模式与断开

- **头显接入。** 07 号服务据 USB 广播识别头显。正常 `handleGlassIn`（`0x1D2930`）最多等显示添加闩锁 5000 ms，随后进入初始化。`VRDeviceNodeMonitor.start`（`0x1D89D0`）先初始化接近、温控、亮度、接近读回、耳机和电池，然后读取上行 VCOM。实际可跨平台复现的步骤包括验证 PCUI 型号、识别接近与佩戴、接收面板开屏应答、被动接收第二串口事件，独立记录 GPU 当前活动信号和成像。[原厂初始化与 HID 布局](../firmware-resource-analysis.md) · [PCUI 接口映射](../usb-panel-research.md)
- **线缆识别。** 04 号 VRHandle 的 `m1.o.m`（DEX `0x289E8C`）通过 Android USB 枚举精确匹配 `2109:0105`；`m1.t.e`（`0x28B100`）请求该设备权限，`m1.t.f`（`0x28B00C`）判断在线。实际头显接入后可由 05 号桌面经 PCUI 查询 `AT^CABLEINFO?`；该库的 `getCableInfo`、`upgradeCable`、`setVrScreenOn` 和 `setVrScreenOff` 分别位于 ELF VA `0x84E0`、`0x874C`、`0x895C`、`0x8B6C`。
- **进入线缆维护模式。** 05 号桌面 `u2.b.onDisplayRemoved`（DEX `0x18BB4C`）核对显示 ID 和升级状态后才调用 `VrHelmetConnector.upgradeCable`。`AT^CABLESWITCHUSB` 属于这条维护路径。`AT^SETSOURCE` 在七个 APK 的普通 DEX 和 SO 中未命中完整字面值；07 号事件分派也无定义为“换源”的类型。来源设置的确切行为以 PCUI 的设置、读回和光学对照为准，反射、动态解包资源、系统 HAL 和 MCU 的其他行为均未穷尽。[维护模式固件处理](../firmware-resource-analysis.md) · [电脑上的来源对照](company-pc.md)
- **整机掉线。** 07 号 `handleGlassOut`（`0x1D299C`）调用 `notifyStaticCheck`（`0x1D3158`）。正常路径在 500 ms 后排消息 16；升级等待状态可等 10000 ms，正在升级的另一分支则跳过处理。`handleCheckStatic`（`0x1D2850`）按当前状态再检查或进入 `exit`（`0x1D268C`）。退出撤销 Android VR 模式、解绑桌面、恢复手机环境并停监视器。已追踪的这些方法没有发 USB 端口复位或关闭 VBUS；07 号 `onDisplayRemoved`（`0x1D346C`）处理显示闩锁、广播及亮度恢复。与此相对，佩戴状态触发的 `SWITCHSCREEN=0` 是明确存在的头显面板控制。手机内核、PD 控制器或眼镜固件自主复位仍属未排除的机制。

可将现有 Windows 同步录制中的首个 04/05/07 事件、最后一个 03、GPU 模式应用完成、Windows 端口 1/2/5 首次报告无设备排在同一单调时钟上。先在普通 C-C 接法验证接近 02 和稳定心跳 03，再用相同解析器处理原厂线。若最后心跳后直接出现 USB 断开、没有完整异常帧，可报告“捕获窗口未见预警”；设备可能在传出下一帧前已失联。要确定带载供电瞬断仍需眼镜侧电压或 PD/CC 记录。

## 复核样本

| 按资源编号及成员定位 | SHA-256 |
| --- | --- |
| 04 号 APK 的 classes.dex | `68ec4ef220804fd5545c335534993ba98ad703230cc0bd7b382cda7e26aa75bd` |
| 05 号 APK 的 lib/armeabi-v7a/libvrconnector.so | `55a51aead0c624d700b08189c5fb4fa55a6f4f11b2a9cb13f4129c719b50b16e` |
| 07 号 APK 的 classes.dex | `c24c0f865ffc17737ed450af85ff8e6bc38f74d43f3cb41f19043d305ed68820` |
| 07 号 APK 的 lib/armeabi-v7a/libvrservice.so | `f447cdd956ed1b1f9c4cbe9d18eed19dfe43d00bdf7413b2924da2ff15fc0176` |

DEX 地址采用 Android SDK dexdump 的方法 code_item 文件偏移。05 号 DEX 的部分调试参数流报告格式异常；上文引用已解出的调用指令。07 号服务样本版本为 12.0.0.302，P40 实装为 13.0.0.300；上述偏移只适用于表列样本。[P40 软件版本核验](../device-openxr-check.md)

## 佩戴触发与背光供电

这版眼镜没有从 `AT^TBATVOLT` 读出电压的实现。用 `halliday.dfu` 的解压入口（文件 `0xB0F7D`）及段描述符（`0xB9E51`）还原初始 SRAM 后，`0x200008AC` 的 TBATVOLT 表项与 `0x200008DC`、`0x200008E4` 的 VBUS、VBUS? 表项均指向 Thumb 指针 `0x080A1F1B`。实际处理代码在文件 `0x8243F`，将 r0–r3 全部置零后调用公共应答函数并返回。这里无 ADC、I²C 读数或单位。TBATCURRENT、TBATTEMP、TBATDATA?、IINLIMIT? 也走同一处理器。固件中另有 TCPC 状态及 PD Source/Sink 的 mV、mA 调试字符串；本轮没有找到把眼镜负载端模拟电压送回普通主机的公共只读接口。PCUI 的 TYPECSTATE?、线控 CABLEINFO?、音频/控制的 USB 连接状态均不能替代带载电压测量。

**亮度有普通 HID 通道。** 07 号 `IoSetBrightness` 的 ARM 代码在 ELF VA `0x8478–0x8490` 组装 `03 level` 两字节，经 `ioctl(0xC0024806)` 发给头显 HID，主机包装层允许 0–9。眼镜 USB 的 HID 类请求走 107e 的接口 3。等价原始 EP0 设置为 `bmRequestType=0x21, bRequest=9, wValue=0x0303, wIndex=3`，负载 `03 level`；读回为 `0xA1, 1, 0x030A, 3`，请求一个状态字节。使用 Windows 原生 HID API 时，其缓冲区包含 report ID，长度与填充应遵循本机 HID collection 的能力描述；上述数值为 USB 控制传输层。COM18 上的开屏成功和 COM19 上的事件无法确认 HID 写入成功。

设备侧 `receive_hid_cmd` 文件 `0x64E21` 按首字节 03 跳到 `0x64F2F`，要求首字节之后还有负载。实际 `set_lcd_backlight_level`（`0x729C5`）只接受 0–4，`0x72A0D` **先写软件缓存**，`0x72A0F` 才检查佩戴是否为 1，并在近场分支调用执行函数 `0x7232D`。该函数在 `0x72337` 和 `0x72345` 查相同的初始 SRAM 表 `0x20006684`，等级 0–4 对应的五个字节为十进制 **49、54、58、63、68**。0 档仍有非零表项；这些值没有可据以换算毫安的校准。GET_REPORT 0A 从 `0x72A79` 读缓存，因此远离时写入成功和回读相符，只能确认目标档位。

Fold7 已在普通 C-C 上验证亮度 1 可成像；C9.49.6、C9.52.6 原厂线均曾成功回读档位 1、随后仍失去控制接口。对于这台 Windows PC，宜比较固定视频时序和固定遮挡动作下，不同目标档位的掉线延迟及光学结果。若等级 0 也触发掉线，仍需将近场启用产生的电气瞬态与其他触发因素区分。记录原档位并在稳定链路恢复、回读即可。[Fold7 亮度与 USB 逐项实测](../../research/evidence/fold7-original-firmware-retest-20261126.txt)

**Windows HID 包装与回读。** 同一固件的初始 SRAM `0x2000A618` 含长度 68 字节的 HID 报告描述符，Feature ID 04 声明 127 个八位数据字段；连同 ID 共 128 字节。固件 OUT 完成分支 `0x56325–0x5633D` 检查长度 128、首字节 04，取第 1 字节为内层长度，再从第 2 字节取内层指令。因此在该 collection 上，`HidD_SetFeature` 的亮度包候选为 `04 02 03 level` 后补零至 128 字节。应先在普通 C-C 直连和固定白图条件下验证其光学效果。

这个包装只有 SET 方向。内层 `receive_hid_cmd` 首字节分派中没有 0A；将 0A 包入 04 不会触发亮度查询。原始 `GET_REPORT` 通过 `0x650DD` 分派，04 的 1 字节读取返回接近，而 0A 的 1 字节读取才在 `0x65199` 调用 `0x72A79`。整个固件的直接 Thumb BL 指令中，这是亮度 getter 的唯一调用者。普通 PCUI 表中未见亮度查询，上行事件 02–07 也未定义亮度读回。要逐档验证缓存，可用已验证的 Android USB Host API 保存原值并在试验后恢复；单机 Windows 使用可正常成像的直连线、固定测试图和锁定曝光的摄像头，能够独立验证发包是否改变实际光输出。
