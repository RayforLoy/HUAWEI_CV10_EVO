# 跨电脑协作指南

项目当前目标是在 Galaxy Z Fold7 上用标准 OpenXR 应用驱动 HUAWEI VR Glass CV10。另一台电脑接手时，以 Git 提交、发布附件摘要与实机读数对齐进度。四个会话的工作索引见 [README](README.md)。

## 接手工作树

当前协作分支为 `codex/cv10-phase1`。在仓库根目录运行以下命令，核对本机分支、未提交工作、与远端的差距，以及发布标签对应的源码。新检出可用 `git clone --recurse-submodules --branch codex/cv10-phase1 https://github.com/RayforLoy/HUAWEI_CV10_EVO.git`。

```powershell
git fetch origin --tags
git status --short --branch
git log --oneline --left-right HEAD...origin/codex/cv10-phase1
git log -1 --oneline v0.1.1
git ls-tree HEAD ports/Monado_CV10
git -C ports/Monado_CV10 describe --tags --always
```

已在协作分支且工作树干净、仅落后时，用 `git pull --ff-only` 同步。遇到两端都有提交或本地改动时，先核对差异，保留其他会话的工作。交接时分别记下测试用提交或 APK 摘要、机型、接线、验证结果和剩余问题。在报告中区分本地提交、远端分支与已发布版本。

## 在新电脑上复现

- **直接安装**　Fold7 使用 [Monado CV10 v0.1.3](https://github.com/RayforLoy/Monado_CV10/releases/tag/v0.1.3) 的 arm64-v8a APK。Windows x64 连接线工具在[主项目 v0.1.1](https://github.com/RayforLoy/HUAWEI_CV10_EVO/releases/tag/v0.1.1)。用 `Get-FileHash <文件> -Algorithm SHA256` 与各自发布页核对。覆盖安装已有运行时需要相同签名。
- **验证整合功能**　安装 [Monado CV10 v0.1.4-rc.1](https://github.com/RayforLoy/Monado_CV10/releases/tag/v0.1.4-rc.1)，在 Broker 选择 **Monado CV10 Preview**。同一个 APK 提供启动器、Pocket XR 外显、CF20、6DoF 套件和软件瞳距入口。[整合验收与原厂对照](docs/cv10-unified-runtime.md)
- **构建 Monado**　更新干净工作树后运行 `git submodule update --init --recursive`，再按 [v0.1.3 构建说明](https://github.com/RayforLoy/Monado_CV10/blob/v0.1.3/README.md)构建。历史补丁和验证记录位于 `ports/Monado_CV10/history/`。
- **移植其他应用**：可复用仓库内的 [OpenXR 移植流程](.agents/skills/cv10-openxr-port/SKILL.md)。[Globalka](ports/globalka/README.md) 已实测手机和 Windows 桌面投屏；[PiliPlus](https://github.com/RayforLoy/piliplus_monado/blob/de31798f68501b75c96977e9f64dbaf61944119a/README.md) 已验证手机端播放，仍待其自身的镜片与头动验收。
- **本地资料**：`.research/` 是本机构建、日志和厂商样本的工作目录，`resources/` 放本地输入和产物，本地研究目录及 .gitignore 列出的个别大文件被 Git 忽略。新电脑上需另外准备所需上游源码、SDK 或样本；目录名和 ADB 序列号以当前机器为准。

## 设备与验收

1. 用 `adb devices -l` 找出当前 Fold7 的序列号。另一部 P40 Pro+ 可能同时在线，所有手机操作使用 `adb -s $serial …`。Fold7 可通过无线 ADB 观察，三星 DeX 外接显示器选择「已镜像」。可用普通 C-C 直连。原厂线的成功配置为用户已刷 2 A 测试固件的线盒、外接 5 V / 2 A，先接辅助供电，再接已解锁的手机。
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

Fold7 接原厂线后可从手机桌面启动原版 `hello_xr`。记录接线、运行时 APK 摘要和镜片实际画面。在 2 A 测试配置上，外显活动时序为 3200×1600、90 Hz，右镜片拍到蓝块，用户随后复测两次通过。若系统截图有双目方块而镜片仍黑，可保留手机端和辅助电源，拔下眼镜端约 5 秒再接回，按系统提示允许 USB 访问。该操作曾在同一 OpenXR 会话内恢复画面。[重接日志与镜片实拍](docs/device-openxr-check.md#原厂线重接时的黑屏)

Windows 连接线工具面向单独接入电脑的原厂手机线。早期对照使用原厂 C9.52.6 和 C9.49.6，均在 Fold7 复现黑屏，回刷后断电双读与原备份一致。后续 2 A 镜像仍可报告原版本字段，交接时应另记线盒使用的镜像及其来源。详见[连接线实测](docs/cable.md)、[头显固件研究](docs/firmware-resource-analysis.md)及[早期手机、电脑与镜片对照](docs/cv10-original-cable-overnight-20261126.md)。

发布时把标签固定到已推送的提交，核对 APK 包名、签名及两个附件的 SHA-256。仓库共享补丁、工具源码和筛选后的证据；发布附件使用项目构建的运行时和诊断工具，厂商样本保留在本地。
