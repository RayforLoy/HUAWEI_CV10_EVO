# HUAWEI CV10 EVO

项目目标是在 Galaxy Z Fold7 上运行标准 OpenXR 应用，由 HUAWEI VR Glass CV10 显示独立双目画面并提供头部 3DoF。Fold7 上未经修改的 Khronos `hello_xr` 已通过双眼镜片实拍、立体视差和眼镜姿态验证。当前使用定制运行时 **Monado CV10**。

[下载 Monado CV10 v0.1.3](https://github.com/RayforLoy/Monado_CV10/releases/tag/v0.1.3) · [Windows 连接线工具（主项目 v0.1.1）](https://github.com/RayforLoy/HUAWEI_CV10_EVO/releases/tag/v0.1.1) · [跨电脑接手指南](AGENTS.md)

## Android 源码与安装包

| 项目 | 源码及构建 | 安装包 |
| --- | --- | --- |
| Monado CV10 运行时 | [v0.1.3 源码及构建说明](https://github.com/RayforLoy/Monado_CV10/blob/v0.1.3/README.md)，本地位于 `ports/Monado_CV10` | [v0.1.3 发行版](https://github.com/RayforLoy/Monado_CV10/releases/tag/v0.1.3)，Fold7 选择 arm64-v8a |
| PiliPlus Monado 播放器 | [源码与移植提交](https://github.com/RayforLoy/piliplus_monado)，本地位于 `ports/piliplus_monado` | 在子模块内运行 `python build.py`，产物为 `dist/PiliPlus-CV10.apk` |
| Moonlight XR CV10 串流客户端 | [源码补丁、构建及实机记录](ports/moonlight-xr/README.md) | 构建 `nonRootRelease` 的 arm64-v8a APK。正常退出及重进已使用带卸载修复的 Monado 预览包验证 |

新电脑运行以下命令，获取主项目及对应版本的两个子模块：

```shell
git clone --recurse-submodules --branch codex/cv10-phase1 https://github.com/RayforLoy/HUAWEI_CV10_EVO.git
```

已有工作树更新主分支后运行 `git submodule update --init --recursive`。


## 各会话进度 · 2026-11-26

| 会话 | 已验证 | 待验证或待取得的材料 |
| --- | --- | --- |
| 核对资源并移植OpenXR | 在 Fold7 上，Monado CV10 经 USB 开屏、从眼镜 IMU 以约 1 kHz 采样，官方 `hello_xr` 进入 FOCUSED。两台摄像头分别拍到正读的 L↑、R↑ 和样例方块，双眼水平视差方向正确。[构建及证据](https://github.com/RayforLoy/Monado_CV10/blob/v0.1.2/README.md) | 当前提供旋转 3DoF。镜片畸变、个体瞳距与三轴角度精度待标定；Android XR 通用启动器兼容性尚未验证。 |
| 核对资源并移植OpenXR · 桌面与时序 | Globalka 已把手机桌面和 Windows 桌面投到镜片，接入眼镜姿态。Monado 的 MAILBOX 配合会话刷新率脚本，使外屏图层从约 60 升至 90 次呈现/秒，画面就绪到呈现中位等待从 27.5 降至 10.3 ms，佩戴者确认转头拖影明显减少。[Globalka 移植](ports/globalka/README.md) · [Windows 发送端](docs/windows-desktop-sender.md) · [时序实测](research/evidence/fold7-cv10-frame-pacing.json) | v0.1.0 使用 ADB 会话脚本。[v0.1.1 Shizuku 版](https://github.com/RayforLoy/Monado_CV10/blob/v0.1.2/history/shizuku-120.md) 已验证在手机上启动和恢复；完整运动到成像延迟仍待测量。 |
| 移植 PiliPlus VR 播放器 | 11.19 版已在 Fold7 从推荐页选片播放，mpv 切换到 VR SurfaceTexture，OpenXR 会话进入 FOCUSED。1920×1080 视频交换链在两个三秒窗口分别收到 90、91 帧。[移植与构建](https://github.com/RayforLoy/piliplus_monado/blob/de31798f68501b75c96977e9f64dbaf61944119a/README.md) · [可复用移植流程](.agents/skills/cv10-openxr-port/SKILL.md) | 该轮仅验证手机端播放；仍需用 Monado CV10 对播放器本身做双眼镜片实拍和转头测试。 |
| 核对资源并移植OpenXR · 原厂手机线 | 在接外部 5 V / 2 A、装有 2 A 测试固件的原厂线上，Fold7 独立启动了原版 `hello_xr`。运行时重新取得眼镜 HID 后会再检查来源、发送开屏。先接线再开应用拍到右眼蓝块，用户随后两次复测通过。[实机记录](docs/device-openxr-check.md#原厂线重接时的黑屏) | 已观察到开屏应答 OK 而镜片仍黑的状态。实测保留手机端和供电、只重插眼镜端可恢复；触发条件仍待定位。 |
| 研究固件升级工具 | 原厂 C9.52.6 和 C9.49.6 已做过对照，回刷后双读的 49,152 字节与备份一致。Windows 工具可读电量计原值。[头显升级器](docs/firmware-resource-analysis.md) · [连接线协议](docs/cable-firmware-research.md) · [工具与操作记录](docs/cable.md) | 两个原厂镜像在早期 Fold7 对照中均黑屏；后续 2 A 测试配置的结果见下表。电池健康状况仍待实测。[早期对照与镜片实拍](docs/cv10-original-cable-overnight-20261126.md) |
| 调研 VRglass 点亮开源项目 | 比较了七个项目或构建分支，整理了 Globalka 在三星设备上的出图记录、Flip5 的 IMU 实验和 Jetson 的显示异常。Fold7 本地复测确认同一条普通 C-C 线在 DeX 扩展与镜像模式下表现不同。[开源项目调研与原始出处](docs/vrglass-open-source-survey.md) | B 站所述闪烁评论的原文尚未定位。 |

## 硬件实测 · 更新于 2026-11-26

| 主机与线材 | 镜片观察 | 已确认的系统行为 |
| --- | --- | --- |
| P40 Pro+，普通 C-C | 用户实测可见 | 作为同一副眼镜、同一根线的对照 |
| Windows，普通 C-C | 用户实测 SteamVR 可见 | 本机安装 HiSuite 和 NOLO HOME |
| P40 Pro+，原厂手机线 | 早期测试黑屏；同一根线装入 2 A 测试固件并外接 5 V 后，华为 VR 可见 | P40 使用 3200×1600、70 Hz。[右眼实拍](research/evidence/p40-original-2a-vr-right-20261126.jpg) |
| Fold7，原厂手机线，2 A 测试固件，外接 5 V / 2 A | 原版 `hello_xr` 右眼蓝块可见 | 读取眼镜 IMU。面板 3200×1600、90 Hz，图层实测 89.96 次/秒。[先接线后启动实拍](research/evidence/fold7-original-2a-delayed-start-right-20261126.jpg) |
| Windows，RTX 3070 Laptop，以上原厂线及供电 | 右镜片拍到 SteamVR 菜单，转动眼镜后测得约 14° 姿态变化 | NOLO HOME 连接后使用 NVIDIA 直连 90 Hz。个别会话控制接口掉线，需重插眼镜端。[实测与恢复步骤](docs/device-openxr-check.md#windows-原厂手机线与-nolo-steamvr) |
| Fold7，普通 C-C，三星 DeX 扩展 | 镜片黑屏，摄像头复测一致 | HUAWEIAV03 为 640×480 @ 60 Hz，PCUI 开屏返回 OK |
| Fold7，同一接法，三星「已镜像」 | 左右镜片均拍到正向测试图和官方 hello_xr 方块 | Monado CV10 向 HUAWEIAV03 提交双目画面，使用眼镜 USB IMU；面板活动模式 3200×1600 @ 90 Hz |

**Fold7 启动方法**　在三星 DeX 外接显示器设置选择「已镜像」，在 Khronos OpenXR Runtime Broker 选择 **Monado CV10**。普通 C-C 线可直接接眼镜。使用上表的原厂手机线时，先给线盒接入 5 V，再接已解锁的 Fold7。戴上眼镜，从手机桌面打开 `hello_xr`，系统询问时允许 Monado CV10 访问 HUAWEI GLASS HID。需要手机独立高刷时，启动 Shizuku 并在 Monado CV10 中启用独立 120 Hz。[接线、权限与刷新率验收](AGENTS.md#设备与验收)

## 研究与工具

- [原厂线固件逆向与诊断](docs/cable-firmware-research.md) 对照 C9.49.6 镜像与实机 USB 应答，记录显示与供电功能、配置常量和诊断上位机的使用方法。

- [USB 开屏研究](docs/usb-panel-research.md) 对照公开项目、原厂服务及本机识别出的 PCUI 端点。
- [Fold7 与 P40 真机记录](docs/device-openxr-check.md) 包含无线 ADB、设备版本、当前显示模式和 OpenXR 验证。
- [PC 升级器与眼镜固件](docs/firmware-resource-analysis.md) 给出两份镜像的版本、目标、校验和升级日志。
- [原厂线实测与使用方法](docs/cable.md)和[连接线工具](tools/cable.py) 用于区分线缆控制器与头显，核对固件。运行 `python tools/cable.py --help` 查看命令。
- [Android 显示测试程序](probe/Probe.java) 用系统 Presentation 接口向外屏提交左右眼测试图。Windows 构建命令为 `python probe/build.py`，输出在 `.research/probe/cv10-display.apk`。同一程序可经 USB 读取 CV10 型号、发送开屏命令及短时采集头显 HID 报告。需要 JDK、Android SDK Platform 36 和 Build-Tools 36.0.0。用 `adb -s <设备> install -r .research/probe/cv10-display.apk` 安装。解锁手机并打开「CV10 显示测试」，按屏幕名选择目标。通过 ADB 启动时可用 `adb -s <设备> shell am start --display 0 -n org.cv10.displayprobe/.Probe --ez auto_cv10 true` 在已识别的 HUAWEIAV03 上自动显示。
- [Fold7 点亮手册](docs/fold7-bringup.md)、[原厂 APK 分析](docs/apk-research.md)及[样本清单](research/sources.json)保留复测步骤和前期证据。

## 本地样本与发布范围

`resources/华为VR/` 为用户提供的可用软件集。01 至 06 逐一匹配样本清单；07 的 SHA-256 为 `fd363dbea8f8413e5de0b984e3151432e27fc788e579b72ec542a2a48f02882d`，与 QQ 包内手动提取的服务相同。P40 装机服务版本另见真机记录。QQ 的 Globalka 为 `com.samrat.vrglassbridge 0.14-installer`，可作为外屏参考；Wolvic 为 arm64 浏览器客户端，橙子 VR 仅带 ARMv7 原生库。手柄应用、模型与 PC 助手用于对应外设对照。

项目拟以 GPL 发布原创代码。第三方 APK、厂商升级器、固件和原始真机日志保存在 Git 忽略的本地目录。GPL 允许下游商业分发；如需发布受售后非营利条件约束的材料，其授权范围须另行确认。[GNU GPL FAQ](https://www.gnu.org/licenses/gpl-faq.html#DoesTheGPLAllowMoney)
