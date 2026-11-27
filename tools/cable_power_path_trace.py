"""Build the C9.49.6 port and battery-switch trace image, or read an armed trace."""

import argparse
import json
from pathlib import Path
import time

import cable
from cable_charge_trial import STOCK_SHA256


# Reuse the diagnostic cache that normally holds charger INFO. The two command
# addresses select reads via the VL105 USB request echo, as in cable_input_event_trial.
SLOT = 0x2e00
DISARM = 0x2c69
ARM = 0x2c5e
IDLE = 0x69
ACTIVE = 0xa0


def build(stock):
    if cable.inspect_image(stock)['sha256'] != STOCK_SHA256:
        raise ValueError('Expected the original C9.49.6 image from the measured cable')
    image = bytearray(stock)

    def patch(address, previous, replacement):
        if image[address:address + len(previous)] != previous or len(previous) != len(replacement):
            raise ValueError(f'Unexpected bytes at {address:04x}')
        image[address:address + len(previous)] = replacement

    # PUSH/POP direct SFRs work in every register bank. Preserve IE around the
    # short cache update so nested events cannot lose an earlier bit. No calls
    # or hardware I/O occur with interrupts masked except the trace RAM access.
    lock = 'c0 a8 c2 af '
    unlock = 'd0 a8 '
    save = 'c0 d0 c0 e0 c0 82 c0 83 '
    restore = 'd0 83 d0 82 d0 e0 d0 d0 '

    # One small routine per hook. Local relative branches use labels; absolute
    # jumps back to the stock firmware are checked against its exact image.
    def hook(at, original, start, body):
        code = bytearray()
        labels = {}
        branches = []
        for line in body:
            if line.endswith(':'):
                labels[line[:-1]] = len(code)
            elif '>' in line:
                opcode, name = line.split('>')
                code.extend(bytes.fromhex(opcode))
                branches.append((len(code), name))
                code.append(0)
            else:
                code.extend(bytes.fromhex(line))
        for pos, name in branches:
            offset = labels[name] - pos - 1
            if not -128 <= offset <= 127:
                raise ValueError(f'Branch too far: {name}')
            code[pos] = offset & 255
        patch(start, b'\xff' * len(code), code)
        replaced = bytes.fromhex(original)
        patch(at, replaced, b'\x02' + start.to_bytes(2, 'big') + bytes(len(replaced) - 3))

    # Called where stock publishes an INFO read. An identity mismatch disarms
    # the trace. Only an explicit standalone WinUSB read can arm a new window.
    hook(0xa198, '90 2e 00 ef f0', 0xb900, [
        'c0 d0 ef', 'b4 69>invalid',
        '90 2c f0 e0', 'b4 01>exit',
        'a3 e0', 'b4 e0>exit',
        '90 2c fa e0', '70>exit',
        '90 2c f9 e0', 'b4 2c>exit',
        '90 2c f8 e0', 'b4 69>arm', '74 69', '80>store',
        'arm:', 'b4 5e>exit',
        '90 2e 00 e0', 'b4 69>exit', '74 a0', '80>store',
        'invalid:', '74 60',
        'store:', '90 2e 00 f0',
        'exit:', '90 2e 00 ef d0 d0 02 a1 9d',
    ])
    # Replicate the OEM port-cache reset and invalidate the measurement epoch.
    hook(0xadc1, 'e4 90 2d ff f0 22', 0xb950, [
        '90 2e 00 74 69 f0 e4 90 2d ff f0 22',
    ])
    # State 3 has just finished both GPIO writes and the stock pulse delay.
    # Record the port argument only after the original pulse has completed.
    hook(0x3b3d, '90 2a 9f', 0xb970, [
        'c0 d0', lock, '90 2e 00 e0 54 f0', 'b4 a0>done',
        'e5 5f', 'b4 01>second', 'e0 44 01 f0', '80>done',
        'second:', 'b4 02>done', 'e0 44 02 f0',
        'done:', unlock, 'd0 d0 90 2a 9f 02 3b 40',
    ])
    # Inspect arguments of the native I2C single-byte writer before bus START.
    # A bit means a call was made, not that the IC accepted the request.
    hook(0x9999, 'ce ef ce', 0xb9b0, [
        save, 'bf 53>return', 'bd 02>return', lock,
        '90 2e 00 e0 54 f0', 'b4 a0>release',
        'eb', '30 e5>clear', 'e0 44 04 f0', '80>release',
        'clear:', 'e0 44 08 f0',
        'release:', unlock, 'return:', restore,
        'ce ef ce 02 99 9c',
    ])
    image[-2:] = cable.crc16_usb(image[:-2]).to_bytes(2, 'little')
    return bytes(image)


def decode(raw):
    result = {'raw': f'{raw:02X}', 'armed': raw & 0xf0 == ACTIVE}
    if result['armed']:
        result.update(port1_pulse_completed=bool(raw & 1),
                      port2_pulse_completed=bool(raw & 2),
                      battery_disconnect_requested=bool(raw & 4),
                      battery_disconnect_bit_written_clear=bool(raw & 8))
    return result


def capture(arm):
    with cable.cable_reader() as read:
        info = cable.probe(read)
        if info['mode'] != 'runtime' or info['version_raw'] != '0c094906':
            raise ValueError('Expected the C9.49.6 trace build in normal USB mode')
        cable.verify_xdata_addressing(read)
        if arm:
            for address, expected in ((DISARM, IDLE), (ARM, ACTIVE)):
                deadline = time.monotonic() + 21
                while time.monotonic() < deadline:
                    cable.read_register(read, address)
                    time.sleep(0.4)
                    value = cable.read_register(read, SLOT)
                    if value == expected or (expected == ACTIVE and decode(value)['armed']):
                        break
                else:
                    raise TimeoutError(f'Trace command {address:04x} did not complete')
        return decode(cable.read_register(read, SLOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    builder = sub.add_parser('build')
    builder.add_argument('stock', type=Path)
    builder.add_argument('output', type=Path)
    sub.add_parser('arm')
    sub.add_parser('read')
    args = parser.parse_args()
    if args.action == 'build':
        data = build(args.stock.read_bytes())
        with args.output.open('xb') as file:
            file.write(data)
        print(json.dumps(cable.inspect_image(data)))
    else:
        print(json.dumps(capture(args.action == 'arm')))


if __name__ == '__main__':
    main()
