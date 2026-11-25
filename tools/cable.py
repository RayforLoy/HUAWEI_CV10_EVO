"""Inspect a CV10 cable or read its VL105 PD image over Windows WinUSB."""
import argparse
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import struct
import sys
import tempfile
from uuid import NAMESPACE_DNS, UUID, uuid5

VID_PID = (0x2109, 0x0105)
IMAGE_SIZE = 0xC000
HEADER = 0x1003
TRANSFER_SIZE = 32


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
def cable_reader():
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
            yield read
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


def export(args):
    destination = args.file.resolve()
    if destination.exists():
        raise FileExistsError(destination)
    with tempfile.TemporaryDirectory(dir=destination.parent) as staging:
        work = Path(staging)
        if args.fwupdtool:
            image = dump_fwupd(args.fwupdtool, work)
        else:
            with cable_reader() as read:
                image = dump_native(read, probe(read))
        metadata = inspect_image(image)
        staged = work / 'verified.bin'
        staged.write_bytes(image)
        # Publish exclusively only after both reads and the image CRC pass.
        os.link(staged, destination)
    return dict(output=str(destination), independent_reads=2, **metadata)


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('probe', help='read USB descriptors, version and execution mode')
    dump_parser = commands.add_parser('dump', help='read and verify the raw PD image twice')
    dump_parser.add_argument('file', type=Path)
    dump_parser.add_argument('--fwupdtool', metavar='PATH', help='delegate mode changes and readback to fwupd')
    commands.add_parser('inspect', help='check an offline raw VL105 PD image').add_argument('file', type=Path)
    install = commands.add_parser('flash', help='install a board-matched OEM CAB using fwupdmgr')
    install.add_argument('file', type=Path)
    install.add_argument('--sha256', required=True, help='expected digest from the package provider')
    install.add_argument('--fwupdmgr', default='fwupdmgr', help='executable on PATH or absolute path')
    args = parser.parse_args()
    if args.command == 'inspect':
        result = inspect_image(args.file.read_bytes())
    elif args.command == 'dump':
        result = export(args)
    elif args.command == 'flash':
        result = install_cab(args)
    else:
        with cable_reader() as read:
            result = probe(read)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, struct.error, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
