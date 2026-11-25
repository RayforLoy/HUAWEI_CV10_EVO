# Fold7 通过 Shizuku 管理 CV10 会话刷新率

适用于三星 Galaxy Z Fold7 SM-F9660 主用户。Monado 检查内屏在当前分辨率支持 120 Hz，并要求已经连接名为 HUAWEIAV03 的外屏。该功能在运行 OpenXR 应用时提高手机最低刷新率，使外屏合成有机会达到 90 Hz。用户可以在 Monado 内开启或关闭此功能。

1. 在手机安装 Shizuku 13 或更高版本，并通过其“无线调试”功能启动。手机重启后需要重新启动 Shizuku。Android 11 及以上的配对与启动可以在手机上完成。[官方使用指南](https://shizuku.rikka.app/guide/setup/)
2. 安装 **Monado-CV10-Shizuku120-arm64.apk**。打开 **Monado CV10**，选择 **开启独立 120 Hz**，在说明弹窗确认后，在 Shizuku 的授权弹窗选择允许。菜单显示 **关闭独立 120 Hz** 时表示已启用。若以前选择了拒绝，可在 Shizuku 的“已授权应用”中管理 Monado 的权限。
3. 连接 CV10，启动使用 Monado 的 OpenXR 应用。退出客户端、拔掉眼镜或通过菜单关闭功能都会触发恢复。为确保能恢复，先退出 XR 应用，再停止 Shizuku 或卸载 Monado。

运行时采用官方 Shizuku API/Provider 13.1.5。UserService 仅接受无线调试启动的 shell 服务，并限定于主用户的 `Settings.System.min_refresh_rate`。它在实际 OpenXR IPC 连接建立后校验原值并设为 `120.0`，收尾时复原原数值，原值缺失则删除该项。Binder 接口只提供本设置的会话操作。Monado 在私有存储中先记下原值；当其他程序或用户改为其他数值时会保留该值。相同值的重复写入在 Android 设置接口中不可区分。

UserService 使用 `daemon(false)`，在正常退出或接到运行时的 Binder 死亡通知时尝试恢复。若系统同时杀死服务，或 Shizuku 停止导致暂时无法收尾，重新启动并授权 Shizuku，然后打开 Monado 即可重新检查恢复记录。异常情况下可查看日志标签 `Cv10RefreshLease`。

## 重建

在上游 Monado `ce2b721eb4ffcbd726fb88357625f55871a8f262` 依次应用本目录的 `cv10.patch`、`framevote90.patch`、`primary-mailbox.patch`、`launcher-name.patch`、`shizuku-120.patch`。按主说明构建 outOfProcess arm64。原生库与 named primary-mailbox 版逐字节一致。[Shizuku API 开发文档](https://github.com/RikkaApps/Shizuku-API)

APK SHA-256 为 `0b40daccb53d0155e419169244a820523c089bd4e2dff7c1bc37707c2d033403`。签名证书 SHA-256 为 `3f110dfc8ba9bbe99f454e60679216cf12f66388b27c08cbc5d7cf51d542e684`。

## Fold7 实测

同一 Fold7、普通 C-C 线、CV10 和官方 hello_xr。手机管理器通过无线调试启动 Shizuku，测试期间没有运行电脑会话提频脚本。

| 测试 | 手机主屏与外屏结果 |
| --- | --- |
| 游戏公开帧率 API | 手机窗口清除 preferredDisplayModeId，单独请求 120 Hz；在主屏 32 dp 可见 SurfaceView 持续提交缓冲并调用 Surface.setFrameRate(120, DEFAULT, CHANGE_FRAME_RATE_ALWAYS)，眼镜请求 90 Hz。日志确认实际调用。手机主屏仍选 60 Hz，主屏小窗口实测每秒提交约 60.3 个缓冲。 |
| 普通系统写设置权限 | 设置页允许 WRITE_SETTINGS 后，系统提供程序仍拒绝写最低刷新率，手机选 60 Hz。 |
| Shizuku 授权 | 手机主屏切到 120 Hz，眼镜模式 3200×1600 @ 90 Hz。一次稳态采样记录眼镜图层每秒 89.96 次不同呈现时间戳。通过启动器入口再次启动也触发提频。 |
| 退出 | 按 Android 返回键退出样例后最低刷新率恢复为未设置，手机主屏回到 60 Hz。 |

[初次及重复启动数据](../../research/evidence/fold7-cv10-standalone-refresh.json) · [Android 游戏刷新率说明](https://developer.android.com/games/optimize/display-refresh-rate-change)
