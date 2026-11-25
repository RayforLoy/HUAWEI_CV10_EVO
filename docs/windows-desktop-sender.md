# 将 Windows 桌面投到 CV10

本机可双击 `resources\VRGlassPC.exe`。Windows 负责抓取一个显示器，手机接收 JPEG 帧并通过外屏向眼镜绘制。声音、返向输入与头部姿态不包含在这条桌面视频通道内。[上游协议](https://github.com/samrat1games/huawei-vr-glass-globalka/blob/266dbe02e115c7aeed936dedc2d1924ae375bc8c/docs/desktop-protocol.md)

1. Fold7 通过普通 C-C 线接 CV10，将三星 DeX 的“连接的显示设备”设为“已镜像”。在接收应用打开“接收电脑屏幕”，记下手机显示的局域网 IP 和本次六位配对码。
2. 在同一可信局域网上打开 Windows 发送端。第一项填手机 IP，第二项填六位码，第三项选择要发送的显示器。端口固定为 TCP 7788，默认 JPEG 质量为 60。应用协议通过局域网明文传输。
3. 点击 **Отправлять на телефон**（开始发送）。状态区显示实际编码尺寸、平均帧率与累计帧数。点击 **Прекратить**（停止）可立即结束抓屏。

**2026-11-25 实测**使用固定版 Globalka 的 Windows 桌面发送端连接原版 Android 接收端。副显示器放置黄底黑圆、蓝底白三角与递增秒数。发送端报告 `DISPLAY2`、源区域 1707×1067，实际帧为 1599×1000；累计 510 帧时平均 16.2 fps。眼镜摄像头拍到同一桌面标记。

随后使用同一 Windows 发送端复测启用 CV10 IMU 的适配版 Android 接收端。14:07 把桌面测试图切换成每隔约 130 像素重复显示的 **PC** 和递增秒数。镜片实拍可辨认 **PC** 与 **0019**。最终一轮停止前发送了 1350 帧，实际 1599×1000，发送端报告平均 12.0 fps。该帧率统计的是 Windows 端发送速度。测试已停止，副屏桌面已恢复。

## 本地构建

上游固定提交为 `266dbe02e115c7aeed936dedc2d1924ae375bc8c`。原始 `VRGlassPC.cs` SHA-256 为 `85395fffc0f20e7c8124f02c7bc891e9c9e84f50c6d048e6db1401e50e9d177b`。原样使用 .NET Framework 4 C# 编译器时报 CS0104，`Encoder` 同时匹配 `System.Text.Encoder` 和 `System.Drawing.Imaging.Encoder`。构建脚本在临时副本中仅将 JPEG 参数限定为 `System.Drawing.Imaging.Encoder.Quality`，再使用上游编译选项生成 WinForms EXE。[固定版本发送端源码](https://github.com/samrat1games/huawei-vr-glass-globalka/blob/266dbe02e115c7aeed936dedc2d1924ae375bc8c/windows/VRGlassPC.cs)

```powershell
.\tools\build-globalka-sender.ps1
```

脚本默认写入 `resources\VRGlassPC.exe`，支持 `-OutputDirectory` 指定其他目录。本机实测二进制的 SHA-256 为 `7f7ad9d8e3934873b4141bcae10cee8fe032457ed305e3916b26718139108c11`。上游 README 的 Licence 段仅说明代码按现状发布，另列全景素材为 CC0。仓库跟踪本项目的构建脚本，第三方 EXE 保存在本机资源目录。[上游 Licence](https://github.com/samrat1games/huawei-vr-glass-globalka/blob/266dbe02e115c7aeed936dedc2d1924ae375bc8c/README.md#licence)
