# PiliPlus VR · Fold7 / CV10

从项目根目录执行 `python ports/piliplus/build.py`，默认产物为 `.research/piliplus/PiliPlus-CV10.apk`。需要 Windows、Python 3.11+、Git、Java、Android Build-Tools 36.0.0、NDK r28c 和本机 Android debug.keystore。SDK 可用 ANDROID_HOME 指定，独立 NDK 可用 ANDROID_NDK_HOME 指定。本机 NDK 来自 SDK 安装缓存，可在 PowerShell 设置后构建：

```powershell
$env:ANDROID_NDK_HOME = "$env:LOCALAPPDATA/Android/Sdk/.temp/PackageOperation01/unzip/android-ndk-r28c"
python ports/piliplus/build.py
```

脚本校验 11.19 源包散列，从源码重建原生渲染库，复用包内 Flutter 和 Java 播放逻辑，合入 Khronos loader 的 Android 发现声明。APK 使用本机开发签名，沿用包名 com.example.piliplus。运行时选用项目装好的 Monado。播放器从首页选择视频后点播放，默认自动进入 VR，返回键退出。

2026-11-25，Fold7 通过无线 ADB 安装后从推荐页选片并播放。mpv 成功切换到 VR SurfaceTexture，OpenXR 进入 FOCUSED，圆柱图层使用 1920×1080 视频交换链，连续两个三秒窗口接收 90 和 91 帧。此轮只验证手机端，镜片图像与眼镜运动留待接回头显后验收。项目 [Globalka 移植](../globalka/README.md) 已验证显示与眼镜 IMU，可作为实机对照。该姿态源属于 Globalka 应用，当前 PiliPlus 的姿态由 Monado 提供。

后续移植可使用项目的 [cv10-openxr-port skill](../../.agents/skills/cv10-openxr-port/SKILL.md)。
