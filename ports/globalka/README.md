# Globalka 的 CV10 头部追踪测试版

本补丁基于 Globalka 提交 `266dbe02e115c7aeed936dedc2d1924ae375bc8c`。定制包名为 `com.samrat.vrglassbridge.cv10`，可与原版共存。选「投手机桌面 / Mirror phone」直接开启手机画面投屏，选「PC / Mac screen in VR」使用上游电脑发送端。两者以及全景场景的双眼渲染都接入同一个眼镜姿态源。手机首次使用时，Android 会询问是否允许应用访问 USB 设备。手机桌面模式还需要上游原有的悬浮窗和屏幕捕获授权。[固定上游源码](https://github.com/samrat1games/huawei-vr-glass-globalka/tree/266dbe02e115c7aeed936dedc2d1924ae375bc8c)

## 构建

从本项目根目录在 PowerShell 中运行。示例使用一个新目录，Android SDK 需要 Platform 36 和 Build-Tools 36.0.0，可用 Android Studio 的 JBR。

```powershell
$src = '.research/globalka-build'
git clone https://github.com/samrat1games/huawei-vr-glass-globalka.git $src
git -C $src checkout --detach 266dbe02e115c7aeed936dedc2d1924ae375bc8c
$patch = (Resolve-Path 'ports/globalka/cv10-imu.patch').Path
git -C $src apply --check $patch
git -C $src apply $patch
$env:ANDROID_HOME = "$env:LOCALAPPDATA/Android/Sdk"
$env:JAVA_HOME = 'C:/Program Files/Android/Android Studio/jbr'
python "$src/tools/build.py"
```

结果写入源码目录的 `dist/Globalka-CV10-IMU.apk`。构建工具在源码目录的 `build/` 生成本地开发签名；保留该目录可使用同一证书更新。不同签名密钥会改变文件哈希。本次设备测试包在 `.research/globalka-imu/dist/`，APK SHA-256 为 `de3dfa2587c2c8a1e3058863ff87612a20e1ed8ed6e79b9df9fbbce936ebafe3`，已通过 v2/v3 签名校验。固定上游树的根目录没有 LICENSE 文件，本仓库以补丁记录变更，构建产物保存在本地研究目录。

## 采集与渲染

应用匹配 Fold7 上已实测的 CV10 USB `12d1:107e`，读取接口 3 的中断 IN 端点 `0x84`。第一个渲染表面附着后尝试取得 USB 权限并启用 IMU（`05 02 00 00 00`），最后一个表面释放后发送对应停用报文（`06 02 00 00 00`）。采集线程按实测 60 字节格式验证报告，使用设备时钟和陀螺角速度进行四元数积分，并用加速度方向修正相对倾斜。所有外屏渲染表面共享一个 USB 连接。渲染器在绘制左右眼之前读取同一份最新矩阵；超过半秒无新姿态时恢复使用已有手柄视角控制。[协议与字段](../../docs/firmware-resource-analysis.md)

首个近似静止的重力样本定义初始参考方向。该版本按原厂 Wallex 报告的 X/Y/Z 顺序输入 OpenGL 旋转，需通过单轴佩戴运动验证物理朝向和符号。系统没有外部航向参考，长时间使用会有航向漂移。退出所有场景并重新进入可重新建立初始参考。手机姿态和手柄指针不参与眼镜 IMU 积分。

日志标签为 `GlobalkaCV10`。采集线程在启用后最多等候五秒首包，运行中的短暂空窗保留同一份 USB 请求。首次有效报告会触发 `CV10 head tracking active`，此后日志每约三秒给出累计有效报告数、耗时及前向量。每个渲染实例首次实际采用姿态时会输出 `Renderer using CV10 pose scene=mirror|remote|environment` 对应场景。测试时将手机放稳，分别转动眼镜、再固定眼镜仅转动手机，可区分眼镜姿态与手机运动。受控回放测试验证了低 32 位时间戳进位、1 kHz 连续积分 90°、列主序矩阵和异常帧过滤。

```powershell
$pkg = "$src/app/src/main/java/org/vrglass/bridge"
$classes = New-Item -Force -ItemType Directory "$src/build/pose-test"
& "$env:JAVA_HOME/bin/javac.exe" -d $classes.FullName "$pkg/Cv10Pose.java" "$src/tools/tests/Cv10PoseCheck.java"
& "$env:JAVA_HOME/bin/java.exe" -cp $classes.FullName org.vrglass.bridge.Cv10PoseCheck
```

## Fold7 真机验收 · 2026-11-25

Fold7 用普通 C-C 线直连 CV10，三星外接显示器保持「已镜像」。两项测试均使用手机上的 `Globalka CV10 IMU`。从手机回读已安装 APK 并计算 SHA-256，与 [本机安装包](../../resources/Globalka-CV10-IMU.apk) 一致。QQ 原版也已安装，可作为对照。

| 场景 | 摄像头观察 | 渲染与传输证据 |
| --- | --- | --- |
| 投手机桌面 / Mirror phone | 左镜片可辨认三星桌面的 Gmail、QQ、淘宝图标及文字。[左镜片实拍](../../.research/globalka-test/verified-home2-lens.jpg) | Android MediaProjection 持有者为本包，14:05:02 渲染器首次记录 `scene=mirror` 使用 CV10 姿态，66 秒累计 65,954 个有效报告。 |
| PC / Mac screen in VR | 左镜片可读 Windows 副屏交替色块上的 `PC` 和计时 `0019`。[左镜片实拍](../../.research/globalka-test/verified-pc-tiles-lens.jpg) | Windows 桌面实际捕获，Fold7 接收 1599×1000 JPEG。数次测试手机端约 10–16 fps。14:06:15 渲染器首次记录 `scene=remote` 使用 CV10 姿态，147 秒累计 146,933 个有效报告。 |

在同签名的前一轮适配版上，操作者保持手机静止、转动眼镜并放回，朝向向量由 `(-0.001,0.001,-1.000)` 变为 `(0.028,0.063,-0.998)`，随后回到接近初始方向。日志每三秒记录一次，不能用该差值推算实际转动峰值。验证了眼镜输入引起的姿态变化；尚未逐轴标定方向、增益，光学照片只覆盖左眼。

复用时点首页的「投手机桌面 / Mirror phone」，选择共享整个手机屏幕；投电脑时选「PC / Mac screen in VR」，在 [Windows 发送端](../../resources/VRGlassPC.exe) 填写手机此轮显示的地址和六位码，再选择目标显示器。[发送端配置](../../docs/windows-desktop-sender.md) 测试结束后已退出接收页，确认 USB 停用请求返回 5 字节，手机媒体投影为空。实拍保存在本地忽略目录。
