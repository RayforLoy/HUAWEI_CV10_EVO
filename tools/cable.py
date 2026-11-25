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
import time
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
    return read(0xe0, (address << 8) | 1, 0, 1)[0]


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


def export(args):
    destination = args.file.resolve()
    if destination.exists():
        raise FileExistsError(destination)
    with tempfile.TemporaryDirectory(dir=destination.parent) as staging:
        work = Path(staging)
        if args.fwupdtool:
            image = dump_fwupd(args.fwupdtool, work)
        elif args.maintenance:
            with maintenance_session() as (read, _, info):
                image = dump_native(read, info)
        else:
            with cable_reader() as read:
                image = dump_native(read, probe(read))
        metadata = inspect_image(image)
        staged = work / 'verified.bin'
        staged.write_bytes(image)
        # Publish exclusively only after both reads and the image CRC pass.
        if os.name == 'nt':
            os.rename(staged, destination)  # Windows refuses to replace an existing file.
        else:
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


def flash_raw(args, *, expected_sha256=None):
    image = args.file.read_bytes()
    backup = args.backup.read_bytes()
    metadata = inspect_image(image)
    if expected_sha256 is not None and metadata['sha256'] != expected_sha256:
        raise ValueError('候选文件在预检后发生变化，请重新选择。')
    inspect_image(backup)
    if image[HEADER + 4:HEADER + 8] != backup[HEADER + 4:HEADER + 8]:
        raise ValueError('Candidate and backup have different header VID/PID')
    with maintenance_session() as (read, send, info):
        if dump_native(read, info) != backup or read_region(read, PD_OFFSET, IMAGE_SIZE) != backup:
            raise ValueError('The running image and write region must both match the supplied backup')
        changed = [offset for offset in range(0, IMAGE_SIZE, SECTOR_SIZE)
                   if image[offset:offset + SECTOR_SIZE] != backup[offset:offset + SECTOR_SIZE]]
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
    else:
        with cable_reader() as read:
            result = probe(read)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, struct.error, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
