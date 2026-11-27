# Monado CV10 整合预发布与原厂对照

2026-11-27 · Galaxy Z Fold7 与 HUAWEI VR Glass CV10

## 安装与使用

`Monado-CV10-0.1.4-rc.1.apk` 同时支持 ARM64 和 ARMv7，Android 版本代码为 104。在 Khronos OpenXR Runtime Broker 勾选 **Monado CV10 Preview**，三星外接显示选 **已镜像**。因为本机预览签名与稳定版签名不同，使用已有预览包名，可覆盖同签名的旧预览并与稳定版共存。[GitHub 发布及校验和](https://github.com/RayforLoy/Monado_CV10/releases/tag/v0.1.4-rc.1)

| 入口 | 操作 |
| --- | --- |
| 标准 OpenXR 与离线 2D/3D 启动器 | 手机桌面直开，或者从 Monado 的 **应用启动器** 直开或进入 3D 菜单。手机激光笔使用点按确认、内侧边缘滑动返回和底部滑动停留置中。 |
| 原版 Pocket XR | 从 **更多选项 → Pocket XR 外显预览** 进入空间、测试卡或 Half SBS 电脑串流。虚拟显示需要 Shizuku 和原版 Pocket XR。原版手机触控板可从 2D 列表直接打开。 |
| CF20、6DoF 套件、软件瞳距 | 从 **更多选项 → CV10 蓝牙手柄** 打开 CF20；套件入口位于同页。**CV10 软件瞳距** 调整立体渲染眼距。原厂 SLAM 文件由用户导入。 |

整合版包含 16 KiB 所需的原生库对齐、OpenXR 正常卸载修复及 Fold7 后台服务恢复。原版 Pocket XR 空间和电脑 3D 串流共用同一个 Monado 安装包；在其空间里启动独立 OpenXR 应用时，Broker 仍可使用原版 Pocket XR 的运行时。此前验证过的带卸载修复的 Pocket XR 客户端是可选实验组件。[卸载与重进](https://github.com/RayforLoy/Monado_CV10/blob/v0.1.4-rc.1/history/fold7-offline-launcher.md) · [Pocket XR 独立应用实测](https://github.com/RayforLoy/Monado_CV10/blob/v0.1.4-rc.1/history/fold7-pocket-dual-runtime.md)

## 验收

- APK 的 v2 签名、ZIP 对齐及全部 ARM64 库的 16 KiB `PT_LOAD` 对齐通过。本机 SHA-256 为 `99ace97c02f34845e2c9b4f70c6364c1d1d269f33c3195f0e0f23c9fc8f528d5`，证书 SHA-256 为 `68365fa0904432aaa86a8904c691f9e6487414dc959786d72831a083b9f23fca`。
- Fold7 配 C9.53.6 原厂线和外部 5 V 供电，外显 3200×1600 @ 90 Hz。2D 列表直启和 3D 激光笔点选都让原版 `hello_xr` 在同一进程进入 `FOCUSED`。2D 启动后拍到右镜蓝块，3D 点选后用户确认双眼蓝块，两轮返回都完成 `xrDestroyInstance`。整合包保留已有 Shizuku 授权，原版 Pocket XR 的测试卡也拍到正向 `RIGHT EYE`。[整合包右镜实拍与日志](https://github.com/RayforLoy/Monado_CV10/blob/v0.1.4-rc.1/history/fold7-unified-runtime.md)
- CF20、6DoF 套件和软件瞳距入口均在 Fold7 打开，两组手柄协议向量通过。实际 CF20 配对、套件有效位姿、瞳距光学校准、ARMv7 实机及本包在 16 KiB 系统上的运行待验证。
- 之前的 USB-C 直连轮次已通过双眼与头动、停用 Shizuku 后的整机断网 2D/3D 启动、原版 Pocket XR 空间固定与 Half SBS 电脑串流双眼佩戴验收。[断网实测](https://github.com/RayforLoy/Monado_CV10/blob/v0.1.4-rc.1/history/fold7-offline-launcher.md#fold7-整机断网并停止-shizuku) · [3D 串流佩戴实测](https://github.com/RayforLoy/Monado_CV10/blob/v0.1.4-rc.1/history/fold7-pocket-pc-sbs.md#fold7-usb-c-直连双眼佩戴验收)

## 下一阶段的原厂对照

对照基线为目前的 Fold7 整合版和 P40 Pro+ 原厂 VR 服务。优先固定同一副 CV10、C9.53.6 原厂线和 5 V / 2 A 电源。另记录 USB-C 直连对照。分别记录原厂模式与 Fold7 的外显时序，保留原厂 70 Hz 和 Fold7 90 Hz 的差异。已有 P40 原厂测试在未接眼镜时枚举 11 个 OpenXR 实例扩展，并跟到 `xrCreateInstance → Hxr_Initialize → Helmet::init`。原厂服务在缺少头显及 VR 模式时退出，这轮不作为佩戴或帧时序基线。[硬件和连线实测](device-openxr-check.md) · [原厂 APK 研究](apk-research.md)

本地样本位于 `.research/cv10-oem-optics/`。以下 SHA-256 用于核对样本，厂商 APK、库和逐机标定留在本地。

| 样本 | SHA-256 |
| --- | --- |
| P40 原厂 VR 服务 `p40-hvrsdkserverapp-3.5.0.82.apk` | `e0af366239d1c9c8ad384651a3173dfdfccac9ba221768f4db6c5349101d1444` |
| `libvrsdk.so` | `f1e4e63d0e876313b910115fda33408b0aaefb637f693113e79c64aea95b4af2` |
| `libruntime_service_module.so` | `8302398ae2acff8245a59f8cac0f5be187907972637e8b58148be92a20f00716` |
| `vrglass.xml` | `8072a8d4c3c6c3b308b5c3defa31ae5e1cf39c9c105e97a879552a68ad1f7a91` |

1. **开屏与重连。** 按同一接线顺序记录 USB 枚举、PCUI 切换手机来源、开屏应答、外显首次呈现和实际首个发光帧。用外显截图和镜片照片判定黑屏属于提交、链路还是面板。记录从接线到首个画面的时间，以及退出重进和重连的成功率。[PCUI 接口记录](usb-panel-research.md)
2. **双目和姿态。** 用相同左右眼网格及固定姿态检查眼别、旋转、视场、畸变和眼距。对静止及三个轴的受控转动记录 IMU 时间戳、轴向、漂移和置中行为。各实现的读数与镜片证据一起留档。
3. **合成与定位。** 使用同样的外显模式比较实际呈现频率、帧间隔和追踪到呈现延迟。随后接入 CF20 与定位套件，用已记录的 HID、校准及 Y8 对照追踪有效性和重新捕获。[CF20 与 6DoF 资料](../controller/README.md)
