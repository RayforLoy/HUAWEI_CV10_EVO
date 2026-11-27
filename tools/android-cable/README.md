# CV10 连接线安卓升级工具

本地 APK 位于 [firmware_update/tools/android/CV10-Cable-Updater-2A-arm.apk](../../firmware_update/tools/android/CV10-Cable-Updater-2A-arm.apk)。同一个包包含 `arm64-v8a` 和 `armeabi-v7a`，需要 Android 8.0 及以上和 USB Host 支持。

工具内置 Windows 试验中点亮 CV10 的 `C9.49.6-2A-input-observer.bin`。它将 RT9471 的外部输入限流由 1.00 A 提到 2.00 A，保留原厂的电芯充电控制。预检核对已知的 C9.49.6 或 C9.52.6 镜像。升级后的版本字段显示 C9.49.6。[2.00 A 原厂线实测](../../docs/cv10-original-cable-handoff-20261126/charging-ab.md#2-a-输入限流下原厂手机线在-windows-点亮-cv10)

1. 拔下 CV10。将 5 V / 2 A 电源接在线盒充电口，再把标有“连接手机”的一端接入运行工具的手机。
2. 在工具中勾选两项接线确认，阅读升级风险后确认写入。允许系统的 USB 授权。设备重枚举时，系统可能再次询问。
3. 保持接线、供电和工具在前台。工具先双读并保存原固件，再写入和回读有差异的扇区。完成后可用“导出最近备份”把原固件保存到下载目录等位置。

Windows 构建使用 Android SDK Platform 36、Build-Tools 36.0.0、NDK 26.3.11579264 与 JDK。脚本校验固件 SHA-256 后打包，并在本机目录 `.research/android-cable-updater` 保存该 APK 的签名密钥。

```powershell
python tools/android-cable/build.py
```
