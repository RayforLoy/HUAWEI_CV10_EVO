# Huawei VR Glass 原厂手柄与 6DoF 套件

| 硬件 | Monado CV10 | 独立诊断 APK | 验证 |
| --- | --- | --- | --- |
| CF20 蓝牙 3DoF 手柄 | 应用内搜索、选用、Android 系统配对、会话自动连接和右手 OpenXR 输入 | GATT 状态、报告频率、原始包、四元数、按键、触控、惯性和电量 | 通过构建和协议测试向量。Fold7 待验收 |
| 原厂 6DoF 套件 | 可从手柄菜单进入诊断 | USB 枚举、头显及左右手原始记录、双目和三路 IMU 校准、头显 SLAM 参数导出、每只手柄的 LED 模型和外参、外接 Y8 双目图像导出 | 通过构建、协议测试向量和 Windows 头显 SLAM 配置验收。Fold7 USB／相机可用性及位姿接入待完成 |

两条协议独立记录在 [CF20 蓝牙协议](cf20-protocol.md) 和 [6DoF 套件协议](kit-6dof-protocol.md)。诊断 APK 与运行时共用发现、配对及报告解码源码。

## 本机产物

| APK | 包名 | SHA-256 |
| --- | --- | --- |
| [Cv10ControllerProbe.apk](dist/Cv10ControllerProbe.apk) | `org.cv10.controllerprobe` | `9c386191ef786f4470d4f6f48c1f3a918b84cf6e10d1f33d591f6213bae02aa2` |
| [Monado-CV10-Controller-arm64-v8a.apk](dist/Monado-CV10-Controller-arm64-v8a.apk) | `org.cv10.monado.out_of_process` | `f34acf03038d5cf54c89d9081e8ab06a64ec4f36050c4375ba623d9fc1ed917a` |

两个 APK 均为本地调试构建，最低 Android API 26。本机校验证书 SHA-256 为 `68365fa0904432aaa86a8904c691f9e6487414dc959786d72831a083b9f23fca`。运行时覆盖安装需要与已安装的 APK 签名一致。独立诊断 APK 可与运行时并存。两包已通过 `apksigner verify` 和 `zipalign -c -P 16 4`，运行时包含 `arm64-v8a`。当前工作树未进行真机安装、配对、USB／相机采样或 OpenXR 验收。

## 使用入口

1. 在 Monado CV10 菜单选择 **CV10 蓝牙手柄**，唤醒 CF20，点击 **Scan for CF20**，允许 Android 所需权限并点选结果。也可填写蓝牙地址。
2. 点 **配对并选用**。Monado 收到报告后保存地址，新建 OpenXR 会话时自动连接。**Android 系统配对**可另外尝试建立系统蓝牙绑定。独立诊断 APK 用 **配对并连接** 保持连接并实时显示输入。
3. 套件在同页的 **定位交互套件** 中。**采样定位器 HID** 显示头部、左手、右手原始记录。**采样 OV580 相机** 显示帧计数，并将首个带有效元数据的双目帧保存为 ZIP。
4. 点击 **读取套件校准**，查看双目、各组件 IMU 采样率及手柄 LED 模型的摘要。定位器、左手、右手的完整回复各保存为独立 ZIP（`locator.zip`、`left.zip`、`right.zip`），每包包含 `calibration.bin` 和 `device.hash`。定位器校准可解码时，额外保存 2112 字节的 `slam-params.bin`。保存路径显示在诊断页中。套件的 6DoF 位姿尚未提供给 OpenXR。

## Windows 头显 SLAM 离线验证

用 64 位 Windows Python 运行 [离线探针](probe-slam-head.py)，参数为解包后的原厂 PC 助手 `steamVRDriver/huaweiVR/bin/win64` 目录。脚本校验两个 DLL 的 SHA-256，在当前进程内指定临时 XML 路径，并验证启动、停止、IMU 和空白双目帧送入。可用 `--parameters` 回放诊断 APK 导出的参数。空白帧的预期结果是无位姿。厂商文件由本机准备。

```powershell
python .\controller\probe-slam-head.py <原厂_PC_助手_win64_目录>
python .\controller\probe-slam-head.py <原厂_PC_助手_win64_目录> --parameters <slam-params.bin>
```

## 从源码重建

Monado 源码位于 `ports/Monado_CV10` 子模块。可在其干净的 `9314beab63dea36cfec984d59f4b351dfab26ef3` 基线上应用 [Monado 补丁](monado-cv10-controller.patch)。当前交付工作树已包含改动。

```powershell
git -C ports/Monado_CV10 apply --check ../../controller/monado-cv10-controller.patch
git -C ports/Monado_CV10 apply ../../controller/monado-cv10-controller.patch
```

诊断 APK 使用 JDK 17、Android Platform 35 和 Build Tools 36.0.0。从仓库根目录运行下列命令。脚本先执行两组协议测试向量，再编译、签名和校验 APK。

```powershell
.\controller\build-probe.ps1 -Sdk $env:ANDROID_HOME -Jdk $env:JAVA_HOME
```

运行时依赖和 SDK 配置见 [Monado CV10 构建说明](../ports/Monado_CV10/README.md#从完整源码构建)。从仓库根目录运行下列命令。Gradle 在子模块的 `src/xrt/targets/openxr_android/build/outputs/apk/outOfProcess/debug/` 下生成 APK。

```powershell
Push-Location .\ports\Monado_CV10
.\gradlew.bat '-Pcv10Abi=arm64-v8a' :src:xrt:targets:openxr_android:assembleOutOfProcessDebug
Pop-Location
```
