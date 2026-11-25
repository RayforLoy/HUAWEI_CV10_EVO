# 跨电脑协作指南

项目当前目标是在 Galaxy Z Fold7 上用标准 OpenXR 应用驱动 HUAWEI VR Glass CV10。另一台电脑接手时，以 Git 提交、发布附件摘要与实机读数对齐进度。四个会话的工作索引见 [README](README.md)。

## 接手工作树

当前协作分支为 `codex/cv10-phase1`。在仓库根目录运行以下命令，核对本机分支、未提交工作、与远端的差距，以及发布标签对应的源码。新检出可用 `git clone --branch codex/cv10-phase1 https://github.com/RayforLoy/HUAWEI_CV10_EVO.git`。

```powershell
git fetch origin --tags
git status --short --branch
git log --oneline --left-right HEAD...origin/codex/cv10-phase1
git log -1 --oneline v0.1.1
```

已在协作分支且工作树干净、仅落后时，用 `git pull --ff-only` 同步。遇到两端都有提交或本地改动时，先核对差异，保留其他会话的工作。交接时分别记下测试用提交或 APK 摘要、机型、接线、验证结果和剩余问题。在报告中区分本地提交、远端分支与已发布版本。

## 在新电脑上复现

- **直接安装**：从 [v0.1.1 Release](https://github.com/RayforLoy/HUAWEI_CV10_EVO/releases/tag/v0.1.1) 下载 Android arm64 APK 和 Windows x64 连接线工具。用 `Get-FileHash <文件> -Algorithm SHA256` 与发布页核对。另一台电脑自行构建通常使用不同的 Android 调试证书；覆盖安装已有运行时时优先使用同签名的发布 APK。
- **构建 Monado**：依赖版本和 Gradle 命令见 [Monado 构建说明](ports/monado-cv10/README.md)。v0.1.1 从 Monado 提交 `ce2b721eb4ffcbd726fb88357625f55871a8f262` 开始，依次应用 `cv10.patch`、`framevote90.patch`、`primary-mailbox.patch`、`launcher-name.patch`、`shizuku-120.patch`。每个补丁先执行 `git apply --check` 再应用；最后一个补丁含重连修复。主说明的首段构建示例只应用基础补丁，构建此版本时须补齐这条序列。[Shizuku 构建与恢复说明](ports/monado-cv10/shizuku-120.md)
- **移植其他应用**：可复用仓库内的 [OpenXR 移植流程](.agents/skills/cv10-openxr-port/SKILL.md)。[Globalka](ports/globalka/README.md) 已实测手机和 Windows 桌面投屏；[PiliPlus](ports/piliplus/README.md) 已验证手机端播放，仍待其自身的镜片与头动验收。
- **本地资料**：`.research/` 是本机构建、日志和厂商样本的工作目录，`resources/` 放本地输入和产物，两者均被 Git 忽略。新电脑上需另外准备所需上游源码、SDK 或样本；目录名和 ADB 序列号以当前机器为准。

## 设备与验收

1. 用 `adb devices -l` 找出当前 Fold7 的序列号。另一部 P40 Pro+ 可能同时在线，所有手机操作使用 `adb -s $serial …`。Fold7 可通过无线 ADB 观察，USB-C 口接已验证的普通 C-C 线与眼镜。三星 DeX 外接显示器选择「已镜像」。
2. Broker 选择 **Monado CV10**（`org.cv10.monado.out_of_process`）。官方 Monado 可共存。以未经修改的 Khronos OpenGLES `hello_xr` 测试；样例 APK 的 SHA-256 为 `29ae01ef6a4fea41d67816f7051698f2694ab08ced4c16c02bdd978e62975962`。确认 USB 访问已允许、OpenXR 会话进入 FOCUSED，再分别拍摄左右镜片。
3. 测手机独立高刷时，在手机上启动 Shizuku，通过其「已授权应用」逐项确认 **Monado CV10** 开关，并在 Monado 菜单启用独立 120 Hz。保持旧 ADB 会话提频脚本关闭。记录手机主屏活动模式、眼镜面板模式和眼镜图层不同呈现时间戳的频率。这三项典型读数分别为 120 Hz、90 Hz、约 90 次/秒。按返回键退出后核验系统最低刷新率恢复原值。[重连实测](research/evidence/fold7-cv10-shizuku-reconnect.json)
4. 黑屏或帧率异常时可从以下只读命令开始。通过 SurfaceFlinger 的显示名称和图层列表查当前 ID，每次插拔都可能改变逻辑显示 ID。此次已验证手机端重启 Shizuku 后重新提频；完整的「拔线 → 重启 Shizuku → 接线 → 打开样例」仍待一轮独立记录。

```powershell
adb -s $serial shell dumpsys SurfaceFlinger --display-id
adb -s $serial shell cmd display get-active-mode 0
adb -s $serial shell settings get system min_refresh_rate
adb -s $serial logcat -d -s Cv10RefreshLease MonadoCV10
```

## 原厂线与发布

Windows 连接线工具面向单独接入电脑的原厂手机线。C9.49.6 已双读备份并完成零差异预检，尚待同板型新版供体和实物升级验证。头显升级包与线缆镜像各有独立目标，操作前核实设备和镜像类型。详见[连接线实测](docs/cable.md)和[头显固件研究](docs/firmware-resource-analysis.md)。

发布时把标签固定到已推送的提交，核对 APK 包名、签名及两个附件的 SHA-256。仓库共享补丁、工具源码和筛选后的证据；发布附件使用项目构建的运行时和诊断工具，厂商样本保留在本地。
