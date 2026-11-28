# CV10 安卓线盒工具

适用于通过 USB 主机模式识别为 VIA VL105（`2109:0105`）的 HUAWEI VR Glass CV10 原厂手机线。APK 包名为 `org.cv10.cabletool`，最低支持 Android 8.0。工具通过 Android 的 USB 授权访问控制端点，无需 root。

[v1.2 APK](../../firmware_update/tools/android/CV10-Cable-Tool-Android-v1.2.apk) · [APK SHA-256](../../firmware_update/SHA256SUMS) · [固件索引](../../docs/firmware-update.md)

## 读取、备份与刷写

1. 打开 **CV10 线盒工具**，点 **读取线盒**，允许 Android USB 访问。四个 C9.53.6 镜像报告相同的版本号，可通过预检读回的 SHA-256 区分。
2. 点 **备份与预检**。工具进入 VL105 维护模式，双读 49,152 字节镜像，核对 CRC、镜像头和写入区。线盒重新枚举时，按系统提示再次授权。预检通过后页面显示当前镜像的 SHA-256 和备份文件路径。
3. 选择目标固件，点 **查看风险并确认刷写**。核对当前镜像、目标镜像及预计擦写的扇区。勾选风险确认框后才可启动刷写。
4. 保持线盒供电和当前接线。工具再次比对线盒内容与备份，逐扇区擦写并回读，完整镜像验证通过后才重启。如果写入中断且 USB 仍可通信，工具会尝试恢复原固件。断电或 USB 断开可能使线盒无法启动或无法恢复。

| 内置镜像 | CRC-16/USB | SHA-256 |
| --- | --- | --- |
| C9.49.6 原版 | `1a69` | `f16057065c4c29d6d86901239371f2a6aab2bcf03c6976505c8f5971fba93e02` |
| C9.52.6 原版 | `2dcb` | `1ebf1217d0dda526f64ed3b15504db409fbdf25bc866f0fbebb874adcd00485a` |
| C9.53.6 原版 | `d0db` | `8e8d9d0df2809f2d3a673519834c83662acc5be6635060d75ef246133956843e` |
| C9.53.6 供电测试版 | `7ef0` | `ba4fa99083c69bcacbd44b0a7afcbfcde228b5535752bc47c59cea13fc3d1096` |
| C9.53.6 群友版 · 仅 Pin C | `a5cb` | `c9d88fcc5205bfb6f9aa6cdd93839c0bfb056522f542132d9ef028efe1c129f6` |
| C9.53.6 · RT9471 2.5 A ＋ 条件式 2 A | `acc2` | `6b481d03fadb6911b7fe3e51903a8cc48b9029c5cea85dc848ee5c35787d1f9c` |

供电测试版保留 C9.53.6 的版本号和 RT9471 限流设置。在检测到符合条件的 5 V / 3 A 上游固定电源档时，可向手机发布 5 V / 2 A。刷写验证只覆盖线盒运行和镜像回读。眼镜带载时的手机净电流及温升需单独测量。

群友版沿用上述供电改动，并将 DP 能力声明改为仅支持 Pin C。主机若无法使用 Pin C，眼镜可能无画面。 [差异与离线回放](../../docs/cable-c9536-pin-c.md)

RT9471 2.5 A 版保留原厂上游请求。上游完成 5 V / 3 A 协商后，线盒可向手机发布 5 V / 2 A，并保留原厂 1 A 保护分支。离线回放已覆盖合同丢失、原厂回退和手机侧请求边界。

## 本地构建

Windows 需要 JDK 17、Android SDK Platform 35、Build Tools 34.0.0 和 Android 调试签名密钥。`-Stock49` 和 `-Stock52` 默认从 `firmware_update/firmware/cable/stock/` 读取。原版 52 本地样本也可通过 `-Stock52` 指定路径。脚本校验六份输入的 SHA-256 并打包到 APK。可从已归档 APK 的 `assets/` 取出这些镜像供重建使用，也可从原版 C9.53.6 [生成早期供电测试版](../patch_c9536_charging.py)。

```powershell
./tools/cable-android/build.ps1 `
  -Sdk 'D:/Android/sdk' `
  -Jdk 'D:/Java/jdk-17' `
  -Stock53 'D:/local/CV10-C9.53.6-original.bin' `
  -Phone2A 'D:/local/CV10-C9.53.6-PD3A-phone2A-bench.bin' `
  -PinC 'D:/local/C9.53.6-cur-4lane-pinC.bin' `
  -Rt9471Phone2A 'D:/local/CV10-C9.53.6-RT9471-input-2p5A-PD3A-phone2A.bin'
```

默认输出为 `.research/cable/android-app/CV10-Cable-Tool-Android.apk`。Android 需要相同签名才能覆盖安装同包名的上一版。

## Fold7 验证记录

2026-11-27，使用 v1.0 在 Fold7 上验证。原厂线盒接辅助电源，眼镜端已分离。实测读取 C9.53.6，维护模式双读与写入区一致，备份与 C9.53.6 原版摘要一致。随后完成原版到供电测试版的 3 扇区刷写，两处地址区的完整镜像回读均通过，线盒重启后恢复运行。

2026-11-28，v1.1 通过无线 ADB 覆盖安装。五份 APK 内置镜像均核对原文件，前四份与 v1.0 逐字节一致。群友 Pin C 版验证范围为离线差异和回放。

2026-11-28，v1.2 通过无线 ADB 覆盖安装。原有五份镜像与 v1.1 逐字节相同。Fold7 上刷入 RT9471 2.5 A 版后，工具报告完整回读通过，SHA-256 与内置镜像一致。头显重连后，手机日志确认 5 V / 2 A 档，AICL 最低记录为 500 mA。
