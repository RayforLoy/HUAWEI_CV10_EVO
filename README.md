# HUAWEI CV10 EVO

让 HUAWEI VR Glass CV10 在 Galaxy Z Fold7 上工作。项目依次验证有线出图、可独立运行的 OpenXR 双目渲染与头部 3DoF，最终研究 Google Android XR 的接入条件。

当前阶段使用 Windows PC 离线分析。P40 Pro+、CV10、Fold7 和可用的 PC VR 线缆留作下一阶段的硬件对照。

## 研究入口

- [固定样本与 SHA-256](research/sources.json) 列出两个华为官方 SDK、一份 SDK 内嵌 APK、七份社区镜像 APK 和反编译工具。
- 样本、第三方工具、解包树和原始日志位于 `.research/`。仓库跟踪来源、可复现命令和从样本得出的分析。
