# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise the stock PC head SLAM and hand tracking ABIs without hardware."""

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
    "HandlerDLL.dll": "0269d56389e7c107cb46f668ca48e789befc07fc236c04ed00867eab0ef98451",
    "VR6DOF.dll": "0e5a3ce7be318b45165e4a7837192a18b31fbdac8e658974f6210904d9ce930a",
}
CONFIG_VALID = b"HSDK_CONFIG_MANAGER_IMPL_GET_CHECK_VALID"
CONFIG_PARAMS = b"HSDK_CONFIG_MANAGER_IMPL_GET_SLAM_PARAMS"
HAND_CONFIG = b"HSDK_CONFIG_MANAGER_IMPL_GET_VR_6_DOF_HANDLER_CONFIG"
IMAGE_FORMAT = b"fmt:yuv@res:480p@rot:0"
FRAME_FORMAT = IMAGE_FORMAT + b"@fmt:preyuv@res:480p@rot:0@fmt:feature@fmt:depth@rot:0"
INPUT_FORMATS = IMAGE_FORMAT + b";fmt:preyuv@res:480p@rot:0;fmt:feature;fmt:depth@rot:0;fmt:imu"
OUTPUT_FORMATS = (b"fmt:pose@org:slam;fmt:predictpose@org:slam;fmt:cameraintrin@org:slam;"
                  b"fmt:pointcloud@org:slam;fmt:anchor@org:slam@type:update")
POSE_FORMAT = b"fmt:pose@org:slam"
HAND_INPUT_FORMATS = IMAGE_FORMAT + b";fmt:imu@org:helmet;fmt:imu@org:controller;" + POSE_FORMAT
HAND_IMU_FORMAT = b"fmt:imu@org:controller"
HAND_POSE_FORMAT = b"fmt:pose@org:vr6dof"


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


def feed_head_samples(push, get, session, lifetime):
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


def feed_hand_samples(push, get, session, lifetime):
    for ns in (1_000_000_000, 1_004_000_000, 1_008_000_000):
        for side, label in ((ord("0"), "left"), (ord("1"), "right")):
            payload = c.create_string_buffer(0x38)
            struct.pack_into("<BB6xQ10f", payload, 0, 1, side, ns, 0, 0, 9.8, 0, 0, 0, 1, 0, 0, 0)
            packet = AlgorithmData(HAND_IMU_FORMAT, len(payload), ns, c.addressof(payload), None)
            lifetime.extend((payload, packet))
            check_zero(f"push {label} IMU {ns}", push(session, c.byref(packet)))

    # The pinned Windows ABI writes two trivially copyable records into this vector.
    # Reserve both elements so the buffer stays owned by ctypes.
    pose_size = 0x54
    poses = c.create_string_buffer(2 * pose_size)
    first = c.addressof(poses)
    end = first + len(poses)
    vector = (c.c_void_p * 3)(first, end, end)
    packet = AlgorithmData(HAND_POSE_FORMAT, c.sizeof(vector), ns, c.addressof(vector), None)
    code = get(session, c.byref(packet))
    if list(vector) != [first, end, end]:
        raise RuntimeError("Unexpected pose vector layout")
    sides = (poses.raw[0], poses.raw[pose_size])
    states = tuple(struct.unpack_from("<I", poses.raw, start + 4)[0] for start in (0, pose_size))
    print(f"hand poses without images: {code} ({states[0]}, {states[1]})", flush=True)
    if code != -1 or sides != tuple(b"01") or states != (255, 255):
        raise RuntimeError("Expected an unsuccessful optical pose query with both hand records")


def probe(vendor, scratch, override, controllers):
    if controllers:
        dll, export, name = "HandlerDLL.dll", "GetVR6DofInterface", b"VR6Dof"
        config_key, config_size = HAND_CONFIG, 0x1C38
        input_formats, output_formats, feed = HAND_INPUT_FORMATS, HAND_POSE_FORMAT, feed_hand_samples
    else:
        dll, export, name = "arvr_slam.dll", "GetSlamInterface", b"SLAM"
        config_key, config_size = CONFIG_PARAMS, 0x840
        input_formats, output_formats, feed = INPUT_FORMATS, OUTPUT_FORMATS, feed_head_samples

    with os.add_dll_directory(str(vendor)):
        tracking = c.WinDLL(str(vendor / dll))
        wrapper = c.WinDLL(str(vendor / "VR6DOF.dll"))

        # Override the stock settings object's installation path within this process.
        # These RVAs are used only for the verified stock PC wrapper.
        settings = c.WINFUNCTYPE(c.c_void_p)(wrapper._handle + 0x56070)()
        if not settings:
            raise RuntimeError("No stock settings object")
        path_string = c.create_string_buffer(32)
        construct_string = c.WINFUNCTYPE(c.c_void_p, c.c_void_p, c.c_char_p)(wrapper._handle + 0x115A0)
        assign_string = c.WINFUNCTYPE(c.c_void_p, c.c_void_p, c.c_void_p)(wrapper._handle + 0x19160)
        destroy_string = c.WINFUNCTYPE(None, c.c_void_p)(wrapper._handle + 0x11570)
        construct_string(path_string, str(scratch).encode("mbcs"))
        try:
            assign_string(settings, path_string)
        finally:
            destroy_string(path_string)

        get_config = c.WINFUNCTYPE(c.c_void_p)(wrapper._handle + 0x2F6A0)
        init_config = c.WINFUNCTYPE(c.c_int, c.c_void_p)(wrapper._handle + 0x2FEF0)
        read_config = c.WINFUNCTYPE(c.c_int64, c.c_void_p, c.c_char_p, c.c_size_t, c.c_void_p)(
            wrapper._handle + 0x310D0)
        config = get_config()
        if not config:
            raise RuntimeError("No stock configuration object")
        if init_config(config) < 0:
            raise RuntimeError("Stock XML failed to load")
        valid = c.c_uint8()
        if read_config(config, CONFIG_VALID, 1, c.byref(valid)) != 1 or valid.value != 1:
            raise RuntimeError("Stock XML did not validate")
        parameters = c.create_string_buffer(config_size)
        if read_config(config, config_key, len(parameters), parameters) != len(parameters):
            raise RuntimeError("Stock tracking calibration has an unexpected size")

        get_interface = getattr(tracking, export)
        get_interface.argtypes = []
        get_interface.restype = c.c_void_p
        table = get_interface()
        if (not table or c.c_uint64.from_address(table).value != 0x00000001ABCD2012 or
                c.string_at(c.c_void_p.from_address(table + 8).value) != name):
            raise RuntimeError("Unexpected function table")
        print(f"{name.decode()} table RVA={table - tracking._handle:#x}, tag=00000001abcd2012", flush=True)

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
            if override is not None and key == CONFIG_PARAMS:
                if size != len(override):
                    return -1
                c.memmove(buffer, override, size)
                return size
            return read_config(context, key, size, buffer)

        @data_call
        def keep_data(_context, _packet):
            # The lifetime list keeps all input packets alive through stop and deinit.
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
        push = slot(0x70, c.c_int, c.c_void_p, c.POINTER(AlgorithmData))
        get = slot(0x78, c.c_int, c.c_void_p, c.POINTER(AlgorithmData))
        lifetime = []
        register(c.byref(callbacks))
        try:
            session = create(input_formats, output_formats)
            if not session:
                raise RuntimeError("Tracking module creation failed")
            print("create succeeded", flush=True)
            try:
                check_zero("init", init(session))
                try:
                    check_zero("start", start(session))
                    try:
                        feed(push, get, session, lifetime)
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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--parameters", type=Path, help="Use a 2112-byte slam-params.bin for GET_SLAM_PARAMS")
    mode.add_argument("--controllers", action="store_true", help="Exercise the left and right hand tracking module")
    args = parser.parse_args()
    if os.name != "nt" or c.sizeof(c.c_void_p) != 8:
        raise SystemExit("This probe requires 64-bit Windows Python.")
    if c.sizeof(AlgorithmData) != 0x120 or c.sizeof(ImuData) != 0x20:
        raise SystemExit("Unexpected packet alignment.")
    vendor = args.stock_directory.resolve(strict=True)
    override = args.parameters.read_bytes() if args.parameters else None
    if override is not None and len(override) != 0x840:
        parser.error("--parameters must contain exactly 2112 bytes")
    module = "HandlerDLL.dll" if args.controllers else "arvr_slam.dll"
    for name in (module, "VR6DOF.dll"):
        expected = DLL_HASHES[name]
        actual = hashlib.sha256((vendor / name).read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit(f"Unexpected {name} version: {actual}")
    original_directory = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="cv10-head-slam-") as scratch:
        scratch = Path(scratch)
        config_directory = scratch / "steamVRDriver/huaweiVR/bin/win64"
        config_directory.mkdir(parents=True)
        shutil.copyfile(vendor / "vrglass-handler-default.xml", config_directory / "vrglass-handler.xml")
        os.chdir(scratch)
        try:
            probe(vendor, scratch, override, args.controllers)
        finally:
            os.chdir(original_directory)


if __name__ == "__main__":
    main()
