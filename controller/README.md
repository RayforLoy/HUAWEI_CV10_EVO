# Huawei VR Glass 原厂手柄与 6DoF 套件

日常走整合版 **Monado CV10 Preview → 更多选项 → CV10 蓝牙手柄**。下方单独的手柄 APK、协议测试和补丁记录对应早期诊断构建。[整合预发布](https://github.com/RayforLoy/Monado_CV10/releases/tag/v0.1.4-rc.1) · [整合验收](../docs/cv10-unified-runtime.md)

| 硬件 | Monado CV10 | 独立诊断 APK | 验证 |
| --- | --- | --- | --- |
| CF20 蓝牙 3DoF 手柄 | 应用内搜索、选用、Android 系统配对、会话自动连接和右手 OpenXR 输入 | GATT 状态、报告频率、原始包、四元数、按键、触控、惯性和电量 | 通过构建和协议测试向量。Fold7 待验收 |
| 原厂 6DoF 套件 | 菜单可启用头显定位，或启用头显加双手定位。前台服务读取定位器 HID、外接 Y8 和逐机校准。双手提供 OpenXR 位姿和按键 | 枚举 USB 和相机，读取原始记录和逐机校准，导出双目帧及头显 SLAM 参数，离线回放头显和双手，实时采样头显 SLAM | 已通过构建、协议向量、Windows 原厂库回放及手柄标定参数对照。Fold7 的外接 Y8、HiAI 和有效 OpenXR 位姿待验证 |

两条协议独立记录在 [CF20 蓝牙协议](cf20-protocol.md) 和 [6DoF 套件协议](kit-6dof-protocol.md)。诊断 APK 与运行时共用发现、配对及报告解码源码。

[原厂手机与 CF20 的控制切换](oem-controller-switching.md)记录原厂 SDK 如何选择输入源、处理重连，以及电源键如何控制手机模型与射线。

[原厂手机操控逆向](oem-phone-controller.md)记录手机的触控分区、手势阈值、姿态射线和回正。

[原厂光标与射线渲染](oem-pointer-rendering.md)记录光标贴图、命中位置、射线几何及深度遮挡。

## 本机产物

| APK | 包名 | SHA-256 |
| --- | --- | --- |
| [Cv10ControllerProbe.apk](dist/Cv10ControllerProbe.apk) | `org.cv10.controllerprobe` | `a12935af38b8d67d21b34052d25ceb1ff44832ebb5fbe58032264c96083c643b` |
| [Monado-CV10-Controller-arm64-v8a.apk](dist/Monado-CV10-Controller-arm64-v8a.apk) | `org.cv10.monado.out_of_process` | `4799f643488010fd79402a081dd2b528e06e387cefe7b91d03ce68cdfbb2f8bb` |

两个 APK 均为本地 ARM64 调试构建，最低 Android API 26。独立诊断和运行时的目标 API 分别为 35 和 31。本机签名证书 SHA-256 为 `68365fa0904432aaa86a8904c691f9e6487414dc959786d72831a083b9f23fca`。运行时覆盖安装需要与已安装的 APK 签名一致。独立诊断 APK 可与运行时并存。两包均通过 `apksigner verify` 和 `zipalign -c -P 16 4`。原厂文件由用户从应用内导入。真机安装、配对、USB／相机采样和 OpenXR 验收待做。

## 使用入口

1. 在 Monado CV10 菜单选择 **CV10 蓝牙手柄**，唤醒 CF20，点击 **Scan for CF20**，允许 Android 所需权限并点选结果。也可填写蓝牙地址。
2. 点 **配对并选用**。Monado 收到报告后保存地址，新建 OpenXR 会话时自动连接。**Android 系统配对**可另外尝试建立系统蓝牙绑定。独立诊断 APK 用 **配对并连接** 保持连接并实时显示输入。
3. 套件在同页的 **定位交互套件** 中。**采样定位器 HID** 显示头部、左手、右手原始记录。**采样 OV580 相机** 显示帧计数，并将首个带有效元数据的双目帧保存为 ZIP。
4. 点击 **读取套件校准**，查看双目、各组件 IMU 采样率及手柄 LED 模型的摘要。定位器、左手、右手的完整回复各保存为独立 ZIP（`locator.zip`、`left.zip`、`right.zip`），每包包含 `calibration.bin` 和 `device.hash`。定位器校准可解码时，额外保存 2112 字节的 `slam-params.bin`。保存路径显示在诊断页中。
5. 使用 **导入原厂头显 SLAM 模块** 选择原厂 APK 内的 `assets/arm64-v8a/libarvr_slam.so`。**离线回放头显 SLAM** 读取从 `locator.zip` 解出的 `slam-params.bin`，向原厂库送入合成 IMU 和空白图像。**实时采样头显 SLAM** 从定位器重新读取校准，同时采样头部 IMU 和外接 Y8 双目，并显示实际送入的记录数及位姿。
6. 双手定位另外需要 **导入原厂 6DoF 手柄模块**，选择原厂 `com.huawei.hvrsdkserverapp.apk`，并用 **导入双手回放配置** 选择下文生成的 `hand-config.bin`。两个应用各有私有目录，在哪个应用运行，就在哪个应用导入。**离线回放左右 6DoF 手柄** 可检查手柄库、HiAI 模型和调用接口，空白双目帧预期无有效位姿。
7. 在 Monado CV10 的套件页面按需选择 **启用 OpenXR 头显定位** 或 **启用 OpenXR 双手与头显定位**，授予相机和定位器 USB 权限。使用双手时先唤醒两只手柄，服务会读取两侧逐机校准。看到正在接收 HID 和 Y8 或已有头显位姿后，再启动 OpenXR 客户端。Monado 在运行时系统创建时公布设备，已运行的客户端和系统须退出并重新创建。可从同一页面或服务通知停止跟踪。
8. 双手模式提供左右两个 `khr/simple_controller`，各自映射选择、菜单、握持和瞄准位姿。该模式的右手位置由套件占用。CF20 配置在退出套件并新建运行时系统后继续使用。

## Windows 位姿接口离线验证

用 64 位 Windows Python 运行 [离线探针](probe-slam-head.py)，参数为解包后的原厂 PC 助手 `steamVRDriver/huaweiVR/bin/win64` 目录。脚本校验使用的 DLL SHA-256，并在当前进程内指定临时 XML 路径。默认回放头部 IMU 和空白双目帧。`--parameters` 用于回放诊断 APK 导出的头显校准。`--controllers` 先送入左右手 IMU，再送入带合成头显位姿的空白双目帧。`--config-xml` 可指定原厂 Android `assets/vrglass.xml`。两种回放都预期返回无有效视觉位姿。厂商文件由本机准备。

```powershell
python .\controller\probe-slam-head.py <原厂_PC_助手_win64_目录>
python .\controller\probe-slam-head.py <原厂_PC_助手_win64_目录> --parameters <slam-params.bin>
python .\controller\probe-slam-head.py <原厂_PC_助手_win64_目录> --controllers
python .\controller\probe-slam-head.py <原厂_PC_助手_win64_目录> --controllers --config-xml <原厂_Android_vrglass.xml> --export-config .\controller\build\hand-config.bin
```

`--export-config` 接受新文件路径。导入 Android 应用用的 7224 字节模板必须来自原厂 Android APK 的 `assets/vrglass.xml`，生成文件的 SHA-256 为 `75de7b935b0ac46b9cd32542aaaf62df806ef129b3146356cce11617ae8bdec3`。以上命令沿用 Windows 原厂配置解析器。实时双手跟踪以模板提供 LED 法线、包围盒和算法默认项，再写入本机定位器以及左右手柄的标定值。

要核验 Android 头显适配层和双手 C++ 数据接口，可在 x64 Native Tools Command Prompt 中运行下列命令。原厂 Windows `arvr_slam.dll` 和 `HandlerDLL.dll` 的 SHA-256 分别为 `6d89d332acfe86f9a9a3309a913de6d6cb8f0da2f49b46f60b96a07599283a7d` 和 `0269d56389e7c107cb46f668ca48e789befc07fc236c04ed00867eab0ef98451`。

```powershell
New-Item -ItemType Directory -Force .\controller\build | Out-Null
cl /nologo /EHsc /std:c++17 .\controller\probe\HeadSlamAbi.cpp /Fo:controller\build\HeadSlamAbi.obj /Fe:controller\build\HeadSlamAbi.exe
.\controller\build\HeadSlamAbi.exe <原厂_arvr_slam.dll> <slam-params.bin>
.\controller\build\HeadSlamAbi.exe <原厂_HandlerDLL.dll> <hand-config.bin> --controllers
```

## 从源码重建

Monado 源码位于 `ports/Monado_CV10` 子模块。可在其干净的 `9314beab63dea36cfec984d59f4b351dfab26ef3` 基线上应用 [Monado 补丁](monado-cv10-controller.patch)。当前交付工作树已包含改动。

```powershell
git -C ports/Monado_CV10 apply --check ../../controller/monado-cv10-controller.patch
git -C ports/Monado_CV10 apply ../../controller/monado-cv10-controller.patch
```

诊断 APK 使用 JDK 17、Android Platform 35、Build Tools 36.0.0 和 NDK 26.3.11579264。从仓库根目录运行下列命令。脚本先执行两组协议测试向量，再编译、签名和校验 ARM64 APK。可用 `-Ndk` 指定独立安装路径。

```powershell
.\controller\build-probe.ps1 -Sdk $env:ANDROID_HOME -Jdk $env:JAVA_HOME
```

运行时依赖和 SDK 配置见 [Monado CV10 构建说明](../ports/Monado_CV10/README.md#从完整源码构建)。从仓库根目录运行下列命令。Gradle 在子模块的 `src/xrt/targets/openxr_android/build/outputs/apk/outOfProcess/debug/` 下生成 APK。

```powershell
Push-Location .\ports\Monado_CV10
.\gradlew.bat '-Pcv10Abi=arm64-v8a' :src:xrt:targets:openxr_android:assembleOutOfProcessDebug
Pop-Location
```
