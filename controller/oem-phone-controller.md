# 华为 VR Glass 原厂手机操控

对照华为 VR SDK 3.5.0.82 和华为 VR 桌面 11.1.0.337。手机在 3DoF 模式下充当一个虚拟控制器。转动手机改变射线朝向，触摸主屏产生确认、触控板、返回和主页事件。输入源的选择与断线见[手机与 CF20 的控制切换](oem-controller-switching.md)。

## 手机屏幕手势

以识别器使用的竖屏坐标为准，宽高为 `W`、`H`，`x` 向右、`y` 向下。触点在按下时决定所属区域，手指越过分界后仍由原区域处理。底部优先于左右边缘。表中的位移从按下位置起算，单位为屏幕像素。

| 起始区域 | 操作 | 原厂判断 |
| --- | --- | --- |
| 中央，`0.05W ≤ x ≤ 0.95W` 且 `y < 0.90H` | 点击射线指向的对象 | 按下满 50 ms 后的第一个 `MOVE` 检查横向和纵向位移是否都严格小于 5 px。命中时同时置位 `confirm` 和 `thumbstick`，持续到抬起或取消。 |
| 中央，同上 | 滑动触控板，桌面可左右切换卡片 | 按下和移动时更新坐标 `u = x / (0.90W)`、`v = y / (0.90H)`。原生 SDK 在触控结束时按轨迹首尾的归一化位移判定滑动，平方距离须达到 `0.04`。横向位移绝对值大于纵向时判为左右，其余判为上下。 |
| 左侧 `x < 0.05W` 或右侧 `x > 0.95W`，且 `y < 0.90H` | 向内滑返回 | 水平向内至少 40 px，且水平位移严格大于垂直位移，随后保持 `back` 到抬起或取消。 |
| 底部，`y ≥ 0.90H` | 上滑后松手回主页 | 向上至少 40 px，且垂直位移严格大于水平位移，随后保持 `home` 到抬起或取消。桌面的短按计时从识别到 `home` 按下开始。 |
| 底部，同上 | 上滑后继续按住以回正 | 滑过同一阈值后保持 `home`。桌面在约 1 秒时识别长按，并在一次持续按压中触发一次回正。 |
| 手机实体电源键 | 显示或隐藏手机模型和射线 | 原厂触控服务在电源键抬起时切换手机主屏的电源模式（开为 `2`，关为 `0`）。关闭时停止转发触摸和采样手机姿态，保留最后一次姿态。重新开启时启动采样。 |

50 ms 条件由移动事件检查。该次检查无论成功与否都会消耗本次手势的确认机会。仅含 `DOWN → UP` 的事件序列在这一层没有确认事件。中央坐标不减去左边缘偏移，也不裁剪，抬起或取消后恢复为零。触控状态取决于两个坐标分别乘 255、转整数再转 Java `byte` 后是否至少一个非零。华为公开说明给出的用户动作与这些分区对应，并说明手机模式不提供实体手柄的扳机和截图功能。[华为手机操控说明](https://consumer.huawei.com/cn/support/content/zh-cn00776840/)

`VrTouchService` 通过华为系统接口 `VrTouchInterfaceEx` 接收主屏事件。触控转发要求手机模式和交互显示开启，事件源须为 `SOURCE_TOUCHSCREEN`（`0x1002`），首指工具类型和设备 ID 均非零。`PhoneController` 还检查 SDK 前后台状态，只从首指读取坐标，处理 `DOWN`、`MOVE`、`UP` 和 `CANCEL`。若主屏实际尺寸为横屏，方向值为 1 和 3 时分别把原坐标换成 `(W-y, x)` 和 `(y, H-x)`。原厂针对华为折叠屏另有显示模式回调，重新计算触控边界。

## 姿态、射线与回正

1. 手机的陀螺仪、加速度计和磁力计由原生 `MobileSensor` 采集。实际加载路径为 `libvrsdk.so → libWalleAlg.so`，后者的 `PhoneControllerPose` 把 IMU 数据送入 `VrPoseState::calculatPose`，读取时以当前原生时钟调用 `predictPose`。传感器队列请求各传感器的最小采样间隔，实际频率由设备决定。JNI 将原生四元数的 `xyzw` 顺序重排为 Java 的 `wxyz`。
2. 桌面 `HVRController.UpdateControllerPos` 把控制器姿态写入模型的局部旋转，3DoF 模型的腕部位置由相对头显的虚拟手臂计算。`HVRLinePointer` 从这个模型沿前向生成射线。触屏坐标用于点按和滑动，移动射线要转动手机。
3. 桌面 `HVRInputModule` 将 `ButtonConfirm` 接到射线点击链。释放时检查按下对象的抬起处理结果，并要求触控板起止坐标差的长度小于 `0.1` 和 Unity 鼠标位移小于 `3`，才发送 `PointerClick`。滑动则作为方向事件发给当前选中对象，供页面翻卡或滚动。
4. 桌面 `ButtonUtils` 从虚拟 `ButtonHome` 的按下沿开始计时，源码读取的是 `TimeSpan.Seconds`。长按使 `RecenterCanvas` 调用 `HVR_ResetSensorYaw` 并重新设置画布朝向。`Controller::getPose` 另有重算 Y 轴补偿并乘入姿态输出的分支。已确认重新开启手机交互显示时，通知 `2097153` 会请求重置控制器姿态。华为说明底部上滑并停留会同时回正视角和射线，桌面长按时手机射线的最终原生调用链仍待复核。[华为手机操控说明](https://consumer.huawei.com/cn/support/content/zh-cn00776840/)

## 原厂 SDK 的 3DoF 数据

`PhoneController` 的类型和控制器索引均为 `0`。`VrControllerManager.getData()` 生成 31 个浮点数，以下为从零开始的索引。

| 索引 | 手机模式的值 |
| --- | --- |
| `0–1` | 控制器索引 `0`、固定电量 `100` |
| `2–5` | 依次为确认、返回、主页、触控板按下。触控板按下与确认共用同一个布尔值 |
| `11`、`16–17` | 触控板接触状态及 `u, v` |
| `18–21` | 手机旋转四元数 `w, x, y, z` |
| `22–30` | 对外的加速度、角速度、位置字段均为零 |

模拟扳机、握持和振动未由手机模式实现。射线的虚拟腕部位置由桌面单独计算。

## 复核位置

| 样本 | SHA-256 | 入口 |
| --- | --- | --- |
| `com.huawei.hvrsdkserverapp` 3.5.0.82 | `e0af366239d1c9c8ad384651a3173dfdfccac9ba221768f4db6c5349101d1444` | 比较 `classes.dex` 和 `assets/hvrframework.dex` 的 `VrTouchService.VrInputEventCb`、`PhoneController` 的 `calcBoundaryThreshold`、`touchEventProcess`、`isClickDown` 和 `genPhoneControllerRawData`，以及 `VrControllerManager.getData`。 |
| SDK APK 内 `assets/arm64-v8a/libvrsdk.so` | `5b95a82174d26b548829ff4fd8399603d5d791101eabfc35786276c3ddf7ae39` | `Controller::touchpadSwipe` 在 `0x6fae4`，平方阈值存于虚拟地址 `0x11ac68`。`Controller::getPose` 在 `0x71590`，JNI `getPhoneControllerPose` 在 `0xc3804`，`PhoneControllerPoseCaller::init` 在 `0xc765c`。 |
| SDK APK 内 `assets/arm64-v8a/libWalleAlg.so` | `ab24d28aee9b2dabc27a6dc412a0dac4bcde4315434c162aba57adf54a18d7a3` | `PhoneControllerPoseStart`、`PhoneControllerPoseGet` 在 `0x24a8c` 和 `0x24b5c`，手机传感器注册在 `MobileSensor::onThreadReady`（`0x25478`）。 |
| SDK APK 内 `assets/armeabi-v7a/libvrsdk.so` | `f1e4e63d0e876313b910115fda33408b0aaefb637f693113e79c64aea95b4af2` | Thumb 模式检查 `Controller::touchpadSwipe`（`0x55030`），平方阈值在 `0x55188`。 |
| `com.huawei.vrlauncherx` 11.1.0.337 | `1e91f00d596c636c3f52dddc494ee6b745cdf90bb3a0838ff203f9ae54b92dd3` | `Assembly-CSharp.dll` 中的 `HVRInputModule`、`HVRController`、`HVRArmModel`、`HVRLinePointer`、`ButtonUtils`、`RecenterBase`、`RecenterCanvas` 和手机新手引导 `PhoneOobeManager`。 |

以上为 APK 的静态结果。实际轻点时华为触控服务提供的事件序列、不同屏幕模式的坐标变换和原厂射线回正效果尚无真机记录。
