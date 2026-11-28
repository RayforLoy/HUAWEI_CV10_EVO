# Fold7 / CV10 公司电脑交接

2026-11-28，香港时间。此分支冻结 Fold7 混合刷新率、应用渲染和其他会话的研发进度。实验包和证据在 [GitHub 预发布](https://github.com/RayforLoy/HUAWEI_CV10_EVO/releases/tag/cv10-handoff-2026-11-28)。

## 接手

```powershell
git clone --branch codex/cv10-company-handoff --recurse-submodules https://github.com/RayforLoy/HUAWEI_CV10_EVO.git
Set-Location HUAWEI_CV10_EVO
git switch --detach cv10-handoff-2026-11-28
git submodule update --init --recursive
git submodule status --recursive
adb devices -l
```

Pocket XR 的源资源用 Git LFS 管理。只查看源码或使用预编译 APK 时，可以在 clone 前设置 `GIT_LFS_SKIP_SMUDGE=1`。构建前安装 Git LFS 并在 Pocket XR 子模块运行 `git lfs pull`。PiliPlus 有独立构建依赖，版本和来源见其 README。

- Monado CV10 **`3ddf7e0`** 包含显示链、直接渲染、零拷贝、四视图、延迟重投影和 CF20/手机指针的整合。冻结包 `company-freeze` 使用真实 IMU，已构建、核对包名、签名和 16 KiB ZIP 对齐。这个合并后的组合仍待 Fold7 验收。
- Pocket XR CV10 **`b9a2fb1`**，运行代码仍与 **`d6ac61e`** 一致，另加入英文的确定性测试布局配方。PiliPlus **`f236c24`** 包含 VR 浏览、播放和 OpenXR 路径，镜片及头动验收留在该项目。
- 并入 [CF20 指针和腕点模型](../controller/oem-pointer-rendering.md)、[华为六个 APK 的可复用接口](cv10-oem-reuse-audit.md)、[线材工具 v1.2](../tools/cable-android/README.md)及 [C9.53.6 充电跟进](cable-c9536-fold7-charging.md)。[Moonlight](../ports/moonlight-xr/README.md) 的补丁、实测记录和同一 APK 一并保留，左镜及佩戴转头仍待验。原厂样本、调试凭据和含桌面内容的原始抓屏保存在原研究机。

## 实测结论

对照机为锁定的 Galaxy Z Fold7 SM-F9660，系统构建 F9660ZCUDBZJ9，原厂 53.6 试验线盒接辅助供电，三星外显「已镜像」，CV10 活动模式 3200×1600 @ 90 Hz。每次接线重新读取外显 ID。先用原版 Khronos OpenGLES Hello XR 做双眼出画和姿态基线，记录手机实际亮屏状态、活动刷新率、外显物理模式和实际呈现频率。

| 条件 | Monado 提交/秒 | CV10 实呈/秒 | 新 Pocket XR 源帧/秒 |
| --- | ---: | ---: | ---: |
| 内屏亮着 60 Hz，四视图对照 1 | 89.86 | 60.33 | 59.60 |
| 内屏亮着 60 Hz，四视图对照 2 | 89.93 | 60.31 | 59.51 |
| 内屏熄灭，CV10 领跑，四视图对照 2 | 90.00 | 89.53 | 83.19 |
| 熄屏，预算等待关闭 → 开启 | 90.00 → 90.00 | 87.80 → 89.40 | 87.26 → 86.26 |

- 在亮屏 60 Hz 时，Perfetto 把瓶颈缩小到 SurfaceFlinger 的同步 HWC 提交和共享的显示连接锁。手机提交等待上一个 retire fence 时，CV10 也可能在进入 DRM 前被阻塞。独立缓冲、渲染格式和应用时序对照仍约 60 次实呈。九个 AOSP 改动与 Qualcomm retire 前置等待是源码原型。Fold7 没有替换系统或 HAL。[完整实验线索、补丁与分析方法](../ports/Monado_CV10/history/fold7-independent-present.md)
- 用授权过的无线 ADB 启动可自动恢复的内屏熄灭脚本，Hello XR 观察到 60.3 → 90.0 → 60.3 实呈/秒。该显示控制路径不依赖 Shizuku。Pocket XR 的可信虚拟屏和应用启动仍按现有 Shizuku 流程授权。另有使用真实 IMU 的 Monado 内置熄屏对照拍到右镜画面。
- Pocket XR 通过 AHardwareBuffer 直接交付四视图，双眼由 1600² 全视场和独立 1280² 中心组成 3200×2880 图集。GLES 外围可用 2×2 分片速率，中心保持 1×1。一个配对合成对照中，融合 Vulkan Compute 的 GPU p95 从 10.85 ms 降到 4.24 ms。把全视场缩到 1280² 没有得到可重复的优势。
- 500 µs fence 等待的熄屏结果中，新源帧仍下降约 1 次/秒。亮屏开启组还出现了 1.5 ms 的实测等待尾部。第四组亮屏关闭在 CV10/ADB 断开前没有有效采样。默认继续关闭等待。近期转头对照使用模拟 IMU，证明了时序和源帧行为。最近固定右镜相机没有解析出工作区，实物拖影、中心清晰度和端到端光子延迟仍待佩戴与光学复测。
- 最后一轮恢复 APK 的两次安装都返回 Success，随后无线 ADB 变为离线。恢复联网后先查 [APK 摘要](../research/evidence/fold7-handoff-apks-20261128.sha256)、面板和时钟状态，再继续。此前 OFF 组日志均记录了面板复位。

## 下一次测试

1. 先验真实 IMU 整合包的 Hello XR 双眼、3D 菜单点选及 CF20 回正。检查右镜固定相机或由佩戴者分别确认两眼。原厂线若在外显截图有画、镜片无画，按工作树的黑屏排查流程记录后再复测。
2. 依照 [测试工具和操作说明](../tools/fold7-present/README.md) 跑同一场景的 ON/60 和临时 OFF 对照。用同一截图布局、GLES FFR 状态、皮温基线与同长度连续转头，分别保存 SurfaceFlinger 呈现、Monado GPU 与 Pocket XR 源图像更新。低于 20% 停止高耗能测试，充到 30% 再恢复。
3. 亮屏独立 90 Hz 的下一步是通过同一时钟对比 SF、HWC/Composer 和共享连接锁，以确定能否在手机旧帧未 retire 时先推进 CV10。源码模型只在独立的可调试 Android 环境验证。Pocket XR 继续查 ready atlas 到 runtime latch 的相位，保留零拷贝与中心尺寸，先用 A/B/A/B 确认稳定收益。

[本轮逐组数值与热状态](../research/evidence/fold7-present-handoff-20261128.txt) · [Android 与镜片检查](device-openxr-check.md) · [跨电脑基础指南](../AGENTS.md)

## 冻结后续测入口

从发布标签复现实验 APK 和全部固定版本。要用以下续测工具，检出本交接分支的最新提交，再用标签固定的 APK 作基线。两个 Monado 分支各自从冻结版分出，可用独立工作树复现。

- 显示链分支 `026d882` 将静止手机输出复用、手机旧帧未完成时的准入判断放进同一份 AOSP 实验系列。补丁通过源树应用和反向检查，栅栏判定通过主机边界测试。还需系统构建及 Fold7 实测。[补丁和回放说明](https://github.com/RayforLoy/Monado_CV10/blob/026d882c0cf24afa74e23aacda3314a298228f8b/history/fold7-independent-present.md)
- 渲染分支 `29cf882` 含 GLES 管线的就绪栅栏实验、融合四视图重投影预计算和可选畸变坐标打包。打包后每个输出像素的畸变纹理读取从三次减至两次，已构建 ARM64 APK，主机逐像素核对通过。Fold7 上的 GPU 时长及镜片验收仍待测。[构建及对照说明](https://github.com/RayforLoy/Monado_CV10/blob/29cf8827f4b3a08cadda7bc4e67d6dc8d73877f8/history/fold7-independent-present.md)

[双屏硬件呈现统计工具](../tools/fold7-present/README.md#analyze-and-trace)已用原 Fold7 追踪复查。取每段起点后 1 秒开始的同长度 20 秒，`pocket-ready-cadence-pair2-{lit,off}-default-calibrated-true-0-2.0.perfetto-trace` 的结果如下。较长间隔指相邻外屏 retire 之间超过 16.667 ms。

| Pocket XR 对照 | 手机 retire/s | CV10 retire/s | CV10 每秒范围 | CV10 较长间隔 |
| --- | ---: | ---: | ---: | ---: |
| 亮屏 60 Hz | 60.30 | 60.30 | 60–61 | 584 |
| 内屏熄灭 | 0 | 89.70 | 87–90 | 5 |

这里统计的是两块屏同一窗口里的内核栅栏数量。续测时同时记录手机内屏模式、Pocket XR 新源帧数、眼镜图层实际呈现和镜片画面。
