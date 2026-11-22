# HUAWEI CV10 EVO

让 HUAWEI VR Glass CV10 在 Galaxy Z Fold7 上工作。项目依次验证有线出图、可独立运行的 OpenXR 双目渲染与头部 3DoF，最终研究 Google Android XR 的接入条件。

第一阶段的 Windows PC 离线分析已完成。P40 Pro+、CV10、Fold7 和可用的 PC VR 线缆用于下一阶段的硬件对照。Fold7 冷插后两眼能否稳定出图仍待实测。

## 研究入口

- [APK 离线分析](docs/apk-research.md) 记录八份 APK 的签名、包名与 ABI，复核华为系统的 USB、外显、VCOM 屏幕控制和 HID 姿态路径。
- [Fold7 点亮手册](docs/fold7-bringup.md) 给出原厂对照、无线采集、三次冷插验收以及后续 OpenXR 和 Android XR 的验收条件。
- [固定样本与 SHA-256](research/sources.json) 列出两个华为官方 SDK、一份 SDK 内嵌 APK、七份社区镜像 APK 和反编译工具。
- 样本、第三方工具、解包树和原始日志位于 `.research/`。仓库跟踪来源、可复现命令和从样本得出的分析。
