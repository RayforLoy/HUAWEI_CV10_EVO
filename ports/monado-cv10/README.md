# Monado CV10 Android 运行时

本目录的 `cv10.patch` 适用于 Monado 提交 `ce2b721eb4ffcbd726fb88357625f55871a8f262`。定制运行时包名为 `org.cv10.monado.out_of_process`，可与官方 `org.freedesktop.monado.openxr_runtime.out_of_process` 共存。在 Khronos OpenXR Runtime Broker 中选择 **Monado CV10** 使用定制版，选择 **Monado XR** 恢复官方版。[Monado 固定源码](https://gitlab.freedesktop.org/monado/monado/-/tree/ce2b721eb4ffcbd726fb88357625f55871a8f262)

定制 HMD 驱动读取 `12d1:107e` 的头显 IMU，向 OpenXR 提供旋转姿态。头显未连接、USB 授权缺失或报告中断时，应用应检查返回的姿态有效标志。外屏路径按名称识别 `HUAWEIAV03`，使用 3200×1600 左右两个视区及相反的逐眼旋转。当前对称视场和镜间距为开发用参数，光学畸变与个体标定仍待测量。

## 从固定源码构建

在 Windows 工作站上准备 Git、JDK 17、Python 3.10 或更新版本、可在 PATH 中调用的 `glslangValidator`，以及 Android SDK Platform 35、Build Tools 34.0.0、NDK 26.3.11579264 和 CMake 3.22.1。本次使用 Eigen 5.0.0 的 CMake 安装目录及 glslang 16.6.0。设置 `JAVA_HOME` 指向 JDK，`ANDROID_HOME` 指向 SDK，`CV10_EIGEN_CMAKE_DIR` 指向包含 `Eigen3Config.cmake` 的目录。[Eigen](https://gitlab.com/libeigen/eigen/-/tree/5.0.0) · [glslang](https://github.com/KhronosGroup/glslang)

从本项目根目录的 PowerShell 执行：

```powershell
$patch = (Resolve-Path ports/monado-cv10/cv10.patch).Path
$checkout = '.research/monado-cv10-rebuild'
$revision = 'ce2b721eb4ffcbd726fb88357625f55871a8f262'
git init $checkout
git -C $checkout fetch --depth 1 https://gitlab.freedesktop.org/monado/monado.git $revision
git -C $checkout checkout --detach FETCH_HEAD
git -C $checkout apply --check $patch
if ($LASTEXITCODE) { throw 'Patch does not match the checkout' }
git -C $checkout apply $patch
$sdk = $env:ANDROID_HOME.Replace('\','/')
$eigen = $env:CV10_EIGEN_CMAKE_DIR.Replace('\','/')
$python = (Get-Command python).Source.Replace('\','/')
@("sdk.dir=$sdk", "eigenCMakeDir=$eigen", "pythonBinary=$python") |
    Set-Content -Encoding ascii "$checkout/local.properties"
Push-Location $checkout
try {
    .\gradlew.bat --max-workers=6 -Pandroid.injected.build.abi=arm64-v8a :src:xrt:targets:openxr_android:assembleOutOfProcessDebug
    if ($LASTEXITCODE) { throw 'Gradle build failed' }
    Get-ChildItem src/xrt/targets/openxr_android/build/intermediates/apk/outOfProcess/debug/*.apk
} finally {
    Pop-Location
}
```

Gradle 使用本机 Android 调试签名。检查产物时，使用 SDK Build Tools 的 `apksigner.bat verify --verbose --print-certs` 和 `aapt.exe dump badging`，并确认 APK 内有 `lib/arm64-v8a/libopenxr_monado.so` 与 `lib/arm64-v8a/libmonado-service.so`。首次安装选择新的 Broker 条目；后续更新同一包名时应使用同一签名。

2026-11-25 构建通过 Gradle 组合任务及 APK v2 签名验证，独立文件保存在本机 `resources/Monado-CV10-arm64.apk`。逐眼旋转对照版为 34,760,200 字节，SHA-256 为 `b697c76fc273e9716269918a0680ed4e68a6da28fbadcff30e72ff8742d7fc6b`。测试签名证书 SHA-256 为 `3f110dfc8ba9bbe99f454e60679216cf12f66388b27c08cbc5d7cf51d542e684`。

Java IPC 的 CONNECT action 与合并后的 Manifest 一致。原生客户端通过 CMake 生成的 XRT_ANDROID_PACKAGE 定位服务和加载运行时类。首轮 APK 的这个值仍指向官方包，实机在绑定服务时失败。修复版已从打包的两份原生库的 .rodata 区逐一核实定制包名，并核实不含旧包名。

逐眼旋转对照版使用 `u_device_rotation_left` 处理视图 0，使用 `u_device_rotation_right` 处理视图 1。上一版的两项设置相反，SHA-256 为 `4faa15e81c7585158deb8adf4928050be4404c9eacff6a785cdc26c87bec029c`。两个 APK 的 ZIP 条目经逐一比较，变化限于 `libmonado-service.so`。视差方向及佩戴效果以同一标记的新旧实机对照为准。

## Fold7 与 CV10 双眼实机验收（2026-11-25）

使用普通 C-C 线、Fold7 的三星「已镜像」显示模式及两台固定摄像头。Khronos Broker 选中 Monado CV10。样例为 Khronos OpenGLES `hello_xr` 1.1.65。开始和结束时分别从手机拉取已安装的 base.apk，SHA-256 均为 `29ae01ef6a4fea41d67816f7051698f2694ab08ced4c16c02bdd978e62975962`。最终测试的运行时 APK SHA-256 为 `b697c76fc273e9716269918a0680ed4e68a6da28fbadcff30e72ff8742d7fc6b`。此调试 APK 在 Fold7 上使用 `adb install -t -r` 安装。

| 项目 | 实测结果 |
| --- | --- |
| 开屏和输出 | 定制运行时获得 USB 访问许可，PCUI 返回开屏 OK。外屏 Presentation 选中 HUAWEIAV03，活动模式 3200×1600 @ 90 Hz。该值是面板模式，未测量应用持续帧率。 |
| OpenXR 会话 | 原版样例枚举到 Huawei VR Glass CV10 (USB IMU)，旋转跟踪为真，位置跟踪为假，双眼交换链创建成功，会话进入 FOCUSED。[日志](../../research/evidence/fold7-monado-cv10-session.log.txt) |
| 镜片眼别和方向 | 探针 Canvas 左 270°、右 90°。两台摄像头分别拍到蓝色 L↑ 和橙色 R↑，字母正读。[左镜片](../../research/evidence/fold7-cv10-upright-left.jpg) · [右镜片](../../research/evidence/fold7-cv10-upright-right.jpg) |
| 样例实际出图 | 在同一摄像头位置换为官方样例，两个镜片均拍到中央蓝色方块。左摄像头广角镜头的背景反光较强。[左眼实拍](../../research/evidence/fold7-monado-cv10-left.jpg) · [右眼实拍](../../research/evidence/fold7-monado-cv10-right.jpg) |
| 立体视差 | 将外屏截图按中央分为两个 1600×1600 视图，左图顺时针 90°、右图逆时针 90°还原佩戴方向。用 B>220、G<30、R<30 求中央方块像素重心。旧版左 x=784、右 x=815。最终版左 x=815、右 x=784，两者 y=799.5，视区中心为 (799.5,799.5)。前方居中物体呈正确的水平视差。[最终外屏原图](../../research/evidence/fold7-monado-cv10-surface.png) |
| 眼镜姿态 | USB 端点 0x84 连续送入眼镜设备时钟与 IMU 样本，最终版本日志包含采集与融合四元数。转动对照使用上一个仅视图旋转不同的运行时，约 15:13:11 至 15:13:21，四元数夹角约 21.5°，角速度峰值 0.60 rad/s，外屏边缘场景随之改变。中央方块在样例中锁定于头部前方 2 米，不能用它判断是否发生头动。实验没有独立记录手机转动时间或手机陀螺仪。[姿态日志](../../research/evidence/fold7-monado-cv10-motion.log.txt) · [Khronos 样例源码](https://github.com/KhronosGroup/OpenXR-SDK-Source/blob/release-1.1.65/src/tests/hello_xr/openxr_program.cpp) |

此验收覆盖该样例的 3DoF 头显链路。镜片畸变、个体瞳距和三轴角度精度仍待光学校准。
