# Moonlight XR CV10

在 Galaxy Z Fold7 上使用 Moonlight XR 接收 Sunshine 串流。Monado CV10 提供 Android OpenXR 运行时，并负责 CV10 的双眼合成及 USB IMU。手机打开 **Moonlight XR CV10** 后，在主机列表选择 Sunshine，完成 PIN 配对，再选择 **Desktop** 或游戏。测试时保持三星 DeX 外接显示为「已镜像」，在 Khronos Broker 中选择 Monado CV10。手机设置里的 VR Mode 控制 OpenXR，实时 3D 控制单目画面的深度估计和逐眼合成。

正常退出和重进已在包含 Monado 卸载修复的预览运行时通过。稳定包 v0.1.2 能显示串流，退出时会崩溃。测试用运行时摘要及实机证据见 [Fold7 与 CV10 测试记录](evidence/fold7-cv10.md)。

## 源码与构建

补丁基于 Gilleece Moonlight XR v0.4.3 的 [源码提交 `75d92f2`](https://github.com/Gilleece/moonlight-android-xr/tree/75d92f2559a91c92a68f05f14fc472b7284cc034)。`nonRoot` 构建限 `arm64-v8a`，包名为 `org.cv10.moonlightxr`，可和上游 APK 同时安装。上游对照发行包 SHA-256 为 `acb2221aff323b4da23e5acb04667797dc2043bd1e6895e1a2eb44119c4a1f99`。[上游发行页](https://github.com/Gilleece/moonlight-android-xr/releases/tag/v0.4)

从本仓库根目录执行下列 PowerShell 命令。用 JDK 17 或兼容的新版 JDK，安装 Android Platform 37、Build Tools 36.0.0、Platform Tools 和 NDK `29.0.14206865`。项目自带 Gradle 9.7.1 Wrapper。

```powershell
$source = '.research/moonlight-xr-build'
$patch = (Resolve-Path 'ports/moonlight-xr/cv10.patch').Path
git clone https://github.com/Gilleece/moonlight-android-xr.git $source
git -C $source checkout --detach 75d92f2559a91c92a68f05f14fc472b7284cc034
git -C $source submodule update --init --recursive
git -C $source apply --check $patch
git -C $source apply $patch
$sdk = ($env:LOCALAPPDATA + '/Android/Sdk').Replace('\', '/')
Set-Content -Encoding ascii "$source/local.properties" "sdk.dir=$sdk"
& "$source/gradlew.bat" -p $source :app:assembleNonRootRelease
```

未配置 `keystore.properties` 时，输出为 `app/build/outputs/apk/nonRoot/release/app-nonRoot-release-unsigned.apk`。用 `zipalign -P 16 -f 4` 对齐，再用 `apksigner sign` 签名。覆盖安装时保留自己的签名证书。APK 中的 Moonlight 和第三方组件许可证沿用上游源码。

本轮在 Windows 上用 JBR 25.0.3 完成 release 构建及 Lint。`testNonRootDebugUnitTest` 的 48 个测试套件共通过 335 项。开发签名 APK 版本为 `12.1-xr0.4.3`（31407），SHA-256 为 `581e973086ef5a2a378a542c2d87d32a8d768dc078e9723868f1131948fbaf39`。签名、16 KiB 原生库对齐、包名及仅含 `arm64-v8a` 已核对。DEX 检查确认上游对照 APK 缺少该方法，CV10 APK 包含该方法。

## 兼容性修复

原版 APK 能完成 PC 配对和串流协商。启动 XR 时，loader 枚举了 Monado CV10 的扩展，运行时随即在加载 Android 生命周期回调时抛出 `NoSuchMethodError`，缺少 `kotlin.jvm.internal.Intrinsics.checkNotNullParameter(Object, String)`。`xrCreateInstance` 返回 `XR_ERROR_RUNTIME_UNAVAILABLE`，该线程退出时进程收到 `SIGSEGV`。补丁保留 APK 中 `Intrinsics` 的方法，供 Monado 在客户端进程加载的 Kotlin 回调使用。

在此修复后，稳定运行时仍在应用退出时复现另一个问题。`xrDestroyInstance` 成功后，OpenXR loader 关闭 Monado 库，而退出的渲染线程仍有线程局部析构函数要执行。Monado 提交 `4fe230f72c04906a4f28c857788d3c07a48423e0` 为 Android 运行时设置 `-z nodelete`。Fold7 上使用同一个 Moonlight APK 对照验证了该修复。
