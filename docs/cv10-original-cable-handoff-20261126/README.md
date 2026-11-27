# 原厂手机线黑屏 · 公司电脑接手记录

**15:14 已在 Windows 上用原厂手机线点亮 CV10。** 外接 5 V / 2 A，RT9471 输入限流实读为 2.00 A。右眼拍到随输入变色的 `R ↑`，开屏后的 35 秒内 USB 保持在线。测试后已刷回原版并双读校验。[2 A 实验与右眼实拍](charging-ab.md#2-a-输入限流下原厂手机线在-windows-点亮-cv10)

**2026 年 11 月 26 日，香港时间。** 家中电脑的黑屏试验于 09:46:51 结束。公司电脑随后以原生 90 Hz 和原厂 PC 模式复测；12:14 在头显就绪后接入独立 PD 电源，佩戴时仍掉线。相同眼镜用普通 Gen 2 C-C 线直连，P40 Pro+ 可显示华为 VR 桌面，Fold7 可显示左右眼测试图，公司电脑可显示随输入变色的右眼图案。原厂线已刷回本线的 **C9.49.6**。此前的 C9.52.6 也出现过相同症状。[夜间报告及镜片照片](../cv10-original-cable-overnight-20261126.md) · [公司电脑实测](windows-host-startup.md) · [就绪后接电对照](pd-proximity.md#在头显就绪后接入辅助电源)

在家用电脑上，Windows 读到了眼镜的原生 EDID，头显也回复了开屏 `OK`，但主板 AMD 核显实际只输出 640×480。交替发送全屏洋红和绿色时，P40 拍到的双镜片均未随之变色。公司电脑若改用另一块 GPU，应重新记录其活动信号和镜片实拍。[电脑信号、开屏和光学对照](../../research/evidence/pc-original-cable-20261126.json)

## 最新定位

09:42，Fold7 经原厂线连接 CV10，转接盒保持外接 5 V。佩戴者确认双眼始终黑屏。手机选中 3200×1600、90 Hz，DP 两阶段训练成功，内核记录视频流启动。约 **2.14 秒后，手机的 USB 2 根端口 1 首先报告下游连接消失**。内核随即注销整棵集线器，随后 Android 才移除音频和头显控制设备。外屏仍在，手机保持受电和 USB 数据主机角色。[本轮原始日志摘录](evidence.txt)

当时根端口的 `status 0100, change 0001` 表示端口供电标志仍置位，连接位已清除，变化位是连接变化。该条记录的过流和挂起位均未置位。[Linux 对 USB 2.0 集线器端口状态的定义](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/usb/ch11.h#L113-L179)

掉线前约 3.76 秒，**手机端**充电芯片记录输入 273 mA、VBYP 4650 mV。掉线瞬间眼镜端的实际电压尚未测得。盒内电量和温度原始读数分别为 `FF` 和 `FFFF`，目前仍无法区分电芯老化、转接线供电瞬断和 USB 数据链路复位。[线控固件、电量与温度实测](../../research/evidence/fold7-original-firmware-retest-20261126.txt)

| 下游位置 | 正常直连可见 | 此次原厂线掉线后 |
| --- | --- | --- |
| `1-1`，VIA `2109:2211` 集线器 | 是 | 消失，约 1.90 秒后重新枚举 |
| `1-1.1`，`12d1:1092` 音频 | 是 | 消失，在此轮观察中未回来 |
| `1-1.2`，`12d1:107e` 头显控制、传感器 | 是 | 消失，在此轮观察中未回来 |
| `1-1.5`，VIA `2109:8888` HID | 是 | 集线器恢复约 0.68 秒后重新枚举 |

普通 C-C 直连也会出现这两个 VIA 设备。原厂转接线单独接主机时可见的是 `2109:0105` Billboard。区分这三个设备，才能判断一次重枚举究竟恢复了什么。[线缆设备身份](../cable-firmware-research.md) · [P40 的独立对照](../../research/evidence/p40-original-c9526-power-roles.txt)

## 09:30 之后已做的单项试验

| 操作 | 实测结果 |
| --- | --- |
| 保持 PC、原厂线和 5 V 接线，向头显发送 `AT^SETSOURCE=0` | 读回手机来源 0，25 秒内的 100 次检查均可枚举头显控制接口，Type-C 状态仍是 1。随后用 `AT^SETSOURCE=1` 恢复并读回 PC 来源 1。这只改变了头显上报的来源，没有重现手机掉线 |
| Fold7 在插线前临时停用 USB 音频自动路由 | 三星音频服务确认停用。控制设备于 09:42:28.001 加入 Android，图案于 09:42:28.030 提交，09:42:29.184 控制设备被移除。两眼持续黑。此轮仅记录到应用请求 USB 权限。先前用同一原厂线已有开屏 `OK` 后仍掉线的记录 |
| 外接 5 V 不动，请 Fold7 从受电／主机切到供电／主机 | 手机真实端口列出该组合，USB HAL 随后返回 `role switch failed, err:1`。整个观察期间仍为受电／主机 |
| 故障后仅关闭再开启手机口的 USB 数据 | 关闭时 DP 外屏仍在。恢复数据后只有集线器和第 5 口重新出现，音频及控制均未恢复 |
| 故障后单独将眼镜外屏电源设为 OFF，保持 OFF 再开关一次 USB 数据 | SurfaceFlinger 确认眼镜外屏已 OFF。结果仍只有集线器和第 5 口。随后恢复外屏 ON 并核验。**首次插入时就延迟外屏开启的对照尚未运行** |

USB 自动路由设置已恢复为原来的未设置值，USB 数据已启用，外屏电源覆盖已清除。Fold7 上的诊断 APK 已恢复为本轮开始时的版本并已停止运行，安装后在手机上读回 SHA-256 为 `307223fe9dc68f560e4831fb1e44819fd854f6c044ee7d2206df0032a238ff0e`。家用电脑保留实测可用的头显 MI_00 WinUSB 驱动。冻结时原厂线最后接在 Fold7 和 CV10 之间并保持外接 5 V。

## 公司电脑如何继续

1. 新电脑运行下面的命令取得协作分支及固定版本的子模块。已有干净工作树在同一分支时可用 `git pull --ff-only`，再运行 `git submodule update --init --recursive`。本轮上午实验开始时的主项目提交为 `efba860`，主项目发行标签仍为 `v0.1.1`。[跨电脑协作指南](../../AGENTS.md)

   ```powershell
   git clone --branch codex/cv10-phase1 --recurse-submodules https://github.com/RayforLoy/HUAWEI_CV10_EVO.git
   cd HUAWEI_CV10_EVO
   git status --short --branch
   git submodule status --recursive
   ```

2. 可在公司电脑先阅读随文的日志摘录。做实机对照时，将 Fold7 授权给该电脑的无线 ADB，让手机 USB-C 口留给眼镜。用 `adb devices -l` 找当日序列号。验证 Fold7 型号为 `SM-F9660` 后，按当前显示名、活动模式和 USB 拓扑认设备。显示 ID 和无线端口会随重连变化。

   ```powershell
   adb devices -l
   $foldSerial = Read-Host '输入 Fold7 的 ADB 序列号'
   adb -s $foldSerial shell getprop ro.product.model
   adb -s $foldSerial shell cmd display get-displays
   adb -s $foldSerial shell ls -1 /sys/bus/usb/devices
   ```

3. 下一项对照可以保持原厂线、5 V、手机和眼镜不变，在一次新的连接中推迟 Android 启用眼镜外屏，观察控制接口能否越过此前的掉线窗口。随附脚本的 `observe` 只记录，`delay` 会在新识别到 HUAWEIAV03 后立即请求 OFF，等待 12 秒再释放覆盖。两轮均只拔插眼镜端，按相同方向接回，在同样的佩戴或遮挡条件下对照。两种流程已用模拟的手机命令输出离线核验。首次连接时延迟开启外屏的效果仍待实机验证。[采集脚本](startup.sh)

   ```powershell
   adb -s $foldSerial push docs/cv10-original-cable-handoff-20261126/startup.sh /data/local/tmp/cv10-startup.sh
   adb -s $foldSerial shell sh /data/local/tmp/cv10-startup.sh observe | Tee-Object cv10-observe.txt
   adb -s $foldSerial shell sh /data/local/tmp/cv10-startup.sh delay | Tee-Object cv10-delay.txt
   ```

   每轮看到 `READY` 后再插拔。记录新显示 ID、眼镜外屏的实际 `powerMode`，以及音频和控制子口出现与消失的顺序。Android 只能在识别逻辑外屏后请求 OFF。若 OFF 晚于掉线，或采样未捕获两者顺序，这一轮就无法用来判断。需要更细时间线时，可在第二个终端于插入时运行 `adb -s $foldSerial bugreport cv10-attach.zip`。若脚本中断，可重新用 `cmd display get-displays` 核对 HUAWEIAV03 的当前非零 ID，再用 `adb -s $foldSerial shell cmd display power-reset <该ID>` 释放外屏电源覆盖。

4. 若控制接口能够保住，再用[仓库内的双眼图案及开屏工具](../../probe/Probe.java)或已验证的 Monado 样例进行镜片验收。记录恢复 ON 后两只华为 USB 设备是否持续在线、活动信号是否为 3200×1600，以及双眼能否实际看见并再次重现左右眼图案。一次 AT 应答或一张手机外显截图不足以确认修复。

## 公司电脑实测

独立 PD 电源下，眼镜在 90 Hz 视频和未佩戴状态下保持约 190 秒，仅遮住感应窗即可复现掉线。反过来先让眼镜报告已佩戴、延迟约 24 秒送视频，也得到相同结果。[新电源、佩戴与视频的交叉试验](pd-proximity.md)

11:36，按旧 Android 服务的佩戴分支在收到事件后发开屏，头显在约 3 ms 内回应，约 10 ms 后事件串口失联。右镜片持续黑屏。故障后关眼镜视频约 22 秒再恢复 90 Hz，音频、头显控制及显卡端的 DDC 读取都未恢复。[开屏应答和镜片记录](../../research/evidence/pc-original-wear-reply-20261126.txt)

11:45，断开辅助充电头后重新接电脑，线控蓝灯亮，真实佩戴后仍掉线。此次故障后仍可从 NVIDIA DDC 连读三次完整 EDID；USB 控制口消失，原音频口出现设备描述符请求失败、Code 43。[电脑单独供电对照](../../research/evidence/pc-original-host-power-20261126.txt)

已按 P40 编号收齐六种 APK。旧版 VR 手柄 10.0.0.374 明确访问线控，普通手柄服务和线缆升级使用不同的 USB 入口。各版本来源、签名、DEX 定位及还缺的首发样本见[六个历史 APK 与原厂线协议](legacy-android-suite.md)。

**待补的对照是另一根能点亮 CV10 的原厂手机线。** 现有 C9.52.6 镜像能比较代码；归档中的点亮试验和电量读数都来自本线或普通 C-C 线。P40 的华为 VR 手柄界面曾把本线当时的 C9.52.6 显示为「已是最新版本」。群文件的问答表提过 9.53.6，未随附该版本镜像或良品电量记录，也没有服务端发布范围的证明。[P40 当时的读数及界面](../../research/evidence/p40-original-c9526-power-roles.txt) · [群文件说明](../firmware-resource-analysis.md)

取得对照时，在同一根线上先确认 CV10 镜片可见画面，记下主机型号、是否外接电源和线版本，再记录该线的电量与原始温度。现有只读工具支持 C9.49.6 和 C9.52.6。其他版本可先保留正常运行时头显 `AT^CABLEINFO?` 的原始回复，温度显示 `+280` 有多种可能原值。若良品同样读到 `FF/FFFF`，这两个字段就不能单独区分本次故障；若良品读数有效，则优先核查本线的计量及供电链路。[读取方法](../cable.md) · [线盒芯片和字段依据](vl105-pd-analysis.md#从实机身份字节识别充电芯片)

12:00，按华为 PCVR 助手与 NOLO 驱动的正常协议启用 IMU 并设置 PC 来源。眼镜回传三帧有效 IMU 样本，随后在原生 90 Hz 视频下报告佩戴，约 9 ms 后事件串口失联。右眼录像 6,592 帧均未出现测试色。[Windows 助手调用链与实机时间线](windows-host-startup.md)

11 月 26 日上午用 RTX 3070 Laptop GPU 在同一个 USB-C 口对照了两根线。普通 C-C 在右镜片显示了随输入变色的 `R ↑`。带电源口的原厂手机线在 Windows 原生 90 Hz 和 70 Hz 下均复现头显 USB 掉线。推迟视频使控制接口保持在线约 159 秒；随后打开 70 Hz 视频，头显仍能应答一次开屏，几秒后控制和音频消失。各轮供电、时间线和镜片原照见[公司电脑实测](company-pc.md)。
