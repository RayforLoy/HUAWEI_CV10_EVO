# CV10 固件与 PC 升级器

2026-11-25 检查了 `resources/qq_gourp` 中的升级包、已有运行日志和设备问题汇总。升级器包含两款头显的应用镜像。CV10 的镜像提供查询连接线信息的线索，包内未找到可识别为原厂连接线的独立镜像或读回、写入连接线的流程。用户报告的线版本为 `C9.49.6`，线单独接入电脑后，WinUSB 实读版本字节为 `0c 09 49 06`。

## 两份 DFU 的目标

原 ZIP 的 SHA-256 为 `272ad42b514a552821305201b6487bc203c92c119815d36b6b88fa677a6ae23e`。压缩包内 28 个普通文件与已展开目录的同名文件逐字节一致。已展开目录下的两份运行日志是额外文件。直接解析 DfuSe 前缀、target、element 和后缀，得到以下结果。

| 镜像 | 产品与内置版本 | 文件字节数 | element 数据字节数 | SHA-256 |
| --- | --- | ---: | ---: | --- |
| `halliday.dfu` | CV10，`10.0.1.357` | 810371 | 810062 | `85579969f7362cc9acf894cd351d54328763b1a6819c0953c64857a5d1aae7e8` |
| `wallex.dfu` | AV02，`C00B268` | 425836 | 425527 | `c9eb16d9bd9081fd92a5cc444e752ccb81fbaaab05eb5ba89ceb64024dbc363a` |

两份容器的版本均为 1，各有一个名为 `app` 的 target，alt-setting 为 0，各有一个位于 `0x08020000` 的 element。后缀中的 VID:PID 均为 `12D1:1093`，bcdDFU 为 `0x011A`。对末尾四字节之前的数据计算 `zlib.crc32(data) ^ 0xffffffff`，与文件内小端 CRC 一致，分别为 `0xFBCCC50E`、`0x331ACC95`。同一 USB 标识对应两个产品，因此判断型号还要看设备版本和镜像内容。

两份镜像的 element 均从文件偏移 `0x125` 开始，开头字符串均为 `VR_WalleX`，各自的内置版本位于 `0x14B`。CV10 镜像还含 `CV10_Upgrade`（`0xB1321`）及 `HUAWEI GLASS CV10`（`0xC1DA5`），另一份含 `AV02_Upgrade`（`0x51D49`）。这些偏移可用于在二进制查看器中核对，不依赖文件名。

## 程序与既有运行记录

用 Windows .NET Framework 的 ReflectionOnlyLoadFrom 只读解析升级器的 IL，通过元数据 token 还原方法调用和字符串，又检查了原生 DLL 的 PE 导出表。没有启动升级器。结果可在以下入口复核。

1. `HelmetManager.GetHelmetVersion` 经 `GetHelmetInfo` 发送以回车结尾的 `AT^SWVER`，解析 `MAINVER:` 行。`Upgrader.AutoLoadDfuFile` 按 `GetHelmetType` 结果在两份内置镜像中选择，再调用 `NeedUpgradeByCheckVersion`。程序集包含 `AV02C00B`、`CV10AC` 两种头显版本前缀。
2. `GetWallexDfuVersionCode` 解析 `C00B` 后的数字，`GetHallidayDfuVersionCode` 解析四段数字版本。`HidConnectState.dll` 导出普通模式识别、DFU 识别、通信检查和进入升级模式四个入口。随附的 `STtube.inf` 将 `12D1:1093` 标为华为 DFU 设备。
3. `UpgradeProcess.StartUpgrade` 将选定文件交给 `DfuSeCommandNew.exe`，等待进程结束、检查返回码、检测头显连接，再进入退出 DFU 流程。随包 PDF 第 1、6 页说明工具支持两代头显，升级中断后可能需要手动选对头显型号。
4. 已有 `CSharp_log-2026-11-25.txt` 记录了本机的一次成功升级。13:04:40，程序从 PCUI 串口收到 `CV10AC10.0.1.349`，自动选中 `halliday.dfu`，读出 `10.0.1.357`。随后通过 HID 请求进入 DFU，13:04:48 检出 DFU，13:05:59 写入子进程返回 0，13:06:03 退出 DFU 成功。日志没有升级后重读的 `MAINVER` 或线缆版本。

## 能从现有证据获得的线缆信息

在 CV10 镜像中，`AT^CABLEINFO?` 位于文件偏移 `0xC1EC1`，`AT^CABLESN?` 位于 `0xC2C39`，另有 `uvdm_cable_info_data_manage`（`0xBDCE5`）、`equip_get_cable_info`、`^CABLEINFO=` 等字符串。这提示可以在**头显的 PCUI 端口**进一步验证查询，通过头显记录线的型号或版本。尚未观察到这些查询的真实响应，也未确认返回字段的编码。单线接电脑时实际枚举为 `2109:0105`，可经 WinUSB 检查 PD 控制器。头显固件中的 `update.bin` 文件名也无法确定线缆载荷。

`华为vr glass问题汇总与解答.xlsx` 首张表 E2 指出，线单独插入手机时可查看版本。作者将 `9.53.6` 记为当时最新，并转述其他用户关于 `9.52` 以上可用的反馈。可据此向工作正常的线缆持有人收集同一硬件版本、手机弹窗版本和读取方式，核验可导出的镜像是否含设备专属序列号或校准区。该表没有提供厂商版本矩阵、固件文件或写入协议。

另用 innoextract 1.9 离线读取 PC VR 助手 3DoF、6DoF 两个安装包的成员清单，均未发现有明确线缆固件标识的文件。6DoF 包的 `FirmwareUpdate.xml` 展示定位器与左右手柄，中文资源称之为“定位交互套件”。`HwVRGlassLite-Setup-1.5.0.exe` 的安装格式未被所用解析器识别，内部资源尚待核实。上述检查不能排除嵌入程序、运行时下载或另行分发的线缆固件。[innoextract 项目](https://constexpr.org/innoextract/)
