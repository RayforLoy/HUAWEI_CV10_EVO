# HUAWEI VR Glass CV10 跨平台点亮与开源项目调研

调研日期为 2026-11-25。本文关注 CV10 镜片能否显示主机输出的可辨认内容，以及哪些公开实现能继续提供双目渲染和头部追踪。资料包括项目源码、作者验证记录、NVIDIA 开发者论坛、华为开发者与支持文档、B 站公开检索结果和本工作区已有实验。本次未重新操作硬件。

## 三星点亮到了哪一步

| 主机 | 可以确认的结果 | 仍缺的证据 |
| --- | --- | --- |
| 三星平板 SM-X806B，Android 16 | 最符合线索的是 **samrat1games/huawei-vr-glass-globalka**。作者在连接眼镜的实机上用无线 ADB 看到外屏 `HUAWEIAV03`、3200×1600、`FLAG_PRESENTATION`，当时系统已自动镜像。项目还记录了佩戴者通过镜片检查画面后纠正两眼旋转方向。这比仅有安装成功或系统截图更能支持“镜内可见”。[作者逐版验证记录](https://github.com/samrat1games/huawei-vr-glass-globalka/blob/266dbe02e115c7aeed936dedc2d1924ae375bc8c/docs/verification.md) | 未找到包含线材、供电、完全断电后插拔顺序及连续显示时长的一套完整记录。无法据此推算其他三星设备的成功率。 |
| Galaxy Z Fold7，普通 C-C，CV10AC 10.0.1.357 | 本工作区已有**左眼镜片实拍**。DeX 扩展时外屏为 640×480 @ 60 Hz，开屏命令应答成功，镜内仍黑。保持接线切到「已镜像」后，系统列出 3200×1600 的 70/90 Hz 模式，当时选中 90 Hz。重开测试图并再次发开屏请求后，左眼拍到蓝底白箭头，随后也拍到官方 OpenXR 样例的方块。[同轮时序与操作记录](usb-panel-research.md) · [左眼箭头](../research/evidence/fold7-mirror-left.jpg) · [左眼 OpenXR 画面](../research/evidence/fold7-hello-xr-left.jpg) | 这轮先后改变了显示模式、应用状态，也重复发送了开屏请求。各操作对冷启动的必要性仍待测。照片只覆盖左眼，持续显示稳定性也需录像。 |
| Galaxy Z Flip5 | EnYaoJingYa 的实测在固件 10.0.1.357 上读到了含报告 ID 的 60 字节 IMU 帧，约 160 Hz。这个频率描述姿态采样，与面板刷新率是两个指标。[Flip5 取证记录](https://github.com/EnYaoJingYa/huawei-vr-compat/blob/03bf1012493fd821f38114010e4b21fe20f1d4f1/docs/evidence/proximity-battery-2026-09-16.md) | 该条 HID 实验没有提供可核对的镜片图案；项目归档时也将完整移植流程标为未完成。 |

**判断。** “至少有三星设备能让 CV10 镜内出图”有具体机型和观察记录支持，其中 Fold7 还留有光学照片。Fold7 上的 Monado 样例运行在默认屏，Android 将结果镜像到眼镜，姿态来自手机传感器。要达到本项目的完整 OpenXR 目标，还需验证右眼、独立双目输出和眼镜自身的追踪。华为官方兼容范围仍限定于所列华为／荣耀系统和机型。[Fold7 OpenXR 日志解读](device-openxr-check.md) · [华为兼容说明](https://consumer.huawei.com/cn/support/content/zh-cn00776811/)

## “能点亮，但闪烁”的原始出处

**B 站评论仍待定位。** 以“华为 VR Glass／CV10、三星／非华为、点亮／闪屏／闪烁”和项目名交叉检索，找到了 CV10 相关视频，但未取得能定位该评论的 BV 号与楼层、评论直链或原图。下列视频只是检索命中，不能将这句话归给其作者或评论区。评论者使用的主机、线材，以及“闪烁”指双眼反复熄灭、局部撕裂还是相机拍到的条纹，目前均未知。[B 站检索命中的 VR Glass 视频](https://www.bilibili.com/video/BV1HbT26sEQM/)

**NVIDIA 论坛有可追溯的相似现象。** 2021 年 Xavier NX 的测试者将眼镜 USB 接有源集线器，DP 先接笔记本，再移接 Jetson。第 20 楼明确记录镜内能看到桌面，同时有严重撕裂。关闭 X 后能点亮背光，却看不到预期测试图；第 46 楼提到一次调整后只有一眼正常，恢复相同设置也未能重复。作者还在另一台 Ubuntu 20.04 电脑上报告直接出图。这组实验说明接线顺序、主机和观察位置值得记录，但没有建立与 B 站评论相同的故障原因。[实验序列，第 20 楼](https://forums.developer.nvidia.com/t/display-to-huawei-vr-glasses/169464/20) · [单眼现象，第 46 楼](https://forums.developer.nvidia.com/t/display-to-huawei-vr-glasses/169464/46) · [另一台电脑的对照，第 17 楼](https://forums.developer.nvidia.com/t/display-to-huawei-vr-glasses/169464/17)

## 可复用的公开项目

以下按项目实际处理的问题列出。仓库内的社区源码、原厂 SDK、原始 APK 和驱动二进制分别列明；发布了安装包的项目，仍可能依赖专有组件。

| 项目与平台 | 作者公开了什么 | 对 CV10 研究的用途与前提 |
| --- | --- | --- |
| **Globalka** · 三星 Android 平板 | 使用 Android 外屏和自绘渲染器向眼镜显示内容。作者保留了早期两眼同向旋转、后来按佩戴反馈修正的过程；最终记录要求左右眼旋转方向相反。 | 适合对照外屏窗口、眼别和逐眼方向。系统在应用启动前就能镜像，渲染器源码不能单独解释主机如何协商到原生时序。[渲染源码](https://github.com/samrat1games/huawei-vr-glass-globalka/blob/266dbe02e115c7aeed936dedc2d1924ae375bc8c/app/src/main/java/org/vrglass/bridge/VrSceneRenderer.java) · [验证历史](https://github.com/samrat1games/huawei-vr-glass-globalka/blob/266dbe02e115c7aeed936dedc2d1924ae375bc8c/docs/verification.md) |
| **huawei-vr-compat** · Flip5／通用 Android 移植 | 公开华为七包的依赖梳理、兼容层、补丁及 HID 实验。作者在 2026-10-19 暂停并归档，记录了原厂 APK、KernelSU 与 LSPosed 的角色。 | 最适合查华为系统服务依赖、USB 接口和传感器报告。复用协议知识与整套移植的系统权限要求不同。[项目状态](https://github.com/EnYaoJingYa/huawei-vr-compat/blob/03bf1012493fd821f38114010e4b21fe20f1d4f1/docs/PROJECT_STATUS.md) · [HID 协议记录](https://github.com/EnYaoJingYa/huawei-vr-compat/blob/03bf1012493fd821f38114010e4b21fe20f1d4f1/docs/HELMET_HID_PROTOCOL.md) |
| **HuaweiVRGlass-ALVR-Android** · 一加 7T | 作者提供自研 OpenXR 兼容层、ALVR 客户端、双目合成和 HID 探针。7T 使用 32 位应用兼容层，姿态方案配有 root 侧模块。作者将一种约每十秒进入纯色待机的现象追到 SteamVR 场景层消失。 | 可借鉴逐眼旋转、姿态和渲染诊断。这里的待机有具体软件条件，不能直接拿来解释其他主机的闪屏。[项目与修复记录](https://github.com/niceqwer55555/HuaweiVRGlass-ALVR-Android/tree/0a7cc2625db16732e38863a419d4aaeb2cdb1322) · [HID 探针](https://github.com/niceqwer55555/HuaweiVRGlass-ALVR-Android/blob/0a7cc2625db16732e38863a419d4aaeb2cdb1322/src/xr/jni/hidprobe.c) |
| **HuaweiVRGlass-ALVR** · 华为手机 | LHT02 的同名系列基于 ALVR 20.14.1，作者报告在 LYA-AL00、HarmonyOS 4.2、华为 VR Runtime 3.5.0.82 上以 3200×1600、70 Hz 串流，配 6DoF 套件。 | 是原厂运行时正常工作后的性能和功能对照。与一加分支同用 ALVR，但手机端运行时不同。[作者验证配置](https://github.com/LHT02/HuaweiVRGlass-ALVR/tree/a4e75760ababc10a6686f52585207c85253429a7) |
| **HwVRGlassLite** · Windows | 公开桌面模式、HID 姿态读取和驱动切换逻辑；发行包另带原厂及补丁驱动。桌面模式可独立于 SteamVR 绘制。 | 可借鉴 PC 端眼镜 IMU 与桌面渲染，也可用已知能出图的 PC 检查眼镜。Windows 驱动依赖限制了向 Android 直接移用的范围。[项目说明](https://github.com/fkun1754/HwVRGlassLite/tree/e1550db5e4f4d106b2b76912fc797ccd60013444) · [IMU 实现](https://github.com/fkun1754/HwVRGlassLite/blob/e1550db5e4f4d106b2b76912fc797ccd60013444/desktop-mode/src/dm_imu.cpp) |
| **Wolvic 的 Huawei 构建** · VR 浏览器 | 构建文档分别列出华为 VR 的 hvr 目标与 Vision Glass 的 visionglass 目标。前者要求另行提供华为 SDK。 | 适合研究已有运行时如何承载 WebXR 内容；复现浏览器构建前须明确接入的是哪款眼镜。[Huawei 构建说明](https://github.com/zykool/wolvic-huawei-vr/blob/HEAD/README.md) |
| **Monado** · freedesktop.org GitLab | 开源 OpenXR 运行时。本工作区的 Android 构建实测能运行官方 hello_xr，系统名为 Monado: Android Sensors。 | 可作为运行时起点。已有镜内实拍与默认屏合成记录可用于检验后续 CV10 直出和头显 IMU 接入是否真正改变了输出路径。[上游源码](https://gitlab.freedesktop.org/monado/monado) · [Fold7 实测](device-openxr-check.md) |

## Fold7 最值得补的三组证据

1. **测冷插条件。** 使用已在 P40 Pro+ 和 Fold7 上出过图的同一副眼镜、同一根普通 C-C 线，每轮先断电。在镜像模式分别记录仅插线、启动测试图、发送开屏请求后首次出现可辨认图案的时刻，再用 DeX 扩展模式作对照。每轮记实际物理时序，避免把 DeX 逻辑桌面大小当成面板信号。[本机接线对照](../README.md) · [历史开屏时序](usb-panel-research.md)
2. **把“闪”记录成两条同步证据。** 左右眼各显示不同字母、方向箭头和递增计数器。保留镜内连续录像，同时记录肉眼观察、外显模式变化、USB 断连及合成帧。若仅手机录像出现条纹，另记相机帧率和曝光；若双眼肉眼同时熄灭，优先看同一时刻外显是否仍在。单张截图不足以判断持续稳定性。
3. **验收眼镜自身追踪。** 双眼图案通过后固定手机，仅转动 CV10，同步记录 HID 样本与镜内画面。这样才能判断应用姿态是否来自眼镜，并将结果与当前 Monado 手机传感器基线比较。[Flip5 的 HID 对照样本](https://github.com/EnYaoJingYa/huawei-vr-compat/blob/03bf1012493fd821f38114010e4b21fe20f1d4f1/docs/evidence/proximity-battery-2026-09-16.md) · [Fold7 当前运行时](device-openxr-check.md)
