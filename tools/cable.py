"""Inspect a CV10 cable or read its VL105 PD image over Windows WinUSB."""
import argparse
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import struct
import sys
import tempfile
import time
from uuid import NAMESPACE_DNS, UUID, uuid5

VID_PID = (0x2109, 0x0105)
IMAGE_SIZE = 0xC000
HEADER = 0x1003
TRANSFER_SIZE = 32
CV10_RUNTIME_VERSIONS = ('0c094906', '0c095206')
CHARGER_MODELS = {0x0d: 'RT9471', 0x0e: 'RT9471D'}
MAX_CUSTOM_REGISTERS = 64


def crc16_usb(data):
    value = 0xFFFF
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0xA001 if value & 1 else 0)
    return value ^ 0xFFFF


def inspect_image(data):
    if data.startswith(b'DfuSe'):
        raise ValueError('DfuSe package supplied. The VL105 requires a raw PD image.')
    if len(data) != IMAGE_SIZE:
        raise ValueError(f'Expected a {IMAGE_SIZE}-byte VL105 PD image, got {len(data)}')
    version = data[HEADER:HEADER + 4]
    ids = struct.unpack_from('<HH', data, HEADER + 4)
    if version[0] >= 0xA0 or version[0] & 0x0F != 0x0C:
        raise ValueError(f'Header tag {version[0]:02x} does not identify VL105')
    stored_crc, = struct.unpack_from('<H', data, len(data) - 2)
    actual_crc = crc16_usb(data[:-2])
    if stored_crc != actual_crc:
        raise ValueError(f'PD CRC mismatch: stored {stored_crc:04x}, computed {actual_crc:04x}')
    return dict(bytes=len(data), version_raw=version.hex(), header_vid_pid='%04x:%04x' % ids,
                crc16_usb=f'{actual_crc:04x}', sha256=hashlib.sha256(data).hexdigest())


def format_version(raw):
    tag, major, minor, patch = bytes.fromhex(raw)
    return f'{tag:X}{major:X}.{minor:X}.{patch:X}'


class Setup(ctypes.Structure):
    _pack_ = 1
    _fields_ = [('bmRequestType', ctypes.c_ubyte), ('bRequest', ctypes.c_ubyte),
                ('wValue', ctypes.c_uint16), ('wIndex', ctypes.c_uint16),
                ('wLength', ctypes.c_uint16)]


def check(ok):
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())


def cable_path():
    cfg = ctypes.WinDLL('cfgmgr32')
    # GUID_DEVINTERFACE_USB_DEVICE, using only present interfaces
    guid = ctypes.create_string_buffer(UUID('a5dcbf10-6530-11d2-901f-00c04fb951ed').bytes_le)
    size = wintypes.ULONG()
    result = cfg.CM_Get_Device_Interface_List_SizeW(ctypes.byref(size), guid, None, 0)
    if result:
        raise RuntimeError(f'CM_Get_Device_Interface_List_SizeW: {result}')
    paths = ctypes.create_unicode_buffer(size.value)
    result = cfg.CM_Get_Device_Interface_ListW(guid, None, paths, size.value, 0)
    if result:
        raise RuntimeError(f'CM_Get_Device_Interface_ListW: {result}')
    matches = [p for p in paths[:].split('\0') if p.lower().startswith(r'\\?\usb#vid_2109&pid_0105#')]
    if len(matches) != 1:
        raise ValueError(f'Expected exactly one 2109:0105 cable, found {len(matches)}')
    return matches[0]


@contextmanager
def cable_reader(*, maintenance=False):
    if os.name != 'nt':
        raise ValueError('Live USB inspection requires Windows with the cable WinUSB driver')
    path = cable_path()
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    usb = ctypes.WinDLL('winusb', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    handle = kernel.CreateFileW(path, 0xc0000000, 3, None, 3, 0x40000000, None)
    check(handle != wintypes.HANDLE(-1).value)
    interface = wintypes.HANDLE()
    try:
        check(usb.WinUsb_Initialize(wintypes.HANDLE(handle), ctypes.byref(interface)))
        try:
            def read(request, value, index, length, *, descriptor=False):
                payload = ctypes.create_string_buffer(length)
                count = wintypes.ULONG()
                packet = Setup(0x80 if descriptor else 0xC0, request, value, index, length)
                check(usb.WinUsb_ControlTransfer(interface, packet, payload, length,
                                                 ctypes.byref(count), None))
                if not descriptor and count.value != length:
                    raise ValueError(f'Short USB response: {count.value}/{length}')
                return payload.raw[:count.value]
            def send(request, value=0, data=b'', *, index=0):
                count = wintypes.ULONG()
                buffer = ctypes.create_string_buffer(data) if data else None
                packet = Setup(0x40, request, value, index, len(data))
                check(usb.WinUsb_ControlTransfer(interface, packet, buffer, len(data),
                                                 ctypes.byref(count), None))
                if count.value != len(data):
                    raise ValueError('Incomplete USB maintenance request')
            yield (read, send) if maintenance else read
        finally:
            usb.WinUsb_Free(interface)
    finally:
        kernel.CloseHandle(wintypes.HANDLE(handle))


def probe(read):
    def descriptor(kind, index, length, language=0):
        return read(6, kind << 8 | index, language, length, descriptor=True)
    device = descriptor(1, 0, 18)
    if len(device) != 18 or struct.unpack_from('<HH', device, 8) != VID_PID or device[4] != 0x11:
        raise ValueError('USB descriptor does not identify a 2109:0105 Billboard device')
    languages = descriptor(3, 0, 255)
    language, = struct.unpack_from('<H', languages, 2)

    def usb_string(index):
        value = descriptor(3, index, 255, language)
        return value[2:].decode('utf-16le').strip()
    bos_header = descriptor(15, 0, 5)
    total, = struct.unpack_from('<H', bos_header, 2)
    bos = descriptor(15, 0, total)
    if len(bos) != total:
        raise ValueError('Incomplete BOS descriptor')
    version = read(0xe2, 1, 0, 4)
    mode = read(0xe0, 0xf701, 0, 1)[0]
    return dict(vid_pid='2109:0105', bcd_device=f'{int.from_bytes(device[12:14], "little"):04x}',
                manufacturer=usb_string(device[14]), product=usb_string(device[15]),
                bos=bos.hex(), version_raw=version.hex(),
                mode='runtime' if mode & 0x80 else 'ROM')


def read_flash(read, address, length):
    # fwupd's FuVliPdDevice SPI READ_DATA using the standard CFI READ opcode.
    return read(0xc4, ((address & 0xff) << 8) | 0x03, address >> 8, length)


def dump_native(read, info):
    version = bytes.fromhex(info['version_raw'])
    if version[0] >= 0xa0 or version[0] & 0x0f != 0x0c:
        raise ValueError('Unexpected live firmware tag for VL105')
    try:
        header = read_flash(read, HEADER, 8)
    except OSError as error:
        raise ValueError(f'Cable refused the SPI header read in {info["mode"]} mode: {error}') from error
    if header[:4] != version:
        raise ValueError(f'PD image header {header.hex()} does not match running version')
    def read_once():
        return b''.join(read_flash(read, address, TRANSFER_SIZE)
                        for address in range(0, IMAGE_SIZE, TRANSFER_SIZE))
    first = read_once()
    second = read_once()
    if first != second or first[HEADER:HEADER + 8] != header:
        raise ValueError('Two independent flash reads or the initial header differ')
    return first


def read_register(read, address):
    if not 0 <= address <= 0xffff:
        raise ValueError('VL105 寄存器地址必须在 0000–FFFF 内')
    return read(0xe0, ((address & 0xff) << 8) | 1, address >> 8, 1)[0]


def verify_xdata_addressing(read):
    # The handler records bRequest and wIndex before reading the requested byte.
    if read_register(read, 0x2cf1) != 0xe0 or read_register(read, 0x2cf9) != 0x2c:
        raise ValueError('未能验证 VL105 的 16 位寄存器寻址')


def battery_status(read, *, info=None):
    if info is None:
        info = probe(read)
    if info['mode'] != 'runtime' or info['version_raw'] not in CV10_RUNTIME_VERSIONS:
        raise ValueError('电池缓存布局仅在 C9.49.6 和 C9.52.6 运行态下已确认')
    verify_xdata_addressing(read)
    level = read_register(read, 0x2dfe)
    for _ in range(3):
        high = read_register(read, 0x2e02)
        low = read_register(read, 0x2e01)
        if high == read_register(read, 0x2e02):
            break
    else:
        raise ValueError('Temperature changed during all three reads')
    raw = (high << 8) | low
    port_status = read_register(read, 0x2dff)
    charger_info = read_register(read, 0x2e00)
    # Include the reset bit in the key so asserted or invalid INFO values stay unknown.
    charger_id = charger_info >> 3
    return dict(version_raw=info['version_raw'], level_raw=level,
                level_percent=level if level <= 100 else None,
                temperature_raw=raw,
                temperature_c=(raw - 2731) / 10 if raw not in (0, 0xffff) else None,
                port_status_raw=port_status, charger_info_raw=charger_info,
                charger_model=CHARGER_MODELS.get(charger_id))


# Chip registers come from fwupd and the two CV10 application images.
CHIP_REGISTERS = (
    ('芯片与 GPIO', 0x0003, 'GPIO A 控制', '位 3 用于固件端口切换，板级信号待确认'),
    ('芯片与 GPIO', 0x0009, '控制标志', '低电量与保护处理路径更改位 2、3'),
    ('芯片与 GPIO', 0x000f, '控制标志', '保护处理分支会清位 3'),
    ('芯片与 GPIO', 0x0015, 'UART-Rx 配置', 'fwupd 维护流程调整的 UART-Rx 配置'),
    ('芯片与 GPIO', 0x0018, '芯片识别', '高四位 A 对应 VL105'),
    ('芯片与 GPIO', 0x0019, 'Watch Mode 配置', 'fwupd 维护流程调整的调试配置'),
    ('芯片与 GPIO', 0x001c, 'GPIO 方向控制', 'fwupd 维护流程使用的配置原值'),
    ('芯片与 GPIO', 0x009c, '工程 ID 高字节', '芯片系列备用 ID 地址，保留原值'),
    ('芯片与 GPIO', 0x009d, '工程 ID 低字节', '芯片系列备用 ID 地址，保留原值'),
    ('芯片与 GPIO', 0x00f7, '执行模式', '位 7 指示应用运行态'),
    ('芯片与 GPIO', 0x011b, '端口 2 控制', '固件会在端口切换时更改位 2'),
)

RUNTIME_REGISTERS = (
    ('电池与供电', 0x2dfe, '电量缓存', '来自电量计 55:2C'),
    ('电池与供电', 0x2dff, 'VL105 端口事件位', '位 1 曾随辅助电源变化'),
    ('电池与供电', 0x2e00, '充电芯片身份缓存', '来自 RT9471 INFO 53:0B'),
    ('电池与供电', 0x2e01, '温度缓存低字节', '与 2E02 组成温度原值'),
    ('电池与供电', 0x2e02, '温度缓存高字节', '0000 和 FFFF 为无效温度'),
    ('DP 与 HPD', 0x2943, 'DP 状态低字节', '用于构造 DP Status / Attention 数据'),
    ('DP 与 HPD', 0x2944, 'DP 状态次低字节', '用于构造 DP Status / Attention 数据'),
    ('DP 与 HPD', 0x2948, '上次 HPD 处理状态', '上一次保存的事件状态'),
    ('DP 与 HPD', 0x2949, '当前 HPD 处理状态', '本轮固件事件状态'),
    ('PD 与端口', 0x2beb, '端口控制触发标志', '多个控制分支共用'),
    ('USB 诊断', 0x2cf0, 'USB wValue 低字节回显', '读取时回显本次 E0 查询'),
    ('USB 诊断', 0x2cf1, 'USB 请求号回显', '读取时回显本次 E0 查询'),
    ('USB 诊断', 0x2cf8, 'USB wValue 高字节回显', '读取时回显本次 E0 查询'),
    ('USB 诊断', 0x2cf9, 'USB wIndex 低字节回显', '核对高位地址寻址'),
)

# Address pairs are ordered C9.49.6, C9.52.6.
VERSIONED_REGISTERS = (
    ('电池与供电', (0x2a5c, 0x2a5d), 'I²C 状态共用缓存', '55:32、53:11、53:12 可写入此处'),
    ('电池与供电', (0x2aa3, 0x2aa4), '线控保护状态', 'A1 是固件会处理的保护状态'),
    ('电池与供电', (0x2b3b, 0x2b3c), '电量阈值控制状态', '参与电量 30 阈值附近的端口处理'),
    ('DP 与 HPD', (0x2a5b, 0x2a5c), 'Attention 状态暂存', '部分 Attention 分支用于生成状态字'),
    ('DP 与 HPD', (0x2b30, 0x2b31), '待处理的 HPD 操作', '1 为 IRQ、2 为拉高、3 为拉低'),
    ('PD 与端口', (0x2a5e, 0x2a5f), '端口控制状态', '含电量阈值分支写入的状态'),
    ('PD 与端口', (0x2a9f, 0x2aa0), '端口切换状态机', '跟踪共同的 1–6 状态切换'),
    ('PD 与端口', (0x2aa5, 0x2aa6), '线缆身份交换序号', '线缆序列号和信息两个响应分支'),
    ('PD 与端口', (0x2b3d, 0x2b3e), 'PD 发现路径状态', 'Discover SVIDs / Discover Modes 构帧路径使用'),
    *(
        ('PD 与端口', (0x2b4f + i, 0x2b50 + i), f'VDM 暂存字节 {i}', '首个 VDO 的固件构帧暂存')
        for i in range(4)
    ),
)

REGISTER_BITS = {
    0x0003: ((3, '位3'),),
    0x0009: ((2, '位2'), (3, '位3')),
    0x000f: ((3, '位3'),),
    0x011b: ((2, '位2'),),
    0x2943: ((7, 'HPD 缓存'),),
    0x2944: ((0, 'HPD IRQ 缓存'),),
    0x2dff: ((1, '端口1事件位'), (2, '端口2事件位')),
}


def parse_register_addresses(query):
    if not query.strip():
        return ()
    addresses = set()
    query = re.sub(r'\s*-\s*', '-', query.strip())
    for item in re.split(r'[\s,，;；]+', query):
        match = re.fullmatch(r'(?:0x)?([\da-f]{1,4})(?:-(?:0x)?([\da-f]{1,4}))?',
                             item, re.IGNORECASE | re.ASCII)
        if match is None:
            raise ValueError(f'无效的十六进制地址或范围：{item}')
        start = int(match[1], 16)
        end = int(match[2] or match[1], 16)
        if end < start:
            raise ValueError(f'结束地址必须大于或等于起始地址：{item}')
        if end - start >= MAX_CUSTOM_REGISTERS:
            raise ValueError(f'每次最多读取 {MAX_CUSTOM_REGISTERS} 个手动地址')
        addresses.update(range(start, end + 1))
        if len(addresses) > MAX_CUSTOM_REGISTERS:
            raise ValueError(f'每次最多读取 {MAX_CUSTOM_REGISTERS} 个手动地址')
    return tuple(sorted(addresses))


def register_interpretation(address, value):
    if address == 0x00f7:
        return '运行态' if value & 0x80 else 'ROM'
    if address in (0x2948, 0x2949):
        return {1: 'HPD 拉低', 2: 'HPD 拉高', 3: 'HPD IRQ'}.get(value, '')
    if address == 0x2dfe:
        return f'{value}%' if value <= 100 else '电量未知'
    if address == 0x2e00:
        model = CHARGER_MODELS.get(value >> 3)
        return f'{model} Rev {value & 7}' if model else '未知充电芯片型号'
    return ' · '.join(f'{label}={(value >> bit) & 1}'
                      for bit, label in REGISTER_BITS.get(address, ()))


def register_snapshot(read, info, addresses=(), *, captured=None):
    cache = {address: (value, None) for address, value in (captured or {}).items()}

    def row(field, *, decode=True):
        group, address, name, note = field
        if address not in cache:
            try:
                cache[address] = (read_register(read, address), None)
            except (OSError, ValueError) as error:
                cache[address] = (None, str(error))
        raw, error = cache[address]
        return dict(group=group, address=address, name=name, raw=raw, error=error, note=note,
                    interpretation=register_interpretation(address, raw)
                    if decode and raw is not None else '')

    presets = [row(field) for field in CHIP_REGISTERS]
    by_address = {entry['address']: entry for entry in presets}
    chip = by_address[0x0018]['raw']
    is_vl105 = chip is not None and chip & 0xf0 == 0xa0
    layout_error = None
    if not is_vl105:
        layout_error = '未能确认芯片为 VL105'
    elif info['mode'] != 'runtime' or info['version_raw'] not in CV10_RUNTIME_VERSIONS:
        layout_error = '当前模式或固件版本的运行态地址布局待确认'
    else:
        try:
            verify_xdata_addressing(read)
        except (OSError, ValueError) as error:
            layout_error = str(error)

    if layout_error is None:
        index = CV10_RUNTIME_VERSIONS.index(info['version_raw'])
        layouts = [(group, offsets[index], name, note)
                   for group, offsets, name, note in VERSIONED_REGISTERS]
        if index == 1:
            layouts.append(('PD 与端口', 0x2a5b, '延迟脉冲状态', 'C9.52.6 的追加控制路径'))
        presets.extend(row(field) for field in (*RUNTIME_REGISTERS, *layouts))
        by_address.update((entry['address'], entry) for entry in presets)

    manual = []
    for address in addresses:
        entry = by_address.get(address)
        if entry is None:
            if not is_vl105:
                cache[address] = (None, layout_error)
            note = 'VL105 XDATA 原值' if layout_error is None else '当前固件的地址布局待确认'
            entry = row(('手动读取', address, '自定义地址', note), decode=False)
        manual.append(entry)
    return dict(presets=presets, manual=manual, layout_error=layout_error)


def wait_mode(path, runtime):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            if cable_path() == path:
                with cable_reader() as read:
                    if bool(read_register(read, 0xf7) & 0x80) == runtime:
                        return
        except (OSError, ValueError):
            pass
        time.sleep(0.25)
    raise RuntimeError(f'Cable did not enumerate in {"runtime" if runtime else "ROM"} mode')


def restart(send, request):
    try:
        send(request)
    except OSError as error:
        # A reset may disconnect USB before the status stage completes.
        if error.winerror not in (31, 121, 1167):
            raise


@contextmanager
def maintenance_session():
    path = cable_path()
    with cable_reader(maintenance=True) as (read, send):
        info = probe(read)
        if info['mode'] != 'runtime' or read_register(read, 0x18) & 0xf0 != 0xa0:
            raise ValueError('Expected a running VL105 before entering maintenance mode')
        # fwupd 2.1.9 VL105 detach sequence. Restore volatile GPIOs if detach fails.
        settings = [(0x15, 0x7f), (0x19, 0), (0x1c, 2),
                    (3, (read_register(read, 3) | 0x10) & 0xfe)]
        saved = []
        try:
            for address, value in settings:
                saved.append((address, read_register(read, address)))
                send(0xe0, (address << 8) | 2, bytes([value]))
            restart(send, 0xc0)
            wait_mode(path, False)
        except Exception:
            if cable_path() == path and read_register(read, 0xf7) & 0x80:
                for address, value in reversed(saved):
                    send(0xe0, (address << 8) | 2, bytes([value]))
            raise
    with cable_reader(maintenance=True) as (read, send):
        try:
            yield read, send, {**info, 'mode': 'ROM'}
        except RecoveryError:
            # A partially written image must not be started.
            raise
        except BaseException:
            restart(send, 0xb0)
            wait_mode(path, True)
            raise
        restart(send, 0xb0)
        wait_mode(path, True)


def fwupd_target(command, work):
    status = subprocess.run([*command, '--json', 'get-devices'], capture_output=True,
                            encoding='utf-8', errors='replace', cwd=work)
    if status.returncode:
        raise RuntimeError(f'fwupd enumeration failed: {status.stdout.strip()} {status.stderr.strip()}')
    devices = json.loads(status.stdout).get('Devices', [])
    expected = str(uuid5(NAMESPACE_DNS, r'USB\VID_2109&PID_0105'))
    matches = [d for d in devices if d.get('Plugin') == 'vli' and expected in d.get('Guid', [])]
    if len(matches) != 1:
        raise ValueError(f'Expected one 2109:0105 device recognized by the VLI plugin, found {len(matches)}')
    device_id = matches[0].get('DeviceId', '')
    if not re.fullmatch(r'[0-9a-f]{40}', device_id):
        raise ValueError('fwupd returned an invalid DeviceId')
    return device_id


def dump_fwupd(executable, work):
    command = [executable, '--plugins', 'vli']
    target = fwupd_target(command, work)
    images = []
    for attempt in (1, 2):
        path = work / f'read-{attempt}.bin'
        subprocess.run([*command, 'firmware-dump', str(path), target], cwd=work, check=True)
        images.append(path.read_bytes())
    if images[0] != images[1]:
        raise ValueError('The two independent fwupd dumps differ')
    return images[0]


def dump_maintenance():
    with maintenance_session() as (read, _, info):
        return dump_native(read, info)


def publish_dump(destination, image, metadata):
    destination = destination.resolve()
    with tempfile.TemporaryDirectory(dir=destination.parent) as staging:
        staged = Path(staging) / 'verified.bin'
        with staged.open('wb') as output:
            output.write(image)
            output.flush()
            os.fsync(output.fileno())
        # Publish exclusively only after both reads and the image CRC pass.
        if os.name == 'nt':
            os.rename(staged, destination)  # Windows refuses to replace an existing file.
        else:
            os.link(staged, destination)
    return dict(output=str(destination), independent_reads=2, **metadata)


def save_versioned_dump(directory, image):
    metadata = inspect_image(image)
    version = format_version(metadata['version_raw'])
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    return publish_dump(directory / f'CV10-cable-{version}-{timestamp}.bin', image, metadata)


def export(args):
    destination = args.file.resolve()
    if destination.exists():
        raise FileExistsError(destination)
    if args.fwupdtool:
        with tempfile.TemporaryDirectory(dir=destination.parent) as staging:
            image = dump_fwupd(args.fwupdtool, Path(staging))
    elif args.maintenance:
        image = dump_maintenance()
    else:
        with cable_reader() as read:
            image = dump_native(read, probe(read))
    return publish_dump(destination, image, inspect_image(image))


def install_cab(args):
    # Only pass the named, verified copy to fwupd. Raw donor images have no board metadata.
    if args.file.suffix.lower() != '.cab' or not re.fullmatch(r'[0-9a-fA-F]{64}', args.sha256):
        raise ValueError('An OEM .cab and its trusted SHA-256 are required')
    package = args.file.read_bytes()
    if not package.startswith(b'MSCF') or hashlib.sha256(package).hexdigest() != args.sha256.lower():
        raise ValueError('Invalid CAB signature or SHA-256 mismatch')
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        target = fwupd_target([args.fwupdmgr], work)
        staged = work / 'cable.cab'
        staged.write_bytes(package)
        subprocess.run([args.fwupdmgr, 'local-install', str(staged), target], cwd=work, check=True)
    return dict(device_id=target, package_sha256=args.sha256.lower(), fwupd_exit=0)


PD_OFFSET = 0x20000  # fwupd VL105 VliPdOffset
SECTOR_SIZE = 4096


class RecoveryError(RuntimeError):
    pass


def read_region(read, address, size):
    return b''.join(read_flash(read, address + offset, min(TRANSFER_SIZE, size - offset))
                    for offset in range(0, size, TRANSFER_SIZE))


def wait_flash(read):
    deadline = time.monotonic() + 5
    while read(0xc2, 5, 0, 1)[0] & 1:
        if time.monotonic() >= deadline:
            raise RuntimeError('Flash remained busy')
        time.sleep(0.005)


def program_sector(read, send, address, data):
    # VL105 SPI bridge, using the standard sector erase and page program opcodes.
    send(0xd4, 6)
    send(0xd2, 0x20, index=address >> 8)
    wait_flash(read)
    if read_region(read, address, SECTOR_SIZE) != b'\xff' * SECTOR_SIZE:
        raise ValueError(f'Sector erase verification failed at {address:#x}')
    for offset in range(0, SECTOR_SIZE, TRANSFER_SIZE):
        block = data[offset:offset + TRANSFER_SIZE]
        if block == b'\xff' * TRANSFER_SIZE:
            continue
        position = address + offset
        send(0xd4, 6)
        send(0xdc, ((position & 0xff) << 8) | 2, block, index=position >> 8)
        time.sleep(0.001)
        wait_flash(read)
    if read_region(read, address, SECTOR_SIZE) != data:
        raise ValueError(f'Sector write verification failed at {address:#x}')


def changed_sectors(image, backup):
    if image[HEADER + 4:HEADER + 8] != backup[HEADER + 4:HEADER + 8]:
        raise ValueError('Candidate and backup have different header VID/PID')
    return [offset for offset in range(0, IMAGE_SIZE, SECTOR_SIZE)
            if image[offset:offset + SECTOR_SIZE] != backup[offset:offset + SECTOR_SIZE]]


def prepare_upgrade(candidate_file, backup_directory):
    image = candidate_file.read_bytes()
    metadata = inspect_image(image)
    backup_directory.mkdir(parents=True, exist_ok=True)
    with maintenance_session() as (read, _, info):
        backup = dump_native(read, info)
        changed = changed_sectors(image, backup)
        if read_region(read, PD_OFFSET, IMAGE_SIZE) != backup:
            raise ValueError('The write region differs from the current firmware image')
    saved = save_versioned_dump(backup_directory, backup)
    return dict(candidate=metadata, backup=saved, differing_sectors=len(changed))


def flash_raw(args, *, expected_sha256=None, expected_backup_sha256=None):
    image = args.file.read_bytes()
    backup = args.backup.read_bytes()
    metadata = inspect_image(image)
    if expected_sha256 is not None and metadata['sha256'] != expected_sha256:
        raise ValueError('候选文件在预检后发生变化，请重新选择。')
    backup_metadata = inspect_image(backup)
    if expected_backup_sha256 is not None and backup_metadata['sha256'] != expected_backup_sha256:
        raise ValueError('自动备份在预检后发生变化，请重新开始烧录。')
    changed = changed_sectors(image, backup)
    with maintenance_session() as (read, send, info):
        if dump_native(read, info) != backup or read_region(read, PD_OFFSET, IMAGE_SIZE) != backup:
            raise ValueError('The running image and write region must both match the supplied backup')
        if changed and args.apply:
            if read(0xc2, 5, 0, 1)[0] != 0:
                raise ValueError('Unexpected SPI status before programming')
            gpio = read_register(read, 3)
            try:
                for address, value in ((0x15, 0x7f), (0x19, 0), (0x1c, 2), (3, gpio | 0x44)):
                    send(0xe0, (address << 8) | 2, bytes([value]))
                started = []
                try:
                    for offset in changed:
                        started.append(offset)
                        program_sector(read, send, PD_OFFSET + offset, image[offset:offset + SECTOR_SIZE])
                    if read_region(read, PD_OFFSET, IMAGE_SIZE) != image:
                        raise ValueError('Full image readback differs')
                except BaseException as failure:
                    try:
                        wait_flash(read)
                        for offset in reversed(started):
                            original = backup[offset:offset + SECTOR_SIZE]
                            if read_region(read, PD_OFFSET + offset, SECTOR_SIZE) != original:
                                program_sector(read, send, PD_OFFSET + offset, original)
                        if read_region(read, PD_OFFSET, IMAGE_SIZE) != backup:
                            raise ValueError('Restored image differs from backup')
                    except BaseException as recovery:
                        raise RecoveryError(f'Programming failed ({failure}); restoration failed '
                                            f'({recovery}). Reset was withheld.') from recovery
                    raise RuntimeError(f'Programming failed ({failure}); backup restored and verified') from failure
            finally:
                try:
                    send(0xe0, 0x0302, bytes([gpio]))
                except OSError as error:
                    raise RecoveryError(f'Could not restore programming GPIO: {error}. Reset was withheld.') from error
    with cable_reader() as read:
        running = probe(read)
    expected = image if args.apply else backup
    if running['mode'] != 'runtime' or running['version_raw'] != expected[HEADER:HEADER + 4].hex():
        raise ValueError(f'Unexpected device state after restart: {running}')
    return dict(candidate=metadata, differing_sectors=len(changed),
                programmed_sectors=len(changed) if args.apply else 0,
                runtime_version=running['version_raw'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('probe', help='read USB descriptors, version and execution mode')
    commands.add_parser('battery', help='read cached cable gauge values in normal Billboard mode')
    register_parser = commands.add_parser('registers', help='capture VL105 registers and optional addresses')
    register_parser.add_argument('addresses', nargs='*', help='hex addresses or inclusive ranges, e.g. 0003 2DFE-2E02')
    dump_parser = commands.add_parser('dump', help='read and verify the raw PD image twice')
    dump_parser.add_argument('file', type=Path)
    backend = dump_parser.add_mutually_exclusive_group()
    backend.add_argument('--fwupdtool', metavar='PATH', help='delegate mode changes and readback to fwupd')
    backend.add_argument('--maintenance', action='store_true', help='enter VL105 ROM, dump, and return to runtime')
    commands.add_parser('inspect', help='check an offline raw VL105 PD image').add_argument('file', type=Path)
    install = commands.add_parser('flash', help='install a board-matched OEM CAB using fwupdmgr')
    install.add_argument('file', type=Path)
    install.add_argument('--sha256', required=True, help='expected digest from the package provider')
    install.add_argument('--fwupdmgr', default='fwupdmgr', help='executable on PATH or absolute path')
    raw = commands.add_parser('flash-raw', help='compare or program a board-matched raw VL105 PD image')
    raw.add_argument('file', type=Path)
    raw.add_argument('--backup', type=Path, required=True, help='verified dump of the current device')
    raw.add_argument('--apply', action='store_true', help='program changed sectors after comparison')
    args = parser.parse_args()
    if args.command == 'inspect':
        result = inspect_image(args.file.read_bytes())
    elif args.command == 'dump':
        result = export(args)
    elif args.command == 'flash':
        result = install_cab(args)
    elif args.command == 'flash-raw':
        result = flash_raw(args)
    elif args.command == 'registers':
        addresses = parse_register_addresses(' '.join(args.addresses))
        with cable_reader() as read:
            info = probe(read)
            result = dict(**info, registers=register_snapshot(read, info, addresses))
    else:
        with cable_reader() as read:
            result = battery_status(read) if args.command == 'battery' else probe(read)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, struct.error, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
