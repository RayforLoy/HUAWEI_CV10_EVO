# 早期华为 VR 客户端与原厂手机线的供电控制

在头显 `CV10AC10.0.1.357` 中可以沿指令查到两种由主机触发的线盒通信。其一查询原厂线的识别信息，其二将线缆切换到 USB 维护模式。已取得的 2019 年 VR 视频和 2021 年 SDK 服务中，尚无证据显示应用在进入 VR 时另行打开线盒的供电输出。这个结论覆盖下列二进制与入口。EMUI 的 USB-C/PD 驱动、其他版本、以及线盒自行响应负载或协商的行为，需要单独验证。

## 实际取得的两个版本

| 包 | 来源与版本时间 | 本地复核 |
| --- | --- | --- |
| 华为 VR 视频 `com.huawei.himovie.vr` | 镜像页面标记更新于 2019-12-27。其手机端普通下载实际提供 `8.0.4.303`，versionCode `80004303`。[下载页](https://m.jb51.net/softs/656057.html) | 131,341,480 字节，APK SHA-256 `fd9de29eb5128fa3ee4307c8eca65eb8c1cb21aee04c35e217f598a0c63f14a3`。Android SDK 的 apksigner 验证 v1、v2 签名通过 |
| 华为 VR SDK 服务 `com.huawei.hvrsdkserverapp` | 华为官方 Unity SDK 压缩包中的 `3.5.0.68.apk`，versionCode `35068`。ZIP 内记录 APK 时间为 2021-10-14，官方 CDN 对象日期为 2021-10-21。[官方 SDK 页](https://developer.huawei.com/consumer/cn/doc/graphics-Library/unity-sdk-download-0000001142315529/) · [官方归档 URL 与双重摘要](../../research/sources.json) | 66,416,668 字节，APK SHA-256 `5c60378ce4229e436fc6a929d4ad2fd362818faadead22008a3eae6dd0fe3547`。下载的 ZIP SHA-256 为 `c699a924f372e9a2d0cf536d7c5f911de83da10e17935e9dfb2d0871578d9dc4` |

两份 APK 的签名证书 SHA-256 均为 `1e3eee2a88a6df75fb4af56adc8373bb818f3cb90a4935c7821582b8cebb694c`，证书主体含 `CN=AndroidTeam, O=Huawei`。AppGallery 的公开包名跳转分别给出视频 `C100197257`、服务 `C100137735`。文件保留在本地 `.research/legacy-vr/sdk-video/`，按包名及版本命名。[视频 AppGallery](https://appgallery.huawei.com/app/C100197257) · [SDK 服务 AppGallery](https://appgallery.huawei.com/app/C100137735)

SDK 服务的 apksigner v2 签名验证通过。华为另列出 2019-01-04 的 Unreal 插件 2.0.0.28，官方给出的 ZIP 摘要为 `8a67c1c4f81ea235f70cec0fdedf73200db3785c37d8a1cf50d4b5ba2013c299`。该链接公开页面仅给出下载协议入口。官方集成说明列举两个插件目录，尚无该归档附带服务 APK 的证据。[华为 Unreal SDK 下载页](https://developer.huawei.com/consumer/cn/doc/graphics-Library/unreal-sdk-download-0000001102329402/) · [官方插件集成说明](https://developer.huawei.com/consumer/cn/doc/graphics-Guides/app-dev-unreal-plugin-0000001205768073/)

2019-11-12 的视频 `8.0.3.302` 另有 APKMirror 条目，记载 SHA-256 为 `3be370668a16e779b1f2d1fd028a26d6e9066945db9b6877904720a2d71ebed3`，本轮未取得对应文件。华为旧 Codelab 的最低 SDK 要求为 `3.0.0.17`，教程所举文件为 Unity 插件，尚未取得同版本的服务 APK。另一个镜像标为视频 `8.1.0.300`，实际从其下载地址取得的是与 P40 资料相同的 `8.2.0.300`，故未将其日期赋给旧版实包。[8.0.3.302 历史条目](https://www.apkmirror.com/apk/huawei/huawei-vr-video-%E5%8D%8E%E4%B8%BAvr%E8%A7%86%E9%A2%91/%E5%8D%8E%E4%B8%BAvr%E8%A7%86%E9%A2%91-8-0-3-302-release/) · [华为旧版 Codelab](https://developer.huawei.com/consumer/cn/codelab/HUAWEI-VR-SDK/index.html) · [镜像页面](https://www.danji100.com/app/127170.html)

## REA 与包内实际指令

- REA 6.7.0 的 `inspect-android-package` 通过 JADX headless 0.7.1 读取了两份签名样本。2019 年视频 APK 的 manifest 声明 `com.huawei.vrservice.permission.VR`、`com.huawei.vrlab.VrPlayerApplication` 和华为 VR 应用元数据，APK 内含 Unity 的 `Assembly-CSharp.dll` 与 `libHvrSurface.so`。REA 报告包含 3,916 个类，证据 ID 为 `ev_bc93d32737345088a0e256459e181289b1fe56b42c10c2c313011381b3c61307`。
- 2021 年 SDK 服务声明 `android.uid.system` 与 `ArvrRuntimeService`，REA 报告包含 413 个类，证据 ID 为 `ev_8738be186dbbcdfc1a614aa35e2bb9984712d8a1fe986ea71fd43eda8242ef85`。遍历两个 ZIP 的全部成员，解压后按连续 ASCII 搜索：2019 视频未检出完整的 `AT^` 命令名；服务仅在 `libruntime_service_module.so` 的三个副本中检出。其 arm64 版 ELF 内文件偏移 `0x19B4A4/0x19B4B5/0x19B4C0/0x19B4CC` 为型号、PSN、版本、完整版本查询，`0x19B8CE/0x19B8FE` 为时间戳，`0x19D62E/0x19D641` 为 `SET6DOFSTATUS=1/0`。字符串搜索无法识别动态拼包、外部 Binder 服务、嵌套压缩或内核路径。REA 报告与逐成员结果在同一本地目录。
- 头显 `AT^SET6DOFSTATUS` 的对应处理器在 `0x85021` 将状态保存到 `0x2004AA28`。可核对的读取函数是 `0x84F81`，其直接调用位于温度处理路径 `0x73587`。仅凭此指令无法推定它是线盒的 VBUS 开关。没有为这项研究向设备发送指令。

两个版本的启动方向也能从具体方法核对。2019 视频的 `com.huawei.vrlab.HVR3DActivity.onCreate` 调用父类后，注册受权限保护的 `ACTION_VR_SERVICE_GLASS` 广播接收器，随后检查权限。2021 SDK 服务的 `ArvrRuntimeService.onCreate` 首先调用 `com.huawei.hvrsdkserverapp.b.a.isVrMode`，后者通过 `getSystemService(IVRSystemServiceManager.VR_MANAGER)` 取系统管理器并调用 `isVRMode()`。若结果为假，服务立即停止。在此调用链，决定手机是否已进 VR 的状态由系统提供。两个启动入口与系统判定方法的 REA 证据分别为 `ev_51beab4c390b9002d6b642f7487d696ab0a08692543e4e0bd03ff80325bfffa5`、`ev_0ba961042ade854d838f2b7300d09e0a13e17703bf6c0892ad641ef94295608f`、`ev_12394e83bd49f49d3d7fd1bfe23481333f95295dc1fb543c96705b0a1b7f2cb4`。

## 哪些主机请求能到达线盒

头显偏移按完整 `halliday.dfu`，SHA-256 为 `85579969f7362cc9acf894cd351d54328763b1a6819c0953c64857a5d1aae7e8`。文件 `0x525` 对应运行地址 `0x08020000`。线缆裸镜像用 C9.49.6、C9.52.6 两份本机备份，样本 SHA 与反汇编约定见[线控固件分析](vl105-pd-analysis.md)。

| 主机入口 | 从头显到线盒的边界 |
| --- | --- |
| `AT^CABLESN?`、`AT^CABLEINFO?` | 头显处在相应线型时，SN 查询设置本地待答位 `0x04`（`0x84D57`），信息查询设置 `0x08`（`0x84E5D`）。发送点 `0x84D63/0x84E69` 均调用 `dp_ufp_u_send_dp_attention_custom`，传入 `0x80000000`。经 `0x91157` 分派入站消息，低 16 位 `0105/0106` 分别进入 `0x91063/0x910BB`。线侧 `0x03B5/0x0917` 分两次组装相应的厂商身份消息。信息回包能表明身份交换成功，电量与温度字段可能仍为无效缓存 |
| `AT^CABLESWITCHUSB` | `0x84F31` 检查已识别的线型为 ASCII `1`，确认后延时，再在 `0x84F79` 传入 `0x40000000`。已知 Android 桌面在用户选择升级线缆并移除显示时经过这个入口。现有代码的用途是切换 USB 维护路径。[桌面调用链](android-cable-analysis.md) |
| 共同的 DP 发送函数 | `0x7E79D` 取当前上下文并以 SVID `0xFF01` 查找 DP 模式，保留状态字低九位，加入 `0x88` 和调用者的高位标志，在 `0x7E7E5` 向发送函数提交。应用代码的直接分支调用扫描只找到上列三处。这个数量限定于可解析的直接分支 |
| `AT^SWITCHSCREEN`、来源设置 | `0x84C55` 将开关转给头显显示状态处理 `0x6B2F5`。来源处理 `0x84105` 将数字存入 `0x2000ABB8`，`0x840D3` 从该处读回手机或 PC 标签。两者的入口都无上述定制 Attention 调用；标签的读回无法确认 PD 电力角色。佩戴时另外有双路背光和音频动作。[佩戴与背光执行顺序](headset-pd-analysis.md) |
| `AT^TCHRENABLE`、`AT^VBUS` / `VBUS?`、`AT^IINLIMIT` / `IINLIMIT?` | 用固件自身启动算法还原的 AT 表将这些名称映射到同一处理器 `0x8243F`。该处理器用四个零调用普通应答函数，没有电源读写。用这些名称作开关或测量没有固件依据。[命令表与实测字段](../firmware-resource-analysis.md) |

## NOLO 在 Windows 上发送的 PC 模式与 IMU 命令

NOLO 的 `setPCMode` 所用的 Windows HID Feature 报告与短 HID 报告在固件中汇合。USB SET_REPORT 完成处 `0x56325–0x5633D` 识别 128 字节、首字节为 `04` 的格式，将第二字节解释为内层长度，从第三字节开始传递数据。对于 `04 02 0E 01 …`，`receive_hid_cmd` 实际接收的是长度 2、内容 `0E 01`。省略尾部的字节在 Windows 报告中仍存在。

- **PC 模式。** 内层 `0E` 在 `0x65037–0x65047` 检查长度至少 2、来源值小于 3，并将其写进 `0x2000ABB8`。与 `AT^SETSOURCE` 相比，此入口另把有效载荷作为系统消息 `13/2C` 传递。设备管理器在 `0x61B25–0x61B51` 将命令 `2C` 映射为 ioctl 6。启动数据中的对象 `0x2000A250` 通过方法表 `0x2000A230` 的 +0x18 指向 `sys_ioctl`（DFU `0x79213`）。`0x792F5–0x79333` 检查载荷，来源 1 才打印 `detect pc source,start charging`，日志调用后直接返回。此分支没有 GPIO、I²C、充电器或 PD 调用。两种来源入口的可见状态效果相同；已知后续佩戴任务在来源 1 时会多调用音频回调。可在测试前后用 `AT^GETSOURCE?` 核对，结束时用原值恢复。
- **IMU。** 内层 `05 02` 在 `0x64F93–0x64FC9` 经 `0x64D11` 将掩码 2 映射为内部传感器 `0F`，以操作 1 申请启用。内层 `06 02` 经 `0x64FCB–0x64FF5` 发送操作 3 停用。Android SDK 的 `Wallex` 用相同的内层值。主动测试应观察实际 IMU 样本；只有测试前停用且没有其他客户使用 IMU 时才用停用命令还原。[原生 Android 对照](../firmware-resource-analysis.md)

### 原厂桌面区分 VR2 与 CV10 的低功耗行为

华为桌面 `11.1.0.337` 的 `z0.c.i()` 在 DEX `0x1AAE8A` 以 Binder 编号 2108 查询头显类型。摘下处理 `t0.c.n`（`0x181180`）根据头显类型决定是否发送 2002、参数 0。类型 1 跳到 `0x181238`，日志为 `halliday do not need go to sleep`。配对发送 0 与 1 的另外两条路径位于 `w0.b$c.d/k`（调用点 `0x192634/0x192A64`），仅在类型为 0 时执行，日志标作 Vr2。`t0.c.t` 处理佩戴时另有 2003（`TYPE_SET_VR_SCREEN`）开屏分支。旧 VR 服务 `11.0.0.322` 收到 2002 才在 DEX `0xE2A42/0xE2A54` 按参数调用 `VRHelmetUtils.setLowPowerModeNativeJNI`。

头显仍支持该 HID 命令。`0D 00` 在 `0x79297` 投递内部系统事件 6，系统随后在 `0x78ECB` 请求睡眠并置下次佩戴的标志位。`0x5DD0D` 只从 READY（3）进入 SLEEP（5），该请求的原因 5 在 `0x5DA8B/0x5DAB9` 直接返回。`0D 01` 在已处于 5 时调用 READY 转换，它的原因 4 在 `0x5DA55/0x5DA79` 同样直接返回，`0x5DCBB` 随后通知已注册模块。以上分支中未见主动移除 USB、停心跳定时器或修改保护参数。系统内部事件 6 与真实传感器的外发 VCOM 事件 2 有独立来源。若做低功耗实验，它能检验改变下次佩戴的背光启动顺序是否影响掉线；它不能验证华为桌面在 CV10 上遗漏了正常启动步骤。HID 发送完成也不能证明异步状态已经切换。[睡眠标志的实际消费者](headset-pd-analysis.md)

对故障定位而言，下一份有区分度的记录是**工作正常的原厂手机线在佩戴前后的 CC/PD 消息与眼镜端 VBUS 同步波形**。可将其与故障线在相同视频模式、相同佩戴动作下对齐，查主机是否在背光唤醒前额外申请电源合同、发送厂商消息，或电压先于 USB 集线器掉线下跌。只有主机供电角色标签、旧 APK 的权限、查询成功或开屏应答，均无法独立证明这种因果关系。[本机 USB 和镜片对照](company-pc.md)
