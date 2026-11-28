# 在 OpenXR 应用中显示原厂 CF20

华为 VR 桌面 `com.huawei.vrlauncherx` 11.1.0.337 的 Unity 场景 `level1` 在 `HVRRightController/DefaultController` 下保存了六个部件。静止时的机身、触控面和按键共 3,350 个三角形，使用原厂 `controller16` 贴图和两种材质。右手 `EventCamera` 给出了原厂瞄准轴。[原厂射线的绘制与命中位置](oem-pointer-rendering.md)

## 提取与构建

使用 Monado CV10 v0.1.4-rc.3 时，提取 GLB 后可直接在 Monado 首页的「更多选项 → 导入已校准的 CF20 手柄模型」选取文件，随后重开 XR 应用。同一 APK 可以服务不同的客户端，模型跟随物理 CF20 的手部角色。以下 Gradle 步骤供希望自行嵌入模型的开发者使用。

在装有 `UnityPy==1.25.4` 和 `numpy` 的 Python 环境中，从仓库根目录运行以下命令。`$apk` 指向本机的华为 VR 桌面 APK。提取器会校验输入版本，并把 Unity 层级、坐标手性和尺寸换算成 OpenXR 握持坐标系中的米。

```powershell
python controller/extract-cf20-model.py $apk .research/cf20-model/cf20.glb --evidence .research/cf20-model/evidence.json
$model = (Resolve-Path .research/cf20-model/cf20.glb).Path
Push-Location ports/Monado_CV10
try {
    .\gradlew.bat "-Pcv10ControllerModel=$model" -Pcv10Abi=arm64-v8a -Pcv10LauncherPreview=true :src:xrt:targets:openxr_android:packageOutOfProcessRelease
} finally {
    Pop-Location
}
```

| 本机核验项 | 值 |
| --- | --- |
| 原版 APK SHA-256 | `1e91f00d596c636c3f52dddc494ee6b745cdf90bb3a0838ff203f9ae54b92dd3` |
| GLB SHA-256 | `76e976932c96b7ebc3f844b773e8476dd16777d29e8a5d2a447f332a1a141087` |
| GLB 结构 | 182,180 字节，6 组索引三角形，2,569 个顶点，内嵌 PNG。Khronos glTF Validator 报告 0 个错误、0 个警告 |
| 握持方向 | 按键朝 +Y，手柄前端朝 −Z。射线起点相对握持原点向上 20 mm、向前 69 mm |

仓库提供提取器。原厂贴图、网格和包含这些资源的运行时由本机输入生成。

## 第三方应用如何调用

应用在创建 OpenXR 实例时启用 `XR_EXT_render_model` 和 `XR_EXT_interaction_render_model`。完成动作绑定和首次 `xrSyncActions` 后，枚举模型 ID，按需查询关联的手，读取 GLB，创建模型空间。每帧用同一个 `predictedDisplayTime` 和场景参考空间定位模型和应用的瞄准动作。模型空间提供外观的位姿，`/user/hand/right/input/aim/pose` 提供射线起点和方向。应用按模型空间的跟踪标志决定是否绘制，并在模型变更事件后重新枚举。[Khronos 模型资源规范](https://registry.khronos.org/OpenXR/specs/1.1/man/html/XR_EXT_render_model.html) · [交互设备模型规范](https://registry.khronos.org/OpenXR/specs/1.1/man/html/XR_EXT_interaction_render_model.html)

CF20 的旋转来自手柄 IMU，握持位置由运行时估算。原厂模型按真实大小绘制。长按 Home 回正时，使用运行时 `LOCAL` 空间的应用可让模型、射线和世界固定面板一起更新。

## Fold7 实测

最终安装组合为 Monado CV10 Preview 与 PiliPlus 的冷启动修复版。加载模型、转动、重进会话期间，122 个同一预测时刻的样本中，模型与射线的夹角在日志精度内为零，起点与原厂偏移的最大差为 0.137 mm。17:29:23 的实体 Home 长按由运行时确认回正成功。[包摘要、姿态和佩戴验收](../research/evidence/fold7-cf20-model-20261128.json) · [两轮冷启动复测](../research/evidence/fold7-piliplus-cold-window-20261128.json)

2026-11-28 在原厂线、外接 5 V / 2 A 和右手 CF20 上，PiliPlus 通过运行时读到 182,180 字节的 GLB。可从头显右下方看到机身、圆形触控盘和从前端伸出的蓝线。38 个同帧样本中，模型前方与瞄准方向的最大夹角为 0.035° 以内，射线起点相对原厂安装位置的最大偏差为 0.35 mm。CF20 长按 Home 后，校正后的手柄与头部水平朝向之差从 −48.88° 变为 −0.02°。佩戴者确认机身、蓝线和面板一起回正。[实测记录](../research/evidence/fold7-cf20-model-20261128.json) · [左眼合成图局部](../research/evidence/fold7-cf20-model-before-aa-left-20261128.png)

首次安装时，光标能用但手柄和蓝线均不可见。Fold7 的 Adreno 驱动报告顶点与片元着色器的 `beamLength` 精度不一致；两阶段统一精度后 GLB 成功加载并在两眼绘制。原厂材质的动态边缘高光在本地 GLB 中以静态 PBR 材质近似。[原厂资源复核](oem-pointer-rendering.md) · [现有设备的其余 OpenXR 接口](../docs/fold7-openxr-capabilities.md)

用户随后指出斜射线的锯齿严重。PiliPlus 改为按每眼推荐分辨率计算线段与圆端的像素覆盖，保留命中光点。对比两张左眼合成图中黑底上倾角接近的线段，逐行绿色总强度的变异系数从 0.241 降至 0.067。佩戴者确认扫动时明显改善，影院内激光也正常。手机保持竖屏，头显里的选片页实测为 1680×1260。手柄首次贴图加载时，两次查询偶尔会跨过新的 BLE 样本；运行时现对相同预测时刻复用握持姿态，Home、掉线和重连会使缓存失效。[抗锯齿版左眼局部](../research/evidence/fold7-cf20-model-aa-left-20261128.png) · [样本和包摘要](../research/evidence/fold7-cf20-model-20261128.json)
