# HUAWEI VR Glass 原厂 6DoF 套件静态协议

定位器由原厂套件连接到眼镜。定位器的双目图像、头显惯性数据和左右手柄记录进入主机。原厂 Android VR SDK 在主机端计算头部和手部位姿。套件数据从独立 USB 设备 `12d1:3a09` 读取，CF20 的 GATT 实现适用于原厂 3DoF 手柄。[华为定位器安装说明](https://consumer.huawei.com/cn/support/content/zh-cn15856477/) · [华为眼镜和手柄的自由度说明](https://consumer.huawei.com/cn/support/content/zh-cn15872018/)

## 复核样本

| 样本 | SHA-256 |
| --- | --- |
| `com.huawei.hvrsdkserverapp` 3.5.0.82（35082） | `e0af366239d1c9c8ad384651a3173dfdfccac9ba221768f4db6c5349101d1444` |
| Android `assets/arm64-v8a/libruntime_service_module.so` | `ff8e781f1c2aa23e725693ee6db7614ee3f9035bc66c58100a224de181d480cb` |
| Android `assets/arm64-v8a/libarvr_slam.so` | `2268ff5e2b26e67da395af6c57980f15f23e6199c4cb942d5fb959b3eb9b46a9` |
| Android `assets/arm64-v8a/libVR6Dof.so` | `92020423ca33b2bf7aa147db64dfc0449aaac926d8273c6f7d595440fea49aee` |
| Windows 原厂 PC 助手 11.0.0.105 安装包 | `93070f41afe2a60dc17ed32e0785f212076895d9d2457a6d338e5172e97d10be` |
| PC 助手中的 `app/steamVRDriver/huaweiVR/bin/win64/VR6DOF.dll` | `0e5a3ce7be318b45165e4a7837192a18b31fbdac8e658974f6210904d9ce930a` |
| PC 助手中的 `app/steamVRDriver/huaweiVR/bin/win64/arvr_slam.dll` | `6d89d332acfe86f9a9a3309a913de6d6cb8f0da2f49b46f60b96a07599283a7d` |

用 JADX 复核 SDK DEX，再以 LLVM 工具反汇编提取的原厂 ELF。下文的 Android 地址为上表运行时 ELF 的虚拟地址，Windows 地址为 DLL 的 RVA。PC 助手样本可用 innoextract 离线提取。

## USB 与惯性数据

- Android `ArvrRuntimeUsbReceiver` 匹配十进制 `4817:14857`（`12d1:3a09`）。现有 CV10 眼镜 IMU 驱动使用 `12d1:107e`。公开的独立实现也使用 `12d1:3a09` 的 HID 接口 2。[HwVRGlassLite 的设备匹配](https://github.com/fkun1754/HwVRGlassLite/blob/e1550db5e4f4d106b2b76912fc797ccd60013444/desktop-mode/src/dm_imu.cpp)
- SDK `IMUThread::openDev`（`0x98e28`）打开华为系统的 `/dev/hwvr3`，`handleOVIMUData`（`0x98bd0`）轮询读取，单次缓冲上限 1024 字节。PC `OVIMU::handleOVIMUData`（`0x6a520`）通过 HID `ReadFile` 读取并要求返回长度为 128 字节（调用 `0x6a610`，校验 `0x6a759`）。PC 解析入口 `0x6a9e0` 同样读取大端头部时间戳并检查字节 `0x30`。诊断 APK 使用公开的 USB Host API 枚举设备与端点，并尝试读取接口 2 的中断 IN；Fold7 报告边界待采样确认。[Android USB Host](https://developer.android.com/reference/android/hardware/usb/UsbManager)
- `IMUPushThread::ThreadLoop`（`0x9a964`）把缓冲交给头部 SLAM、手柄 3DoF 状态和视觉手柄线程。另有设备状态和校准通道，`IMUDealThread` 处理报告类型 `0x29`、`0x2a` 和固件版本类型 `0x25`，`IMUThread::GetHash/GetPack`（`0x99420/0x9966c`）走校准查询。

### 头显记录

`RuntimeTool::GetTimeStampByImuBuffer`（`0xbbd84`）读取 `0x0c–0x13` 大端纳秒计时。`RuntimeTool::CreateHelmetInfo`（`0xbc334`）要求 `[0x14] = 0`、`[0x1b] = 1`，按下表读取大端 s16。六轴读取均在 `ldrh` 后执行 32 位 `rev` 和算术右移 16 位。

| 输出 | X 偏移 | Y 偏移 | Z 偏移 | 各轴比例 |
| --- | --- | --- | --- | --- |
| 加速度 | `0x17` | `0x15` | `0x19` | `(-1,+1,+1) × 0.000244 × 9.8` |
| 角速度 | `0x1e` | `0x1c` | `0x20` | `(-1,+1,+1) × 0.07 × π/180` |

### 左右手柄记录

`VCtrlThread::PushCtrlInfo`（`0xc54bc`）经 `RuntimeTool::CanPushCtrlInfo`（`0xbca94`）检查 `[0x30] = 0x20`。左记录从 `0x31` 开始，右记录从 `0x55` 开始，由 `RuntimeTool::CreateVControlInfo`（`0xbc0c4`）解码。下表使用相对偏移，多字节字段除计时器外均为小端。

| 偏移 | 格式 | 解释 |
| --- | --- | --- |
| `0x00` | u8 位域 | bit 5 确认，bit 4 返回，bit 1 Home，bit 3 摇杆按下 |
| `0x01` | u32 大端 | 手柄计时。原厂先转 f32 并除以 `10⁶`，倍率非零时再用 f32 相乘，最后扩大为 f64 秒。诊断保留原始计数、倍率及送入位姿算法的截断纳秒值 |
| `0x05/07/09` | s16 × 3 | 加速度，各轴乘 `0.0047884039` |
| `0x0b/0d/0f` | s16 × 3 | 角速度，各轴乘 `0.0021305280` |
| `0x11/13/15` | u16 × 3 | 三轴原始值，原厂缩放为 `(value - 32767) × 100 / 1024`，疑似磁传感器 |
| `0x17` | u8 | 计时倍率，0 表示跳过乘法 |
| `0x18` | u8 | 电量字段 |
| `0x19/1b` | s16 × 2 | 扳机、握持，各乘 `25`，实际范围待采样 |
| `0x1d/1f` | s16 × 2 | 摇杆 `X = (raw + 1499) / 3046`；SDK 输出的 `Y = 1 - (raw + 1642) / 3035` |
| `0x21` | u8 位域 | bit 6 确认触摸，bit 0 返回触摸，bit 2 摇杆触摸，bit 4 扳机触摸 |
| `0x22` | u8 位域 | bit 0 握持触摸 |

诊断仅统计计时非零的左右手柄有效记录。原厂后续才生成位姿及有效性等状态。Android `VrParamsRequester.isHW6DoFAvailable` 使用 0、1、2 分别查询头部、左手、右手。`ArvrRuntimeModuleManager.getLeftCtrlPos/getRightCtrlPos` 对应手柄索引 1 和 2。

## 定位器相机

SDK 里的 `module.a.b`（`HWCamera.java`）按尺寸及像素格式选择 Camera2 流，`module.a.c` 接收 `1280 × 481` 的 Y8（`0x20203859`），将 615,680 字节传入原厂 native。 `RuntimeTool::CreateFrameByBuffer`（`0xbbf54`）把每行的前 640 列和后 640 列拆成两路 `640 × 480` 灰度图。原厂紧密排列图像的最后一行从 `0x96000` 开始。诊断根据 Camera2 给出的行步幅定位同一行。[Android ImageFormat](https://developer.android.com/reference/android/graphics/ImageFormat.html)

| 末行内偏移 | 格式 | 解释 |
| --- | --- | --- |
| `0x00` | u64 LE | 定位器设备纳秒计时 |
| `0x12` | u32 LE | 帧号 |
| `0x16` | u16 LE | 曝光时长，µs |
| `0x1c` | u8 | `IsAFrame`（`0xbbdb8`）默认把字段为 0 的帧判为 A。原厂属性 `hvr.abframe=enable` 时改用曝光大于 5000 µs。诊断显示原始字段 |

诊断选择唯一标记为外接且公开上述尺寸及格式的 Camera2 设备。若 Fold7 的 Camera HAL 未公开原始 Y8，仍需验证 USB 视频接口及直读能力。应用在诊断按钮触发后请求相机权限，Android 也可能要求相机权限才能访问含视频接口的复合 USB 设备。[AOSP UsbUserPermissionManager](https://android.googlesource.com/platform/frameworks/base/+/master/services/usb/java/com/android/server/usb/UsbUserPermissionManager.java)

五秒采样保留第一张有效双目帧。ZIP 中两张 `camera0.y8` 和 `camera1.y8` 分别是 307,200 字节的 `640 × 480` 行优先灰度数据。另存可读的原始末行 `trailer.bin` 和 `frame.txt`，后者记录设备时钟、Camera2 图像时间戳及回调读取的 Android 单调时间。这三个时间值分别保留，时钟关系待验证。

## 校准查询

应用请求为 64 字节，格式为 `02 <选择器> 80 00 <协议字节> <命令> <分包序号>`，余下字节填零。选择器按原厂调用参数 0、1、2 依次对应定位器 `81`、左手 `83`、右手 `82`。哈希命令为 `2a`，序号填 0。分包命令为 `29`，序号从 1 开始。

| 原厂程序 | 请求字节 `[4]` 和传输 | 回复 |
| --- | --- | --- |
| Android SDK | `02`。由 `IMUThread::GetHash/GetPack`（`0x99420/0x9966c`）入队，`SendCommandToDevice`（`0x9875c`）写入华为设备描述符 | `WaitHashData`（`0xb50a0`）从 `0x31` 取 `[0x2f]` 字节。`WaitPackData`（`0xb4e0c`）检查 `[0x2c] = 0x80`，用首包 `[0x31]` 确定总包数，从各包 `0x33` 追加 `[0x2f] - 3` 字节 |
| Windows PC 助手 | `05`。`GetCalibrationParameterHash`（`0x48010`）和 `ReadFirmwareBuffer`（`0x48390`）通过标准 HID 设备句柄调用 `WriteFile`，再调用 `ReadFile` 等待 128 字节回复 | 哈希从 `0x31` 取 33 字节。分包长度按大端 u16 取 `[0x2e..0x2f]`，减 3 后从 `0x33` 追加。PC 固定读取 22 个定位器分包和每只手柄 29 个分包，写文件前分别校验 990 和 812 字节（`0x4895e–0x48a12`） |

诊断 APK 从报告 `[0x2d]`、`[0x30]`、`[0x32]` 匹配选择器、命令和分包序号。它先查询 Android 格式，哈希未收到时改用 Windows 格式。USB 接口有中断 OUT 时经该端点写 64 字节，否则发送 HID `SET_REPORT`（`bmRequestType=0x21`、`bRequest=0x09`、`wValue=0x0202`、`wIndex=2`）。每个完整组件保存一个 ZIP，包含校准数据和设备返回的哈希字段。USB 实际端点和回复格式待 Fold7 采样确认。[Windows HID 输出报告](https://learn.microsoft.com/windows-hardware/drivers/hid/sending-hid-reports) · [USB HID 1.11](https://www.usb.org/sites/default/files/hid1_11.pdf) · [Android UsbDeviceConnection](https://developer.android.com/reference/android/hardware/usb/UsbDeviceConnection)

### 定位器校准数据

Android `SaveHelmet`（`0xb2db8`）从分包拼接缓冲解析。前 2 字节为头部，`GetVer`（`0xb1c98`）读取接下来两个小端 32 位值，再跳过 `0x36` 字节。从 `0x40` 和 `0x170` 依次读取两路相机，`GetCamPara`（`0xb2478`）每路前进 `0x130` 字节。头显 IMU 校准数据随后从 `0x2a0` 开始。

| 相机记录相对偏移 | 小端类型 | 字段 |
| --- | --- | --- |
| `0x00/01/05/09/0d` | u8、u32、u32、f32、u8 | 相机编号、宽、高、帧率、滚动快门模式 |
| `0x0e/16/1e` | f64 各 1 | 读出时长、曝光时间偏移、相机与 IMU 延时，单位秒 |
| `0x26` | f64 × 4 | 焦距和主点，各按 X、Y 顺序 |
| `0x46/47/48` | u8、u8、f64 × 8 | 去畸变开关、畸变模式、畸变参数 |
| `0x88/8c` | f32、f32 × 4 | 原厂自动对焦参数 |
| `0x9c/d4` | f64 × 7 各一组 | 外参 `Tbc` 与 `Tcm`，保持原始顺序 |
| `0x10c/110` | f32、32 字节 | 像素标准差、原厂跳过的尾部 |

诊断页校验左右记录的尺寸和内参，显示每路帧率、焦距、主点和 IMU 延时。套件原厂 XML 可对照字段命名，实际畸变模型和外参轴向仍需结合实机数据验证。

### 左右手柄校准数据

Android `SaveHand`（`0xb3274`）对两只手使用相同布局。下表为各自校准数据的绝对偏移，值均为小端。

| 偏移 | 类型 | 字段 |
| --- | --- | --- |
| `0x40` | f64 × 7 | 原始外参按四元数 `xyzw`、平移 `xyz` 排列。原厂在 `0xb3534–0xb3700` 将其逆变换为 `extrinsicThi`，旋转用共轭 `q*`，平移用 `-R(q*)t` |
| `0x98 + i × 0x18` | f64 × 3 | 第 `i` 个 LED 的 `xyz`，共 16 个，循环位于 `0xb3724–0xb374c` |
| `0x218` | f64 | 手柄相机与 IMU 延时，读取位置 `0xb3754`，对应 PC XML 的 `handlerDelayCam2IMU` |
| `0x240` | IMU 记录 | 与定位器采用同一 IMU 记录布局 |

PC 助手的 `vrglass-handler-default.xml` 在 `Handler-Default` 下为每只手柄保存 16 条 `handlerLedParam`、8 个 `ledBBoxPosition` 顶点、IMU 校准及外参。Android 的分包解析直接读取 16 个 LED 的位置。LED 法线、可见性和帧内点关联仍需验证。

### 共用 IMU 校准记录

Android `GetImuPara`（`0xb1e5c`）解析定位器 `0x2a0`、任一手柄 `0x240` 起的记录。字段语义与 `WriteImuParaXml`（`0xae5a8–0xae87c`）输出核对。

| 记录相对偏移 | 小端类型 | 字段 |
| --- | --- | --- |
| `0x00` | u8 | 原厂跳过 |
| `0x01/05/09` | f32、f32、u8 | 陀螺仪和加速度计采样率（Hz）、补偿开关 |
| `0x0a/22/3a` | 每项 f64 × 3 | 陀螺仪偏置、比例、轴误差 |
| `0x52/6a/82` | 每项 f64 × 3 | 加速度计偏置、比例、轴误差 |
| `0x9a` | f64 × 4 | 陀螺仪到加速度计的旋转四元数 |
| `0xba/c2/ca/d2` | 每项 f64 | 陀螺仪噪声、加速度计噪声、陀螺仪偏置、加速度计偏置的标准差 |

## 位姿计算与接入进度

原厂头部路径把双目图像和头部 IMU 分别交给 `SlamThread::PushImageData`（`0xbf6d8`）和 `PushHelmetInfo`（`0xc09b0`），由 `libarvr_slam.so` 估计位姿，运行时通过 `SlamThread::GetPosture`（`0xc0580`）读取。手柄路径把视觉帧和左右手 IMU 送到 `VCtrlThread::PushVCtrlData`（`0xc4b04`）和 `PushCtrlIMU`（`0xc56f8`），`libVR6Dof.so` 内部有 `BlobDetection`、`HCTracker` 等处理。

Android `SlamState::Init` 在 `0xc15b4` 调用 `libarvr_slam.so` 导出的 C 符号 `GetSlamInterface`。该库的 `0x1d3a50` 返回位于 `0xb8d050` 的函数表，首 8 字节是标记 `0x00000001abcd2012`，`+0x08` 是字符串 `SLAM` 的地址。Windows 的 `arvr_slam.dll` 同名导出（`0xfac30`）返回 `0x717620` 的相同标记及槽位布局。以下偏移按此函数表计算。

| 用途 | 表内字节偏移 | Android 运行时的调用位置 |
| --- | --- | --- |
| 设置回调 | `0xa0` | `0xc1624` |
| 创建实例、初始化、启动 | `0x20`、`0x30`、`0x38` | `0xc16e0`、`0xc16fc`、`0xc1dc4` |
| 送入图像和 IMU | `0x70` | `0xc21e0`、`0xc22cc` |
| 取得头部位姿 | `0x78` | `0xc23ac` |
| 停止、清理、释放实例 | `0x50`、`0x58`、`0x28` | `0xc1ee0`、`0xc1c88`、`0xc1ce0` |

Android 先用 `+0xa0` 注册回调，再用 `+0x20` 创建。注册结构依次为上下文、写配置、读配置、保留输入引用、释放输入引用、输入回调、输出回调，各占 8 字节。销毁后用 `+0xa8` 清理注册。创建入参是两条格式字符串：

```text
fmt:yuv@res:480p@rot:0;fmt:preyuv@res:480p@rot:0;fmt:feature;fmt:depth@rot:0;fmt:imu
fmt:pose@org:slam;fmt:predictpose@org:slam;fmt:cameraintrin@org:slam;fmt:pointcloud@org:slam;fmt:anchor@org:slam@type:update
```

创建时读配置回调先收到 `HSDK_CONFIG_MANAGER_IMPL_GET_CHECK_VALID`（1 字节），再收到 `HSDK_CONFIG_MANAGER_IMPL_GET_SLAM_PARAMS`（2112 字节）。Windows `VR6DOF.dll` 的 `VrSlamConfiguration::InitPara`（`0x2fef0`）可从原厂 XML 载入默认模型，其 `GetValue`（`0x310d0`）可通过这两个键返回配置。Android `VrConfiguration::GetValue` 在 `0xba748` 和 `0xba7dc` 分别检查相同的缓冲长度，后者从对象 `+0x08` 复制 `0x840` 字节。Windows 读取配置时还请求 1024 字节的 `HSDK_CONFIG_MANAGER_IMPL_GET_SLAM_BIAS_INFO`。

Android `VrConfiguration::DispatchModulePara`（`0xb7640`）提供下列字节布局。调整 Windows 样本 XML 的字段后分别读取原厂配置，用于复核字段对应关系。

| 缓冲偏移 | 字段 |
| --- | --- |
| `0x000` | u32 相机数量 2 |
| `0x008`、`0x138` | 两路相机，每路记录跨度 `0x130`。相对 `0x00`、`0x04`、`0x08`、`0x0c`、`0x10` 是 u32 ID、模式 1、宽、高、灰度行步幅，`0x14` 是 f32 帧率 |
| 相机记录 `+0x18`、`+0x40` | 各 4 个 f64，分别为对焦补偿和 `fx, fy, cx, cy` |
| 相机记录 `+0x60`、`+0x64`、`+0x68` | 两个 u32 为去畸变标志和模型，随后 8 个 f64 按 `k1, k2, k3, k4, k5, k6, p1, p2` 写入。设备原字段把 `p1, p2` 放在 `k3` 之后 |
| 相机记录 `+0xa8`、`+0x128` | 行优先 f64 `Tbc` 齐次矩阵和 f64 读出时间。`Tbc` 将相机坐标变换到 IMU 坐标 |
| `0x4d4`、`0x4d8`、`0x4e0`、`0x4e8` | f32 加速度计和陀螺仪标称频率，f64 第一相机的相机到 IMU 延时和曝光偏移。Android 在 `0xb7ccc–0xb7cec` 将两路频率设为 1000 Hz，Windows 从 XML 取值 |
| `0x570`、`0x574`、`0x598`、`0x5a4`、`0x5c8` | u32 补偿标志，f32 加速度计矩阵及偏移，f32 陀螺仪矩阵及偏移。矩阵行优先，长 9 元素，偏移量长 3 元素 |
| `0x5d8`、`0x5e0`、`0x5e8`、`0x5f0` | f64 陀螺仪噪声、陀螺仪偏置标准差、加速度计噪声、加速度计偏置标准差 |

对于校准缩放 `s` 和失准 `m`，原厂用 `diag(s)` 左乘上三角矩阵，其对角线为 1，上三角按行依次为 `m[0..2]`。设结果为 `M`，写入的偏移为 `−M⁻¹b`。加速度计矩阵再左乘 `gyro2accel` 旋转矩阵的逆，偏移公式沿用本传感器的 `M`。对应 `XmlOpt::GetAccScaleMatrix`（`0xa8858`）、`GetGyroScaleMatrix`（`0xa9050`）和 `GetImuBias`（`0xa9160`）。

诊断 APK 将 2112 字节参数加入 `locator.zip` 中的 `slam-params.bin`。用原厂 Windows 默认 XML 构造同一份定位器输入后，APK 编码器与原厂的配置逐字节核对，差异限于 Android 的 1000 Hz 和 PC 输出的 `HMA-TL00` 标识。Windows SLAM 离线探针使用 `--parameters` 载入生成的参数后，完成了与原厂 XML 同样的启动、合成输入和清理流程。

### 头显输入与预测时间

Android `HxrAlgorithmData` 在 64 位程序中占 `0x120` 字节。前 `0x100` 字节为以零结尾的格式字符串，随后是 `0x100` 的 u64 载荷长度、`0x108` 的 u64 纳秒时间、`0x110` 的载荷指针和 `0x118` 的所有者指针。图像组合包由原厂保留引用回调管理。头显 IMU 以 `fmt:imu` 分开送入加速度和角速度，每个载荷为 `0x20` 字节。类型 u32 位于 `0x00`（0 为加速度、1 为角速度），设备时间 f64 秒位于 `0x08`，三个轴为从 `0x10` 开始的 f32（`PushHelmetInfo`，`0xc09e8–0xc0adc`）。

双目组合包使用 `fmt:yuv@res:480p@rot:0@fmt:preyuv@res:480p@rot:0@fmt:feature@fmt:depth@rot:0`。其 `0x78` 字节载荷在 `+0x10`、`+0x18` 分别指向两路图像的 `HxrAlgorithmData`，在 `+0x30`、`+0x38` 指向原厂特征数据（`0xbfee4–0xbfef4`）。每路图像用 `fmt:yuv@res:480p@rot:0`，包含 `0x60` 字节的元数据，分别在 `+0x04/+0x08/+0x0c` 保存宽、高、行步幅，`+0x28`、`+0x38` 记录设备时间和曝光秒数，`+0x48` 指向灰度缓冲。

实时查询使用 `fmt:pose@org:slam`，预测查询使用 `fmt:predictpose@org:slam`，两者为 `0x38` 字节输出缓冲。原厂预测时间在 `0xc05d0–0xc05ec` 计算为最后送入的 IMU 时间加上「请求时间（由微秒乘 1000）减当前 `CLOCK_MONOTONIC` 纳秒」的差。图像和 IMU 同时送入时均采用报文设备时间。两路设备时间实际偏差和 Fold7 的数据延迟仍需采样。

`GetHelmetPosture` 在 `0x91af4–0x91b34` 检查查询返回值和 `0x08`／`0x0c` 两个 u32 状态，任一为零都进入无有效位姿分支。缓冲 `0x00` 为 f64 秒，`0x10` 为 3 个 f32 位置 `xyz`，`0x1c` 为 4 个 f32 四元数 `wxyz`。`0x91b08–0x91b20` 将其循环移位为 `xyzw`，随后使用 `UpdateHelmetCoordinate` 转换到头显坐标。

`TransSlamCoord2Hmd`（`0x92914`）先将 SLAM 四元数右乘出厂对齐四元数 `(0.211309, 0.211309, 0.0468461, 0.953154)`，顺序为 `xyzw`。设结果为 `q`。从位置中减去 `q` 旋转后的偏移向量 `(-0.059, -0.029, 0.018)` 米。`coordToHMD`（`0xbb234`）将位置及四元数向量部的轴都重排为 `(x, z, -y)`，最后将四元数右乘绕 X 轴正 90° 的旋转。诊断同时显示 SLAM 坐标和此变换的头显坐标。合成向量覆盖偏移方向、轴重排、四元数乘法及无效状态。原厂 `UpdateHelmetCoordinate` 后续对偏航角及水平原点的重置独立于此转换。

用 [Windows 离线探针](probe-slam-head.py) 在独立进程载入默认 XML，验证库可创建、初始化、启动、停止、清理及销毁。六条合成 IMU 数据和两组无特征的空白双目图都由 `+0x70` 返回 0。随后 `+0x78` 返回 `-1`，输出缓冲保持为零。此测试覆盖调用与数据入口。生成有效的视觉位姿仍需同步的真实输入。

### Android 头显诊断接入

运行时和独立诊断 APK 共用 C++ 头显适配层。用户通过 Android 文档选择器导入原厂 ARM64 `libarvr_slam.so`。应用仅接受 SHA-256 为 `2268ff5e2b26e67da395af6c57980f15f23e6199c4cb942d5fb959b3eb9b46a9` 的样本，并从应用私有目录加载。两份 APK 只打包适配层。适配层用相同的引用计数持有组合包、两路图像和像素，直到调用方和原厂库都释放引用。两路特征指针置空，输入为原始灰度像素。

实时诊断在同一轮中读取定位器校准、头显 HID 和外接 Y8。每组图像等待设备时钟达到该帧的 IMU 样本，再送入 SLAM。离线回放使用所选校准、合成 IMU 和空白图像。两种诊断都显示位姿查询结果。用 [Windows 共用适配层探针](probe/HeadSlamAbi.cpp) 将相同 C++ 代码编译到 x64，已用原厂 PC `arvr_slam.dll` 和 Android 格式校准完成回放，查询返回 `-1`、输出全零，关闭后所有输入缓冲均已释放。尚未在 Fold7 执行 Android 库加载或测得有效头显位姿。

### Monado OpenXR 头显定位

从套件页面显式启动相机前台服务。服务与 OpenXR 运行时共享应用进程，使用同一套 Y8、HID 和 SLAM 实现。在 HID 到达时间上估算定位器时钟到 Android 单调时钟的偏移，用样本间隔限制偏移的增长，筛掉时间超前或超过 250 毫秒的位姿。启用后的新运行时系统将头显的位姿标记为可跟踪位置。Monado 原生层轮询最新位姿并查询历史，未来时刻先保持最近位姿。断流或停止服务时，回到眼镜原有 USB IMU 旋转，清除位置有效标记。当前实现依赖系统公开外接 Y8，时间映射和实际跟踪性能待实测。[Android 相机前台服务要求](https://developer.android.com/develop/background-work/services/fgs/service-types#camera)

### 左右手柄位姿接口

Android `VCtrlState::Init`（`0xc631c`）调用 `libVR6Dof.so` 的 `GetVR6DofInterface`（`0x14ba4c`），返回表 `0x636050`。Windows `HandlerDLL.dll` 的同名导出（RVA `0x3f5f0`）返回表 `0x16f940`。两表使用标记 `0x00000001abcd2012` 和名称 `VR6Dof`。创建、初始化、启停、回收、输入、查询和回调注册槽位与头显表的对应槽位相同。输入格式列表为 `fmt:yuv@res:480p@rot:0;fmt:imu@org:helmet;fmt:imu@org:controller;fmt:pose@org:slam`，输出为 `fmt:pose@org:vr6dof`。配置键 `HSDK_CONFIG_MANAGER_IMPL_GET_VR_6_DOF_HANDLER_CONFIG` 返回 `0x1c38` 字节，见 Android `VrConfiguration::GetValue` 中的 `0xba8a8–0xba8bc`。

Android `VCtrlThread::PushCtrlIMU`（`0xc56f8`）把 `fmt:imu@org:controller` 送入 `HxrAlgorithmData`。其 `0x38` 字节载荷的 `0x00` 为 u8 有效标志，`0x01` 为左手 ASCII `0` 或右手 ASCII `1`，`0x08` 为 u64 纳秒时间，`0x10` 开始为六个 f32 惯性轴，`0x28` 开始为四个 f32，原厂填入 `(1, 0, 0, 0)`。`VCtrlThread::GetPosture`（`0xc5948`）将 `0x18` 字节的 64 位 `std::vector<HandlerPose>` 作为输出载荷交给 `+0x78`。查询返回值及每条姿态的状态需要共同检查。

Android `VCtrlThread::PushVCtrlData`（`0xc4b04–0xc5038`）用 `fmt:yuv@res:480p@rot:0` 送入 `0x68` 字节的载荷。`+0x00` 是图像数量 u32（2），`+0x08/+0x10/+0x18` 为 `std::vector` 的首、尾及容量指针，元素为直接指向 `0x60` 字节图像载荷的指针。`+0x20` 为对应帧的 `0x38` 字节原始头显 SLAM 查询结果，`+0x58/+0x60` 为头部 SLAM 接口和实例指针。Windows 探针的空帧只验证输入与查询边界，两个 SLAM 指针留空。

Windows 离线探针分别使用 PC 原厂默认 XML 与 Android APK 的 `assets/vrglass.xml`，两份配置均初始化两路相机和两只手柄。无图像时查询返回 `-1`。加入覆盖两帧时间的双手 IMU 后，两组带合成头部位姿的空白双目帧都由 `+0x70` 接受，随后的查询返回 `0`。两种查询下，两条 `0x54` 字节的记录均保留 ASCII `0`、`1` 标识，`+0x04` 的左右状态均为 `255`。Android `ArvrRuntimeModuleManager::UpdateCtrlPos` 在 `0x922bc–0x922c8` 拒绝该状态，随后从 `+0x08` 读取 f32 位置 `xyz`，从 `+0x14` 读取 f32 四元数 `wxyz`。探针同时核对查询返回码、标识和每只手柄的状态。

`libarvr_slam.so` 的 ELF `DT_NEEDED` 只列出 Android 平台库。手柄库 `libVR6Dof.so` 另外链接 `libhiai.so`、`libhiai_ir.so`、`libhcl.so` 和 `libhiai_hcl_model_runtime.so`。Android 还在初始化前通过 `+0x60` 以 `fmt:ai_path@org:vr6dof` 设置 `SDmmm1_fp16_480_640.om` 的路径（`0xc6508`、`0xc6620–0xc6634`）。手柄库的 `BlobDetection::DetectBlobs`（`0x13a7a8`）和 `P3PSolver::CalcPose`（`0x1a3d2c`）分别是斑点检测和位姿求解入口。Android 左右手光学定位仍待接入。

待核实 Fold7 上的相机与 HID 可用性、图像与惯性时间的偏差、头显及双手位姿和 OpenXR 6DoF 输出。
