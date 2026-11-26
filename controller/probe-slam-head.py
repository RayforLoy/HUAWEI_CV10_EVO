# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise the pinned stock PC head SLAM ABI with synthetic input and no hardware."""

import argparse
import ctypes as c
import hashlib
import os
from pathlib import Path
import shutil
import struct
import tempfile
import time


DLL_HASHES = {
    "arvr_slam.dll": "6d89d332acfe86f9a9a3309a913de6d6cb8f0da2f49b46f60b96a07599283a7d",
    "VR6DOF.dll": "0e5a3ce7be318b45165e4a7837192a18b31fbdac8e658974f6210904d9ce930a",
}
CONFIG_VALID = b"HSDK_CONFIG_MANAGER_IMPL_GET_CHECK_VALID"
CONFIG_PARAMS = b"HSDK_CONFIG_MANAGER_IMPL_GET_SLAM_PARAMS"
IMAGE_FORMAT = b"fmt:yuv@res:480p@rot:0"
FRAME_FORMAT = IMAGE_FORMAT + b"@fmt:preyuv@res:480p@rot:0@fmt:feature@fmt:depth@rot:0"
INPUT_FORMATS = IMAGE_FORMAT + b";fmt:preyuv@res:480p@rot:0;fmt:feature;fmt:depth@rot:0;fmt:imu"
OUTPUT_FORMATS = (b"fmt:pose@org:slam;fmt:predictpose@org:slam;fmt:cameraintrin@org:slam;"
                  b"fmt:pointcloud@org:slam;fmt:anchor@org:slam@type:update")
POSE_FORMAT = b"fmt:pose@org:slam"


class AlgorithmData(c.Structure):
    _fields_ = [
        ("format", c.c_char * 0x100),
        ("size", c.c_uint64),
        ("timestamp", c.c_uint64),
        ("payload", c.c_void_p),
        ("owner", c.c_void_p),
    ]


class ImuData(c.Structure):
    _fields_ = [
        ("kind", c.c_uint32),
        ("seconds", c.c_double),
        ("axes", c.c_float * 3),
    ]


def check_zero(operation, result):
    if result != 0:
        raise RuntimeError(f"{operation} returned {result}")
    print(f"{operation}={result}", flush=True)


def feed_samples(table, session, lifetime):
    packet_call = c.WINFUNCTYPE(c.c_int, c.c_void_p, c.POINTER(AlgorithmData))
    push = packet_call(c.c_void_p.from_address(table + 0x70).value)
    get = packet_call(c.c_void_p.from_address(table + 0x78).value)
    for ns in (1_000_000_000, 1_005_000_000, 1_010_000_000):
        for kind in (0, 1):
            axes = (c.c_float * 3)(0, 0, 9.8 if kind == 0 else 0)
            payload = ImuData(kind, ns / 1e9, axes)
            packet = AlgorithmData(b"fmt:imu", c.sizeof(payload), ns, c.addressof(payload), None)
            lifetime.extend((payload, packet))
            check_zero(f"push IMU {ns} {kind}", push(session, c.byref(packet)))

    for index in range(2):
        ns = 1_010_000_000 + index * 66_666_666
        frame = c.create_string_buffer(0x78)
        struct.pack_into("<III", frame, 0, 3, 2, 0x101)
        for camera in range(2):
            pixels = c.create_string_buffer(640 * 480)
            image = c.create_string_buffer(0x60)
            struct.pack_into("<9I", image, 0, len(pixels) + len(image), 640, 480, 640,
                             index + 1, 0, 1, 0, 0)
            struct.pack_into("<d", image, 0x28, ns / 1e9)
            struct.pack_into("<d", image, 0x38, 0.004)
            struct.pack_into("<Q", image, 0x48, c.addressof(pixels))
            leaf = AlgorithmData(IMAGE_FORMAT, len(image), ns, c.addressof(image), None)
            struct.pack_into("<Q", frame, 0x10 + camera * 8, c.addressof(leaf))
            lifetime.extend((pixels, image, leaf))
        packet = AlgorithmData(FRAME_FORMAT, len(frame), ns, c.addressof(frame), None)
        lifetime.extend((frame, packet))
        check_zero(f"push blank stereo {index + 1}", push(session, c.byref(packet)))

    time.sleep(0.1)
    pose = c.create_string_buffer(0x38)
    packet = AlgorithmData(POSE_FORMAT, len(pose), 0, c.addressof(pose), None)
    code = get(session, c.byref(packet))
    print(f"pose with blank frames: {code} ({bytes(pose).hex()})", flush=True)
    if code != -1 or any(pose.raw):
        raise RuntimeError("Expected no pose from blank stereo and synthetic IMU")


def probe(vendor):
    with os.add_dll_directory(str(vendor)):
        slam = c.WinDLL(str(vendor / "arvr_slam.dll"))
        wrapper = c.WinDLL(str(vendor / "VR6DOF.dll"))

        # These RVAs are used only for the verified stock PC wrapper.
        get_config = c.WINFUNCTYPE(c.c_void_p)(wrapper._handle + 0x2F6A0)
        init_config = c.WINFUNCTYPE(None, c.c_void_p)(wrapper._handle + 0x2FEF0)
        read_config = c.WINFUNCTYPE(c.c_int64, c.c_void_p, c.c_char_p, c.c_size_t, c.c_void_p)(
            wrapper._handle + 0x310D0)
        config = get_config()
        if not config:
            raise RuntimeError("No stock configuration object")
        init_config(config)
        valid = c.c_uint8()
        if read_config(config, CONFIG_VALID, 1, c.byref(valid)) != 1 or valid.value != 1:
            raise RuntimeError("Stock XML did not validate")
        parameters = c.create_string_buffer(0x840)
        if read_config(config, CONFIG_PARAMS, len(parameters), parameters) != len(parameters):
            raise RuntimeError("Stock SLAM calibration has an unexpected size")

        slam.GetSlamInterface.argtypes = []
        slam.GetSlamInterface.restype = c.c_void_p
        table = slam.GetSlamInterface()
        if (not table or c.c_uint64.from_address(table).value != 0x00000001ABCD2012 or
                c.string_at(c.c_void_p.from_address(table + 8).value) != b"SLAM"):
            raise RuntimeError("Unexpected SLAM function table")
        print(f"SLAM table RVA={table - slam._handle:#x}, tag=00000001abcd2012", flush=True)

        def slot(offset, result, *arguments):
            address = c.c_void_p.from_address(table + offset).value
            if not address:
                raise RuntimeError(f"Missing SLAM slot {offset:#x}")
            return c.WINFUNCTYPE(result, *arguments)(address)

        config_call = c.WINFUNCTYPE(c.c_int64, c.c_void_p, c.c_char_p, c.c_size_t, c.c_void_p)
        data_call = c.WINFUNCTYPE(c.c_int, c.c_void_p, c.c_void_p)

        @config_call
        def set_value(_context, key, size, _buffer):
            print(f"set {key.decode()} ({size} bytes)", flush=True)
            return 0

        @config_call
        def get_value(context, key, size, buffer):
            print(f"get {key.decode()} ({size} bytes)", flush=True)
            return read_config(context, key, size, buffer)

        @data_call
        def keep_data(_context, _packet):
            # feed_samples keeps all allocated packets alive through stop and deinit.
            return 0

        class Callbacks(c.Structure):
            _fields_ = [("context", c.c_void_p), ("set", config_call), ("get", config_call),
                        ("retain", data_call), ("release", data_call), ("input", data_call), ("output", data_call)]

        callbacks = Callbacks(config, set_value, get_value, keep_data, keep_data, keep_data, keep_data)
        register = slot(0xA0, None, c.POINTER(Callbacks))
        unregister = slot(0xA8, None)
        create = slot(0x20, c.c_void_p, c.c_char_p, c.c_char_p)
        destroy = slot(0x28, None, c.c_void_p)
        init = slot(0x30, c.c_int, c.c_void_p)
        start = slot(0x38, c.c_int, c.c_void_p)
        stop = slot(0x50, c.c_int, c.c_void_p)
        deinit = slot(0x58, c.c_int, c.c_void_p)
        lifetime = []
        register(c.byref(callbacks))
        try:
            session = create(INPUT_FORMATS, OUTPUT_FORMATS)
            if not session:
                raise RuntimeError("SLAM creation failed")
            print("create succeeded", flush=True)
            try:
                check_zero("init", init(session))
                try:
                    check_zero("start", start(session))
                    try:
                        feed_samples(table, session, lifetime)
                    finally:
                        check_zero("stop", stop(session))
                finally:
                    check_zero("deinit", deinit(session))
            finally:
                destroy(session)
        finally:
            unregister()
        print("destroyed session and unregistered callbacks", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stock_directory", type=Path, help="Extracted OEM PC assistant win64 directory")
    args = parser.parse_args()
    if os.name != "nt" or c.sizeof(c.c_void_p) != 8:
        raise SystemExit("This probe requires 64-bit Windows Python.")
    if c.sizeof(AlgorithmData) != 0x120 or c.sizeof(ImuData) != 0x20:
        raise SystemExit("Unexpected packet alignment.")
    vendor = args.stock_directory.resolve(strict=True)
    for name, expected in DLL_HASHES.items():
        actual = hashlib.sha256((vendor / name).read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit(f"Unexpected {name} version: {actual}")
    original_directory = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="cv10-head-slam-") as scratch:
        shutil.copyfile(vendor / "vrglass-handler-default.xml", Path(scratch) / "vrglass-handler.xml")
        os.chdir(scratch)
        try:
            probe(vendor)
        finally:
            os.chdir(original_directory)


if __name__ == "__main__":
    main()
