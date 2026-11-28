# 华为 VR 桌面的光标与射线渲染

样本为原厂华为 VR 桌面 `com.huawei.vrlauncherx` 11.1.0.337，使用 Unity 2018.4.35f1。以下结论来自 Android 分支的托管代码、Unity 场景资源和 APK 中的 GLES3 着色器。

## 画面上的光标

原厂把光标和射线作为两个独立物体绘制在 3D 场景里。左右控制器各有一套 `HVRLinePointer`。光标是由 `MeshRenderer` 绘制的 Unity 内置 `Quad`，射线由两个世界坐标端点之间的 `LineRenderer` 绘制。两侧 `EventCamera` 上的相机组件在场景中均禁用，代码仍使用其投影函数做 UI 命中检测。光标的世界旋转每次更新为 `Quaternion.identity`，这条路径没有按眼睛位置或命中面法线旋转光标。

| 状态 | 光标 | 射线 |
| --- | --- | --- |
| 命中且交点离 `EventCamera` 小于 7 个场景单位 | 放在命中的世界坐标，使用基础局部缩放 | 沿瞄准方向画到命中距离的 `0.8` 倍，端点另加 `0.020` 的局部上方向偏移，线尖收细到零宽 |
| 未命中 | 放到默认远端，局部缩放为基础值的 `0.25` 倍 | 画到默认远端，线尖同样收细到零宽 |

Android 默认使用白色空心环，基础局部缩放为 `0.24`，未命中时为 `0.06`。`ShowCircle(false)` 可切为白色实心点，基础值为 `0.10`，未命中时为 `0.025`。这两个数值是 Quad 的局部缩放，环或点只占其贴图的中央部分。已检查的桌面代码和序列化事件中没有找到 `ShowCircle` 调用，尚未确认原厂在哪个界面或事件中会启用实心点。超出 7 个单位的有效命中走远端坐标分支，但仍保留命中标记，不能用表中「未命中」状态推定其最终帧缩放。

手机和 CF20 共用这套光标、射线材质。`Controller3Dof` 根据当前控制器可见状态统一设置模型、射线、光标及控制器 Canvas，手机作为控制器时还要求手机屏幕点亮。[输入源切换与亮灭屏](oem-controller-switching.md)

## 射线位置与命中检测

设 `p`、`f`、`u` 分别为 `EventCamera` 对应 Transform 的世界位置、前方向和上方向，`s` 为控制器运行时缩放系数 `HVRController.m_Radio`。以下坐标按 `HVRLinePointer.UpdateLineRenderPosition()` 的稳定更新路径计算。

| 输入源 | 绘制起点 | 瞄准方向 `d` |
| --- | --- | --- |
| 手机 | `p + 0.0644 × s × f` | `f` |
| CF20 | `p + s × (0.069 × f + 0.020 × u)` | `f` |
| 原厂 6DoF 手柄 | `p − 0.010 × f − 0.034 × u` | `f − u`，这里没有单位化 |

默认远端是 `p + 7 × d`。命中距离 `D` 取 `p` 到交点的直线距离，命中时可见线终点为 `p + 0.8 × D × d + 0.020 × u`。圆环直接使用交点坐标，所以线尖与圆环之间会留出间隔。

- **物理物体**　同一 `EventCamera` 上的 `HVRPhysicsRaycaster` 取 `HVRLinePointer.getRay`。其射线始终从绘制起点指向默认远端，在计算可见线终点之前就已构造。
- **桌面 UI**　`HVRGraphicRaycaster` 处理 World Space Canvas。在手机和 CF20 模式下，它用 `LineRender` 的 Transform 构造射线，取沿该射线前方第 `68` 个单位的参考点，投影到 `EventCamera`，再用 `ScreenPointToRay` 求与 UI 平面的交点。候选图形还需通过 `raycastTarget`、矩形范围和 `Graphic.Raycast` 等检查。`68` 是用于投影的参考距离。
- **交点选择**　`HVRInputModule` 依次按 `sortingLayer`、`sortingOrder`、`depth` 降序和距离、候选索引升序排序，取首个有效目标，并将 `RaycastResult.worldPosition` 传回光标。绘制所用的 7 个单位阈值在这一选择之后应用。

## 材质、透明度与遮挡

| 部件 | 资源与画面 | 渲染状态 |
| --- | --- | --- |
| 环形光标 | `Materials/controller_cursor`，`Gaze` 贴图为 `56 × 56`，有非零 Alpha 的区域为 `26 × 26`，中心 Alpha 为零 | `Unlit/Transparent`，队列 `5000`，`SrcAlpha / OneMinusSrcAlpha`，背面剔除 |
| 实心点 | `Materials/controller_spot`，`spot` 贴图为 `56 × 56`，有非零 Alpha 的区域为 `23 × 23`，中心 Alpha 为 255 | 与环形光标同一着色器及渲染状态 |
| 射线 | `LineRender` 材质，白色顶点色，宽度参数 `0.005`，运行时将末端宽度置零。`line_render` 贴图为 `512 × 512`，沿横向的 Alpha 样本为 `153 → 89 → 26` | `Particles/Additive Overlay`，队列 `Overlay+100`（`4100`），`SrcAlpha / One` 加法混合，双面 |

两种着色器均使用 `ZTest LEqual`、`ZWrite Off`。光标队列晚于射线。它们会被同一深度缓冲里已经写入且更近的几何遮挡，自身透明像素不会写入深度。这一结论覆盖 Unity 的绘制状态，最终镜片画面中不同合成层之间的遮挡仍待实机观察。[Unity 深度状态](https://docs.unity3d.com/cn/2018.4/Manual/SL-CullAndDepth.html) · [Unity 混合因子](https://docs.unity3d.com/2018.4/Documentation/ScriptReference/Rendering.BlendMode.html) · [Unity 渲染队列](https://docs.unity3d.com/2018.4/Documentation/ScriptReference/Rendering.RenderQueue.html)

## 复核位置

### CF20 的握持原点和前端

`level1` 的模型 `DefaultController`（Transform 1842）与 `EventCamera`（Transform 984）同属 `HVRRightController`。相机局部变换为单位矩阵。`HVRController.UpdateControllerPos` 将手柄姿态和手腕位置应用到共同父级。保留模型静置旋转、1.5 倍局部缩放和部件变换，取动态手臂缩放 `m_Radio = 1` 后，OpenXR 握持坐标中的包围盒为 X −28.7 至 +28.7 mm、Y −23.5 至 +28.6 mm、Z −78.7 至 +82.6 mm。圆形触控面中心在 Y 约 +25 mm、Z 约 −47 mm。 [GLB 提取与应用调用](cf20-openxr-model.md)

| 部件 | sharedassets1.assets 网格 ID | 实物对应 |
| --- | ---: | --- |
| `c_b` | 42 | 外壳 |
| `c_f` | 47 | 正面圆形触控面 |
| `b_l`、`b_r` | 56、54 | 左侧返回键、右侧 Home 键 |
| `c_t` | 35 | 前端下方扳机 |
| `v_m` | 51 | 音量按键 |

六个部件共用 `sharedassets1.assets:31/controller16` 图集。外壳使用 `:6/HVR_WhiteRGB`，按键使用 `:5/HVR_WhiteButoon`。GLB 保留原始网格、法线、UV 和图集 RGB，用标准 PBR 材质近似原厂随视角变化的边缘高光。外壳 shader 使用图集 alpha 计算高光，因此 GLB 的表面按不透明材质处理。

### 场景与着色器

Unity 序列化文件路径均相对于 APK 中的 `assets/bin/Data/`。冒号后为 Unity Path ID。

| 证据 | 可复核位置 |
| --- | --- |
| 运行逻辑 | `Managed/Assembly-CSharp.dll` 中的 `HVRLinePointer.Awake`、`LateUpdate`、`UpdateLineRenderPosition`，以及 `HVRInputModule.GetRaycastResult`、`UpdateAnchorPos`、`HVRGraphicRaycaster.Raycast`、`HVRPhysicsRaycaster.Raycast`、`Controller3Dof.LateUpdate`、`HVRController.SetControllerStatus` |
| 场景及左右指针 | `globalgamemanagers:11` 的 BuildSettings 将 `level1` 对应到 `Assets/Scenes/ManagerScene.unity`。左侧 `level1:2268`，光标 `level1:758`，射线 `level1:410`。右侧 `level1:2448`，光标 `level1:385`，射线 `level1:586` |
| 光标资源 | 空心环材质 `2533c3314ef91f1479aafb6b0b829ff6:1`，贴图 `4607b478851d33c47b1c3c997383e3ca:1`。实心点材质 `30830268d1c121d41a65b42ff12c33d4:1`，贴图 `ad8e9c2b497c6d44999c87aa89855bf7:1`。两个材质通过 Unity ResourceManager 映射到代码中的 `Resources.Load` 路径 |
| 射线资源 | `sharedassets1.assets:12` 材质、`:27` 贴图、`:79` 着色器 |

| 样本 | SHA-256 |
| --- | --- |
| `com.huawei.vrlauncherx.apk` | `1e91f00d596c636c3f52dddc494ee6b745cdf90bb3a0838ff203f9ae54b92dd3` |
| `Managed/Assembly-CSharp.dll` | `b5b4bcb3b6fc27fe01df1f77f841a6b789d6d221df631e5f081954d77d7ac6cf` |
| `level1` | `e432d74c493a8d30b5bee3d94f56030cd1b723c7a498896feb99607982aa406b` |

本次完成静态核对。双眼中的实际角尺寸、不同合成层的遮挡关系和模式切换帧的视觉表现尚未实测。
