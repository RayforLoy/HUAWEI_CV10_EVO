# CV10 的 USB 开屏路径

2026-11-25 查阅公开实现，并与原厂 APK、本机华为驱动和 Fold7 插入时的 USB 描述符交叉核对。当前最有证据的试验是通过头显 PCUI 发送原厂面板开关命令，同时记录物理 DP 时序和镜片观察。Android 接受 Presentation 窗口、头显返回命令应答、镜片实际点亮是三个独立的观测点。

## 可复查的公开研究

| 来源与测试环境 | 实际覆盖范围 |
| --- | --- |
| huawei-vr-compat，Galaxy Z Flip5 | 作者区分了 MCU 的 VCOM 串口和姿态 HID，并列出串口屏幕开关。接近/电量探测报告披露了未验证的厂商接口；其 HID 读数不能直接作为 PCUI 开屏证据。[原始实验第 5 节](https://github.com/EnYaoJingYa/huawei-vr-compat/blob/03bf1012493fd821f38114010e4b21fe20f1d4f1/docs/evidence/proximity-battery-2026-09-16.md) |
| HwVRGlassLite，Windows | 与 QQ 资源中的 1.5.0 安装器同名。桌面姿态代码通过 HID 读报告，优先匹配 6DoF 套件，另匹配头显 107e 的接口 3。源码和安装器内的原厂驱动应分别看待；这里未找到通过这一 HID 接口点亮面板的对照实测。[桌面模式 IMU](https://github.com/fkun1754/HwVRGlassLite/blob/e1550db5e4f4d106b2b76912fc797ccd60013444/desktop-mode/src/dm_imu.cpp) |
| HuaweiVRGlass-ALVR-Android，一加 7T | 作者的 hidprobe 用 feature report 5 激活设备并读取数据；项目报告的另一种纯色待机发生在 SteamVR 场景层。该探针没有验证 Fold7 的面板冷启动。[探针源码](https://github.com/niceqwer55555/HuaweiVRGlass-ALVR-Android/blob/0a7cc2625db16732e38863a419d4aaeb2cdb1322/src/xr/jni/hidprobe.c) |
| Globalka，三星 SM-X806B | 有系统已经枚举 3200×1600 和自动镜像的实测，可用来对照外屏提交和眼别。该次测试的初始时序与本机 Fold7 的 640×480 不同。[作者记录](https://github.com/samrat1games/huawei-vr-glass-globalka/blob/266dbe02e115c7aeed936dedc2d1924ae375bc8c/docs/verification.md) |
| Xavier NX 与 Windows，分线 PC 接法 | 作者在 Windows 冷插可见，在 Jetson 冷插时读到 EDID 却黑屏；保留 USB/供电、只把已经出图的 DP 从 Windows 移至 Jetson 后出现画面。这支持检查主机初始化状态，实验没有捕获决定性的 USB 数据包。[原作者实验](https://forums.developer.nvidia.com/t/display-to-huawei-vr-glasses/169464) |

## Fold7 的接口定位

1. 旧版原厂系统服务的 JNI 开屏路径已定位至 `GetSimpleResultFromVcom` 和 `/dev/ttyUSB0`；事件接收走另一串口。12.0.0.302 的原生库虽会拼接设备路径，仍可分别找到 `ttyUSB0`、`ttyUSB1`，其 `AT^SWITCHSCREEN=1\r\n` 在文件偏移 115544；型号和版本查询也包含完整行结束符。[APK 分析](apk-research.md)
2. Fold7 实际枚举的 `12d1:107e` 接口与本机华为 `oem208.inf` 可逐项对应。接口 0 为类/子类/协议 `ff/13/12`，INF 标为 PCUI，bulk OUT/IN 为 `01/81`；接口 1 为 `ff/13/13`（DIAG）；接口 2 为 `ff/13/06`（Control）。接口 3 的 `84` 是中断 IN，用于另一条 HID 路径。INF 编号由 Windows 安装顺序分配，其他电脑可按 `USB\VID_12D1&Subclass_13&Prot_12` 搜索匹配。
3. 两轮普通 C-C 测试中镜片均黑屏。第二轮应用成功在 HUAWEIAV03 创建 Presentation，日志记录动态 ID 18、19 及 640×480 @ 60 Hz。PC 缓存的 EDID 和 Fold7 实际选择的模式分别记载于[真机记录](device-openxr-check.md)。
4. 在手机「CV10 显示测试」点「通过 USB 识别 CV10 并开屏」，允许本次 USB 访问。程序核对 VID/PID、接口、协议和端点，再读取型号和版本；收到包含 CV10 的应答后发送一次开屏请求。实际应答由应用和 `adb logcat -s Cv10Probe` 显示。此操作仅面向头显的运行态面板控制。[PCUI 实现](../probe/PanelControl.java)

## Git 中的前期记录

核查时远端默认分支为 `codex/cv10-phase1`，指向 `5118561`。此前已提交的四个节点依次为 `04d0999`（采样基线）、`11129c5`（APK 分析）、`fbd899a`（Fold7 手册）和 `5118561`（用户提供的 APK 对比）。原始下载、反编译目录与真机日志由 `.gitignore` 排除。可通过 `git log --oneline --all` 和 `git ls-tree -r --name-only 5118561` 检查。

## 普通 C-C 线的真机开屏试验

13:34:50，Fold7 经普通 C-C、Android USB Host API 直接访问 107e 的接口 0，型号查询返回 `^DEVMODEL:CV10`、`OK`；版本查询返回 `MAINVER:CV10AC10.0.1.357`、`OK`；开屏命令返回 `^SWITCHSCREEN=1`、`OK`。此时外屏 ID 24，物理模式 ID 47 为 640×480 @ 60 Hz，DeX 逻辑画布 1600×900。这次实测确认了原厂系统以外的 PCUI 访问、头显固件升级后的实际版本及面板命令应答。

13:36，在 DeX 扩展模式重复开屏并旋转测试图。外显截图中左右图案完整，摄像头连续记录的左镜片仍接近全黑。固件的开屏应答表示命令已被接受。13:38，保持普通 C-C 连接，把三星设置里的外屏方式切成「已镜像」，物理输出随即出现 3200×1600 @ 90/70 Hz，当前 90 Hz。摄像头先观察到亮度变化，重启测试图并再次发送开屏请求后拍到蓝底白箭头。本轮切换前已经发送过开屏命令，其必要性尚需从完全断电状态做单变量复测。

| 可见证据 | 记录 |
| --- | --- |
| 扩展模式，PCUI 已应答 | [左镜片黑屏](../research/evidence/fold7-dex-left.jpg) |
| 镜像模式，原生时序，测试图 | [左镜片蓝底白箭头](../research/evidence/fold7-mirror-left.jpg) |
| 镜像模式，官方 OpenXR 场景 | [左镜片拍到方块边缘](../research/evidence/fold7-hello-xr-left.jpg) · [同次外显合成帧缩略图](../research/evidence/fold7-hello-xr-compositor.jpg) |

以上镜片照片来自同一台对准左眼的摄像头。完整 OpenXR 场景、运行时与实际输出路径见[真机记录](device-openxr-check.md)。
