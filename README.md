# HUAWEI CV10 EVO

项目目标是在 Galaxy Z Fold7 上运行标准 OpenXR 应用，由 HUAWEI VR Glass CV10 显示独立双目画面并提供头部 3DoF。验收时固定手机、转动眼镜，确认应用提交的画面随眼镜转动。

## 当前硬件基线 · 2026-11-25

| 主机与线材 | 镜片观察 | 已确认的系统行为 |
| --- | --- | --- |
| P40 Pro+，普通 C-C | 用户实测可见 | 作为同一副眼镜、同一根线的对照 |
| Windows，普通 C-C | 用户实测 SteamVR 可见 | 本机安装 HiSuite 和 NOLO HOME |
| P40 Pro+，原厂手机线 | 用户实测黑屏 | 手机认出 VR。线单独连接电脑，版本读回为 `0c 09 49 06` |
| Fold7，普通 C-C，三星 DeX 扩展 | 镜片黑屏，摄像头复测一致 | HUAWEIAV03 为 640×480 @ 60 Hz，PCUI 开屏返回 OK |
| Fold7，同一接法，三星「已镜像」 | 左眼摄像头拍到测试图和官方 hello_xr 的蓝色方块 | 活动时序 3200×1600 @ 90 Hz，也列出 70 Hz；Monado 使用手机姿态，右眼尚未独立拍摄 |

**复现已出图的配置**：使用上述普通 C-C 线，在 Fold7「设置 → 已连接的设备 → Samsung DeX → 已连接的显示器」选择「已镜像」。本轮曾先通过 USB 开屏，再切换镜像；尚未从完全断电条件单独验证这条命令的必要性。[镜片实拍与 USB 应答](docs/usb-panel-research.md)

## 研究与工具

- [USB 开屏研究](docs/usb-panel-research.md) 对照公开项目、原厂服务及本机识别出的 PCUI 端点。
- [Fold7 与 P40 真机记录](docs/device-openxr-check.md) 包含无线 ADB、设备版本、当前显示模式和 OpenXR 验证。
- [PC 升级器与眼镜固件](docs/firmware-resource-analysis.md) 给出两份镜像的版本、目标、校验和升级日志。
- [原厂线实测与使用方法](docs/cable.md)和[连接线工具](tools/cable.py) 用于区分线缆控制器与头显，核对固件。运行 `python tools/cable.py --help` 查看命令。
- [Android 显示测试程序](probe/Probe.java) 用系统 Presentation 接口向外屏提交左右眼测试图。Windows 构建命令为 `python probe/build.py`，输出在 `.research/probe/cv10-display.apk`。同一程序可经 USB 读取 CV10 型号、发送开屏命令及短时采集头显 HID 报告。需要 JDK、Android SDK Platform 36 和 Build-Tools 36.0.0。用 `adb -s <设备> install -r .research/probe/cv10-display.apk` 安装。解锁手机并打开「CV10 显示测试」，按屏幕名选择目标。通过 ADB 启动时可用 `adb -s <设备> shell am start --display 0 -n org.cv10.displayprobe/.Probe --ez auto_cv10 true` 在已识别的 HUAWEIAV03 上自动显示。
- [Fold7 点亮手册](docs/fold7-bringup.md)、[原厂 APK 分析](docs/apk-research.md)及[样本清单](research/sources.json)保留复测步骤和前期证据。

## 本地样本与发布范围

`resources/华为VR/` 为用户提供的可用软件集。01 至 06 逐一匹配样本清单；07 的 SHA-256 为 `fd363dbea8f8413e5de0b984e3151432e27fc788e579b72ec542a2a48f02882d`，与 QQ 包内手动提取的服务相同。P40 装机服务版本另见真机记录。QQ 的 Globalka 为 `com.samrat.vrglassbridge 0.14-installer`，可作为外屏参考；Wolvic 为 arm64 浏览器客户端，橙子 VR 仅带 ARMv7 原生库。手柄应用、模型与 PC 助手用于对应外设对照。

项目拟以 GPL 发布原创代码。第三方 APK、厂商升级器、固件和原始真机日志保存在 Git 忽略的本地目录。GPL 允许下游商业分发；如需发布受售后非营利条件约束的材料，其授权范围须另行确认。[GNU GPL FAQ](https://www.gnu.org/licenses/gpl-faq.html#DoesTheGPLAllowMoney)
