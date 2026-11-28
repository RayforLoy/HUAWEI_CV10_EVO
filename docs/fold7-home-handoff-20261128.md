# 家中电脑交接 · Fold7 手机触摸板

从主项目的 `cv10-fold7-20261128.1` 标签继续。这个标签固定三份子模块的提交。它也标记了本轮并入 `main` 的主项目版本。[整套发布及校验清单](https://github.com/RayforLoy/HUAWEI_CV10_EVO/releases/tag/cv10-fold7-20261128.1)

## 源码与安装包

| 仓库 | 本轮版本 | 在 Fold7 上的用途 |
| --- | --- | --- |
| Monado CV10 | `57501d66ca3d183421fabc9d1d34cc80f339cb9e` · [v0.1.4-rc.4](https://github.com/RayforLoy/Monado_CV10/releases/tag/v0.1.4-rc.4) | Broker 中选择 Monado CV10，预览包名为 `org.cv10.monado.out_of_process.launcher_preview`，版本代码 107 |
| PiliPlus | `f762b45d0e21ef009d56c594842f838a9397fd5e` · [双手柄影院版](https://github.com/RayforLoy/piliplus_monado/releases/tag/cv10-dual-controller-zoom-20261128) | 包名 `com.example.piliplus`。从桌面直接进入头显选片页。APK 对应 `87734cb` 的构建，标签提交只追加了使用说明 |
| Pocket XR CV10 | `c700944ec389d7e0421a24db47ac9686451d7710` · [CV10 Spatial Desk 1.6.33](https://github.com/RayforLoy/pocket-xr-cv10/releases/tag/cv10-v1.6.33-quad-ffr.1) | 独立外显应用。本轮测试 Monado 手机手柄时，在 Broker 保持选择 Monado CV10 |

Monado APK 的 SHA-256 为 `0e46b5dac9a23995b6a0408977f26e369d758f7bc99ee6f8581789acb2ef1278`。PiliPlus APK 为 `261c09080f5007203e8300c21fd0c154158ef2a29a8954bae26e32352114bac2`。两份安装文件已和 Fold7 上的 `base.apk` 逐字节摘要核对。签名证书的 SHA-256 为 `68365fa0904432aaa86a8904c691f9e6487414dc959786d72831a083b9f23fca`。家中电脑可直接使用发布包。CV10 Spatial Desk 的包名为 `org.cv10.pocketxr`，本次公开 APK 的 SHA-256 为 `3ace725f2b467e4b4a2065d4576ed75113b9e74a56c9a127b965ac2a35b25669`。本轮通过独立构建、核心测试和签名校验，未在 Fold7 重新安装这份空间桌面 APK。

首次检出可运行以下命令。已有工作区先用 `git status --short --branch` 核对本地改动，在干净的 `main` 上用 `git pull --ff-only`。家中电脑仍在旧分支且有在做的工作时，可在新目录检出本轮标签。

```powershell
git clone --branch main --recurse-submodules https://github.com/RayforLoy/HUAWEI_CV10_EVO.git
cd HUAWEI_CV10_EVO
git fetch origin --tags
git rev-parse 'cv10-fold7-20261128.1^{commit}'
git ls-tree cv10-fold7-20261128.1 ports/Monado_CV10 ports/piliplus_monado ports/pocket-xr-cv10
git submodule status --recursive
```

## 输入与亮度

手机屏幕中央是点阵触摸板。轻点后抬手向 OpenXR 发送一次确认。按住并滑动时，支持 Google Daydream 触摸板的应用可以读取接触状态和连续 XY，右、上为正。超过系统长按时限再抬手、滑动超出 Android 的触摸容差、第二指介入或取消，都不会误点。显示面板时手机窗口亮度锁定为 10%，隐藏后恢复应用最后请求的亮度，回桌面使用系统亮度。此功能无需 Shizuku。

有两只手柄时默认手机在左、CF20 在右，只有手机时在右。CF20 按键朝上正常握持，长按**实体 Home** 约一秒可以回正。PiliPlus 支持任一手点击，可用选片页面板下方按钮翻页。调影院大小和距离请用「画面设置」。双手缩放动作需要两路持续按下的 select，手机的轻点只发送一个短脉冲。[双手输入与模型](fold7-dual-controller.md)

## 本轮验收

- 最终 Monado 和 PiliPlus 已覆盖安装。清除测试客户端与运行时进程后，Fold7 上独立 OpenXR 客户端进入 FOCUSED，并从右手读取了 CF20 的 96% 电量。其间 CV10 外屏和无线 ADB 先后断开，最终组合的镜片点击、双手缩放与实呈频率待复验。
- Android 16 软件设备使用发布 APK 中原样的 DEX，两次从无进程状态启动。快速轻点和按下 115 ms 后抬手各确认一次。向右滑、向上滑、按住 950 ms 和取消均确认零次。手柄可见期间即使应用请求 73%，窗口仍为 10%，隐藏后恢复 73%。JVM 另回放了手指轻微抖动、滑出再返回、第二指、分离窗口以及无障碍点击等十种情况。[分版本与测试环境记录](../research/evidence/fold7-phone-touchpad-rc4-20261128.json)
- 完整的竖屏面板又通过了两轮跨进程冷启动。模拟器加载正式 APK 的原始界面资源和 DEX，客户端通过实际 Binder 连接把手势发给运行时服务；两轮均验证轻点一次、滑动与长按零次确认，隐藏后亮度恢复。[正式版界面截图](../research/evidence/fold7-phone-touchpad-rc4-ui.png)
- 同日较早的候选版在 Fold7 独立 OpenXR 客户端读到两个方向的触点变化，并实测手机窗口 10%、隐藏后 73%、回桌面恢复自动，外显没有亮度覆盖。该候选版使用了后来取消的长按确认。
- PiliPlus 最终包经过独立重编，核对原生库、DEX 和资源；原生输入与影院两组冷回放共通过 23 项结果断言。上一个双手柄版本已有佩戴者验证双手模型、指向、点击和 CF20 Home 回正。[PiliPlus 发布记录](https://github.com/RayforLoy/piliplus_monado/releases/tag/cv10-dual-controller-zoom-20261128)

## 在家优先复测

1. Fold7 解锁，用原厂线接 CV10。工位使用外接 5 V / 2 A，先接辅助供电再插手机。该线报文是 `0C095306`。保持佩戴感应窗遮挡。无线 ADB 的 IP 和端口每次以手机「无线调试」主页为准。
2. 在 Broker 核对 **Monado CV10**。选择终端当前 `adb devices -l` 中的 Fold7 序列号。从没有播放过视频的状态冷启 PiliPlus，记录 Android 报告的 `LaunchState` 和两侧镜片的选片页。下面的命令会结束当前 XR 会话，保留应用数据。
3. 用手机瞄准一个可辨认的控件，轻点触摸板，核对只选中一次。在同一位置滑动、长时间按住，再抬手，检查是否保持原页面。用 CF20 扳机单独点击，头和 CF20 转向一侧后长按实体 Home，检查模型、光束和面板回到新正前方。打开一次视频再返回，分别保存观察结果。
4. 手机手柄可见和隐藏时，分别通过 `dumpsys display` 核对手机显示的 `mWindowManagerBrightnessOverride`。手机端 10% 对应 `0.1`；宿主跟随系统时，隐藏后通常为 `NaN`。记录外显图层不同实际呈现时间戳的频率；手机活动模式和眼镜面板标称 90 Hz 需另列。[实呈采集](../tools/fold7-present/README.md)

```powershell
adb devices -l
$serial = Read-Host 'Fold7 ADB 序列号'
adb -s $serial shell dumpsys SurfaceFlinger --display-id
adb -s $serial shell am force-stop com.example.piliplus
adb -s $serial shell am force-stop org.cv10.monado.out_of_process.launcher_preview
adb -s $serial shell am start -W -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n com.example.piliplus/.MainActivity
adb -s $serial shell dumpsys display | Select-String 'Display Power Controller|mWindowManagerBrightnessOverride'
```
