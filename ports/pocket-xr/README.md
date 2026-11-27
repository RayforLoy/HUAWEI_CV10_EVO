# Pocket XR CV10 光学适配

这两份项目补丁基于 Pocket XR `v1.6.28`（`af04bc4`）。它们添加独立的 `org.cv10.pocketxr` 构建，并让该构建在 Monado 的 `Monado CV10 Pocket XR Optics` 虚拟显示屏上绘制与 CV10 匹配的每眼 95° × 95° 双目场景。其他显示屏继续使用 Pocket XR 自己的显示判断。补丁沿用上游 GPLv3 许可。[Pocket XR v1.6.28](https://github.com/pocket-xr/pocket-xr/tree/v1.6.28)

在 Pocket XR 源码目录中依次应用 `patches` 中的两份补丁，再构建 ARM64 安装包。`<CV10 repo>` 替换为 HUAWEI CV10 EVO 的本机路径。Android SDK、Gradle 和签名要求沿用上游。

```powershell
git switch -c cv10-optics v1.6.28
git am '<CV10 repo>/ports/pocket-xr/patches/0001-Render-a-native-95-degree-stereo-frustum-on-the-CV10.patch' '<CV10 repo>/ports/pocket-xr/patches/0002-Keep-CV10-virtual-display-timing-and-diagnostics-in-.patch'
.\gradlew.bat '-Ppocketxr.cv10=true' :app:assembleRelease
```

为 Pocket XR CV10 单独授权 Shizuku，再从 Monado 的 **Pocket XR 外显预览 → 打开 Pocket XR（CV10 光学视场）** 启动。该构建从虚拟显示屏实际获得的绘制尺寸划分左右眼，方形每眼视场保持 95° × 95°。打开 Monado 的超分辨率后，光学视场入口会请求更大的虚拟显示屏，由 Pocket XR 以该尺寸重新绘制双目空间。Android 应用窗口与 PC 视频的源细节仍取决于应用和视频自身的分辨率。旧版 1600×1600 每眼光学模式已有实机记录，新档位待验证。[渲染原理与档位](../../docs/cv10-oem-rendering.md)
