# CV10 夜间维护交接 · 2026-11-27

Fold7 SM-F9660 使用读回版本为 C9.53.6 的原厂线、5 V 辅助供电及三星 DeX 镜像。以下时间均为香港时间。

## Moonlight XR 串流

上游 Moonlight XR 能与 Sunshine 配对并协商 HEVC，创建 OpenXR 实例时缺少 Monado 生命周期回调需要的 Kotlin 方法。CV10 移植包保留该方法，并在 Fold7 上进入 `FOCUSED`。RTX 3090 使用 NVENC 推送 2560×1440 HEVC，串流请求 90 fps。CV10 外显实际模式为 3200×1600、90 Hz，双眼合成图和右镜片实拍均取得活动画面。稳定运行时的一次采样约为 60.3 次外显呈现/秒。

Monado CV10 v0.1.2 两次在退出 OpenXR 时崩溃。含卸载修复的预览版及后续 16 KiB 对齐预览版各通过两次退出和同进程重进。左镜片实拍、佩戴转头与键盘回传仍待验收。Moonlight APK SHA-256 为 `581e973086ef5a2a378a542c2d87d32a8d768dc078e9723868f1131948fbaf39`，源码和证据提交为 `d211e34`、`f2a0921`。[构建与补丁](../ports/moonlight-xr/README.md) · [实机记录](../ports/moonlight-xr/evidence/fold7-cv10.md)

## 独立启动器与运行时

Fold7 用独立启动器从 2D 列表直启和从离线 3D 菜单点选原版 `hello_xr`。同一进程两次进入 `FOCUSED`，右镜片两次拍到蓝块，返回时两次均销毁 OpenXR 实例。诊断包的 IPv4 和 IPv6 套接字被系统拒绝，两条路径仍通过。无线 ADB 保留以监测电量，预览包无需 Shizuku。修正后的手机激光笔通过四向姿态注入和右镜实拍，应用内返回、置中、系统边缘返回及底部 Home 手势通过回归。真实手持指向待测。原厂华为桌面样本附有第三方依赖声明，本轮未找到它可 fork 的公开源码及许可证。离线菜单由项目实现。

排查中复现了三星 Freecess 冻结。后续对照在 3D 点选后第 78 秒仍约每秒呈现 60 次，右镜有蓝块，退出时正常销毁实例。启动器会提示受限的后台设置。卸载修复为 `4fe230f`。Fold7 实测为 4 KiB 页，APK 另在 16 KiB Android 16 模拟器验证了安装和原生运行时加载。模拟器缺少所需 Vulkan 扩展时，修复后的启动器可提示重试并返回 2D 列表。

独立启动器的集成候选为主项目 `5300269`、Monado `a8fe12a`。用于断网对照的 ARM64 APK SHA-256 为 `b8c7f725abe8da04535f7858c0d1c2997b9244f6e18f3ed29c064c292a8679df`。[启动流程、构建与验收](https://github.com/RayforLoy/Monado_CV10/blob/a8fe12a431e52dbb6203963ba769b54eb890bbe5/history/fold7-offline-launcher.md) · [手机激光笔实测](https://github.com/RayforLoy/Monado_CV10/blob/a8fe12a431e52dbb6203963ba769b54eb890bbe5/history/fold7-phone-laser-axis.md)

## Pocket XR 兼容实验

Fold7 上的整合预览 `a3d86e5` 也通过了原版 `hello_xr` 的 2D 直启、3D 点选及退出回归，并能从 2D 列表打开原版 Pocket XR 1.6.28 的手机触控板后返回。右镜拍到蓝块、3D 菜单和激光指针。ARM64 APK SHA-256 为 `7b4c258ada835cc6f07882231aa9d9ae99504676e52c5a38bb1413c633b1e216`。

沿用无线 ADB 授权的诊断路径验证了原版 Pocket XR 的双目菜单和 Windows Sunshine 的 HEVC Half SBS 实时串流。外显两眼分别显示蓝色 LEFT 和红色 RIGHT，右镜两次拍到正立的动态 RIGHT。由 Monado 显示外层画面、由 Pocket XR 自带运行时启动原版 `hello_xr` 时，右镜也拍到持续画面。原版运行时的两次退出在 `__cxa_thread_finalize` 崩溃，可选 Broker 客户端加上卸载修复后，两次退出及重进正常。上游 1.6.31 与实测 1.6.28 的运行时库字节一致。

Fold7 CV10 的实时静置样本可约以 1 kHz 送至电脑端原版解析器。使用本机 VPN 的断网 Android 16 模拟器已验证原版应用面板更新、连接释放与重开，也重放了 3,000 帧 Fold7 实录的静置数据。另一轮正式菜单实验收到双目源帧，模拟器最终合成画面仍黑。Fold7 的一键空间、普通应用面板、原版应用消费实时头姿、佩戴转头和左镜光学仍待验收。实验改动与详细证据留在主项目 `codex/cv10-fold7-pocket-integration` 的 `4dbea95`，对应 Monado `codex/cv10-launcher-pocket-integration` 的 `6e0f62a`。

## CF20 手柄与原厂 6DoF 套件

CF20 已静态接入搜索、Android 配对、自动重连和右手 OpenXR 3DoF 输入。原厂 6DoF 套件的实现接入定位器 HID、外接双目 Y8、逐机校准及头显和双手 OpenXR 位姿。诊断 APK 和 Monado ARM64 APK 已通过构建、签名、对齐与离线协议向量。原厂 Windows 库接受合成惯性及双目输入，空白图像按预期无有效视觉位姿。Fold7 的 CF20 配对、Y8、HiAI 模型及头显和双手的有效位姿仍待真机验收。补丁在其记录的 Monado 基线 `9314bea` 上通过应用检查，主项目交付提交为 `1a99162`。[协议、构建和 APK 摘要](../controller/README.md)

## 主板 USB-C 直连与 PC 串流

MSI MAG X670E TOMAHAWK WIFI 后面板的 10 Gb/s USB-C 由 Ryzen 9 9900X 核显提供 DisplayPort Alt Mode，同一端口已用普通显示器验证输出。此前 CV10 接入时，Windows 只向桌面开放 640×480，原厂线外接 5 V / 2 A 时镜片仍黑。夜间跑通的 RTX 3090 路径是 PC 用 Sunshine 编码，再由 Fold7 接收和输出。[电脑接线与时序实测](cv10-original-cable-overnight-20261126.md#电脑实测与镜片记录)

## 值守与 Git 归档

09:30 结束电量监测。无线 ADB 记录的电量范围为 57% 至 78%，结束时为 78% 且正在 USB 充电。未触发低于 20% 的暂停和省电流程。无线 ADB 曾短暂失去读数，随后恢复。设备交回时，Broker 已切回稳定运行时，外显仍为 3200×1600、90 Hz。相机固定朝向右镜，左镜实拍和需要移动设备的步骤留待后续。

共同分支快进合并独立启动器，Monado 子模块指向已验证的 a8fe12a。手柄移植以主项目中的源码补丁交付。本机 Monado 工作树里的手柄改动保留，Pocket XR 实验代码仍在交接所列分支。Git 归档包含源码、文档与所引证据。测试 APK 保存在本机。
