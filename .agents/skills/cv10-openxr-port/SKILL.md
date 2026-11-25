---
name: cv10-openxr-port
description: 将 Android 独立头显上的 OpenXR 播放器或应用适配到 Galaxy Fold 与 HUAWEI CV10，建立可重建 APK 的源码补丁并验证播放和镜片输出。
---

从工程 README 和 docs/device-openxr-check.md 确认手机、运行时、外显模式与追踪来源。记录输入版本和散列，从发行包的构建入口向回追踪实际打包的 Activity、JNI、loader、视频输出和输入处理。发行包中 Flutter 的 Kotlin 样例与最终 APK 的 Java 类有时属于不同版本。

用目标设备上的 OpenXR 样例建立基线。核对最终 APK 和 loader AAR 清单中的 Broker provider、服务查询、权限和 ABI。对照实际枚举的扩展，检查所有必需项、函数指针加载和实际调用。逐条分析播放器使用的交换链、图层及输入后备路径。直接交付 Android Surface 与通过 SurfaceTexture 向 GLES 交换链送帧的依赖不同。可选扩展缺失时也要覆盖重建、释放和再次进入。

优先沿用上游构建入口。若发行包由 apktool、预编译 Flutter 资产和可重建 JNI 组成，可参考工程 ports/piliplus/build.py 和 monado.patch。为新应用独立记录输入摘要、补丁、工具版本与构建命令。临时目录应用补丁，核对 ABI、签名、对齐及最终清单，再输出 APK。换签时检查已安装包，保留用户应用数据。

在明确的 adb 设备上从默认显示屏启动。先走正常播放器入口，记录实际媒体时间进度、解码、VR 切换、提交与退出恢复；直接启动 VR Activity 适合单独定位会话初始化。检查镜像模式、外显活动分辨率、合成图层，分别验证双眼镜片。固定手机转动眼镜，确认姿态输入来源。写清哪一项由日志、镜片观察或用户操作证实，以及仍需具备的条件。
