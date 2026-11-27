# CV10 中心分区与增强渲染

静态对照的样本为华为 VR 桌面 `11.1.0.337`、华为 VR 视频 `8.2.0.300`、VR 手机投屏 `11.1.0.325`，以及在 P40 Pro+ 上使用的运行时 `3.5.0.82`。样本版本、来源与提取方法见 [APK 离线分析](apk-research.md)。

## 华为原厂档位

| 场景 | 校正前渲染规格 |
| --- | --- |
| 华为 VR 桌面和 VR 视频 | 场景选择 High 分区档。每眼分别绘制全视场和中心视图，两张纹理的档位上限同为 1280×1280。Medium 和 Low 的上限分别为 1080×1080 和 720×720。 |
| 华为 VR 手机投屏 | 按能力选择 1552×1552 或 2048×2048，双层路径用各视场边界角的一半确定中心投影。被投射的手机内容另有 832、896、1024、1280、1536 像素档。 |
| 华为标准 OpenXR | 普通双目推荐尺寸为每眼 1552×1552。应用可按自身策略创建交换链。 |

桌面和 VR 视频的中心投影在每轴采用全视场投影半角正切的 0.4 倍。1280 像素的中心纹理因此达到约等效每眼全视场 3200 像素的局部线性采样密度。Unity 场景倍率、尺寸回调和温控分支仍会影响实际分配。复核入口为 Unity 场景中的 `HVRCamera.PartitionedRenderingStatus`，以及 `HVRRenderMgrCore` 的尺寸和温控处理、`HVRCamCore` 的两份投影。

## enableEnhancedRenderMode

P40 样本的 `VrDistortionRender` 默认关闭增强渲染。初始化读取属性 `hvr.enhanced.debug`，值为 `true` 时调用 `enableEnhancedRenderMode`。普通畸变的 `Program 16` 使用三色的独立 UV。`Program 17` 在其基础上组合中心五点锐化、色调和饱和度处理。普通增强路径从绿色 UV 中心向外衰减，半径达到 0.15 时归零。运行时曾同时预加载两种程序，现有 SDK Demo 日志的实际绘制选择了 `Program 16`。三个原厂应用各自的执行状态待实机确认。

复核使用运行时 `assets/armeabi-v7a/libvrsdk.so`，SHA-256 为 `f1e4e63d0e876313b910115fda33408b0aaefb637f693113e79c64aea95b4af2`。对应入口包括 `HxrHelmet::HxrHelmet`（`0xa6f00`，普通尺寸 `0x610`），`VrDistortionRender` 默认状态（`0x5f562`）和 `VRRenderWalleImpl::createTextureAndGeometry`（`0x6893c`，检查属性）。

## Monado CV10 的接入方式

CV10 的物理双目输出保持 3200×1600。普通 OpenXR 应用可按运行时返回的推荐边长重新分配交换链。启用超分辨率时，软件预设用华为 High 中心分区的等效全视场密度，即每眼 3200×3200，也可自定义。Pocket XR 光学入口会用双倍边长创建左右并排的源显示屏，适配版 Pocket XR 按实际大小重绘每眼。两条软件路径均使用整眼渲染，原厂独立中心纹理的性能特性仍需支持分区提交的应用才可对照。

`enableEnhancedRenderMode` 独立控制合成阶段的中心增强，默认关闭。提高源分辨率会增加渲染和合成开销，也可能放大 Fold7 已有的发热或掉帧问题。新档位、锐化和运动清晰度均待验收。[Fold7 已知问题](fold7-openxr-known-issues.md) · [Pocket XR CV10 build and display integration](https://github.com/RayforLoy/pocket-xr-cv10/blob/codex/cv10-optics/docs/CV10.md)
