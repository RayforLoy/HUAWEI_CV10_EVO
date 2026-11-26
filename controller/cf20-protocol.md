# HUAWEI CF20 蓝牙手柄静态协议

CF20 是单手持 3DoF 手柄。华为手柄应用负责 BLE 连接，华为 VR SDK 从手柄应用的 AIDL 服务取报告并解码。Monado CV10 直接通过 Android GATT 连接手柄。6DoF 套件的定位器、头显和左右手柄使用另一条链路，见 [6DoF 套件协议](kit-6dof-protocol.md)。

## 复核样本

| 样本 | 版本 | SHA-256 |
| --- | --- | --- |
| 手柄应用 `com.huawei.vrhandle` | 10.0.1.345（100001345） | `e947fc358e9692358ac42cfe4a565c112f7fc9349da693643f863d08af98b3d2` |
| VR SDK 服务 `com.huawei.hvrsdkserverapp` | 3.5.0.82（35082） | `e0af366239d1c9c8ad384651a3173dfdfccac9ba221768f4db6c5349101d1444` |

用 JADX 打开两个 APK。手柄应用中的 `t0.y0` 执行扫描，`r0.n1.l` 识别名称，`t0.s5.X1/T1/W1/d2` 发现服务、注册通知并推进连接状态。`t0.d3.r1/z1` 将输入通知作为消息类型 2 转发，`t0.l8.g2/G0` 缓存原始字节。`VRHandleService.getControllerData` 使用 AIDL 事务 10。SDK 的 `DefaultController.extractRawData` 在 `classes.dex` 代码偏移 `0x06b930` 读取报告，SDK 内嵌的 `hvrframework.dex` 也有此解码路径。

## 搜索、配对与订阅

1. 原厂识别广播名称前缀 `Testmotion`、`Huawei Controller`、`HUAWEI CF20`。Monado 搜索 15 秒，也接受广播下表服务 UUID 的设备。可以手动填写地址。
2. 原厂以 `connectGatt(..., autoConnect=false, transport=LE)` 直连。手柄应用 `MainActivity` 将服务连接状态 1 显示为配对中、2 显示为成功。`t0.l8.r2 → q2` 在状态 2 后向 iConnect 发 `com.huawei.iconnect.action.DEVICE_BOND_STATE_CHANGED`。静态可追溯路径走应用连接状态，未见它主动调用 Android `createBond()`。
3. 原厂先注册控制通知，约 500 ms 后注册输入通知。Monado 等控制 CCCD 写入回调再写输入 CCCD。设备缺少控制通知描述符时尝试直接订阅输入。收到首个符合格式的 20 字节报告后，**配对并选用**保存该地址，下一次运行时创建设备时自动连接。用户也可选**Android 系统配对**，等待 `BOND_BONDED` 后再确认输入通知。系统配对支持情况待特定固件实测。[Android BluetoothDevice](https://developer.android.com/reference/android/bluetooth/BluetoothDevice) · [Android BluetoothGatt](https://developer.android.com/reference/android/bluetooth/BluetoothGatt)

| GATT 项 | UUID | 原厂用途 |
| --- | --- | --- |
| 服务 | `622f5b2a-60da-4484-929a-69e3a9140258` | CF20 私有服务 |
| E4 特征 | `233827e4-09cc-45a4-a59b-4d024138cbbe` | 应用控制写入 |
| E5 特征 | `233827e5-09cc-45a4-a59b-4d024138cbbe` | 控制通知 |
| 输入特征 | `ffb4a651-c224-420b-a134-13d3aba313fb` | 20 字节传感器与按键报告 |
| CCCD | `00002902-0000-1000-8000-00805f9b34fb` | 写 `01 00` 启用通知 |

原厂 E4 另有 iConnect 上下文写入 `01 0f …`（`r0.g2`、`t0.d3.l0/a`）和应用控制写入 `01 07 07 00`（`a.l1/g2.m`）。Monado 只写 CCCD，对输入报告的连通性以实际通知为准。SDK 的 `DefaultController.startVibrate` 返回 `-1`，目前没有已核实的振动输出命令。

## 输入报告

偏移从 0 开始。四元数按 `(x, y, z, w)` 表示。有符号 16 位字段均为大端。

| 偏移 | 格式 | SDK 解释 |
| --- | --- | --- |
| 0 | 位域 | `01` 扳机，`02` 确认，`04` 音量减，`08` 音量加，`10` Home，`20` 返回 |
| 1–2 | s16 | `x = s16 / 32767` |
| 3–4 | s16 | `y = -s16 / 32767` |
| 5–6 | s16 | `w = -s16 / 32767` |
| 7–8 | s16 | `z = s16 / 32767` |
| 9–11 | s8 × 3 | 加速度各轴乘 `16 / 127`，物理单位推测为 g |
| 12–14 | s8 × 3 | 角速度各轴乘 `2000 / 127`，物理单位推测为 °/s |
| 15–16 | u8 × 2 | 触摸坐标除以 255，两字节同为 0 表示无触摸 |
| 17 | s8 | SDK 返回的电量字段 |
| 18–19 | 原始字节 | 该版解码器未读取 |

报告没有 SDK 读取的设备时间戳。Monado 在收到通知时以 `System.nanoTime()` 标记，规范化四元数。最后报告超过 250 ms 即停用输入和姿态。作为 `/user/hand/right` 的 `/interaction_profiles/khr/simple_controller` 提供扳机或确认 → `select/click`、返回 → `menu/click`、`grip/pose` 和 `aim/pose`。位置采用固定右手偏移 `(0.20, -0.30, -0.35) m`，只设置位置有效位。触控、音量、Home、原始传感器和电量用于诊断。握持轴、瞄准轴和头显坐标对齐待实测。[OpenXR Simple Controller](https://registry.khronos.org/OpenXR/specs/1.1/html/xrspec.html#_khr_simple_controller_profile)
