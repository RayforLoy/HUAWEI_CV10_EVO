"""Capture RT9471 input-limit events across one headset trial on the stock 1 A policy."""

import argparse
import json
from pathlib import Path
import time

import cable
from cable_charge_trial import STOCK_SHA256


# These are harmless read addresses in OEM scratch RAM. Their last USB request
# echoes select an action; no command writes into them. IRQ1 is read-to-clear.
PRIME = 0x2c69
ARM = 0x2c5e
FINISH = 0x2c5f
RESULT = 0x2e00
RESET, READY, ARMED = 0x69, 0x81, 0xa1
TAG_MASK = 0xf1
ERRORS = {0xe1: 'INFO control read did not return 69',
          0xe3: 'bus response differs from the three phases of the INFO control',
          0xed: 'IRQ1 reserved bit set or invalid read'}
CAVE = 0xb900


def observer_image(stock):
    if cable.inspect_image(stock)['sha256'] != STOCK_SHA256:
        raise ValueError('This diagnostic requires the verified stock C9.49.6 image')
    code = bytearray()
    labels = {}
    fixups = []

    def emit(instructions):
        code.extend(bytes.fromhex(instructions))

    def label(name):
        labels[name] = len(code)

    def branch(opcode, dest):
        emit(opcode)
        fixups.append((len(code), dest))
        code.append(0)

    # Replaces only the store after the original RT9471 INFO read. Rejoin with
    # original A=R7, DPTR=2E00, flags and general registers.
    emit('c0 d0 ef')                              # PUSH PSW; MOV A,R7
    branch('b4 69', 'exit')                       # identity check
    emit('90 2c f0 e0')
    branch('b4 01', 'exit')                       # vendor read, wValue low 01
    emit('a3 e0')
    branch('b4 e0', 'exit')                       # bRequest E0
    emit('90 2c fa e0')
    branch('70', 'exit')                          # wIndex high 00
    emit('90 2c f9 e0')
    branch('b4 2c', 'exit')                       # XDATA page 2C
    emit('90 2c f8 e0')
    branch('b4 69', 'arm_check')
    emit('90 2e 00 e0 54 f1')
    branch('b4 a1', 'prime')                      # never erase an armed window
    branch('80', 'exit')
    label('prime')
    branch('b4 81', 'take')                       # leave a completed calibration intact
    branch('80', 'exit')
    label('arm_check')
    branch('b4 5e', 'finish_check')
    emit('90 2e 00 e0 54 f1')
    branch('b4 81', 'exit')                       # one clear per new READY tag
    branch('80', 'take')
    label('finish_check')
    branch('b4 5f', 'exit')
    emit('90 2e 00 e0 54 f1')
    branch('b4 a1', 'exit')                       # refuse to span charger re-init
    label('take')
    # Short jump over the common exit; no IRQ read in normal headset operation.
    branch('80', 'read_irq')
    label('exit')
    emit('90 2e 00 ef d0 d0 22')
    label('read_irq')
    emit('ec c0 e0 ed c0 e0 ee c0 e0 ef c0 e0')  # preserve bank-selected R4..R7
    emit('90 2e 00 e0 54 f1')
    branch('b4 81', 'check_armed')
    branch('80','irq_index')
    label('check_armed')
    branch('b4 a1', 'info_index')
    label('irq_index')
    emit('7d 21')
    branch('80','start_bus')
    label('info_index')
    emit('7d 0b')
    label('start_bus')
    # Same low-level 8051 bus primitives and STOP as the native one-byte read.
    # Capture status.bit0 separately for address, index and repeated start.
    # Calibrate the polarity with an actual control read of INFO==69. Keep the
    # OEM sticky success/error bit intact; the native primitives manage it.
    emit('7c 00 7f 53 12 8e d2 12 96 14 13 ec 33 fc')
    emit('ed ff 12 96 fc 13 ec 33 fc')
    emit('d2 52 8e 6a 12 96 14 13 ec 33 fc')
    emit('d2 51 12 97 96 12 8e 9f ec 23 fc ed')
    branch('b4 0b', 'irq_result')
    emit('ef')
    branch('b4 69', 'bad_info')
    emit('ec 44 81')
    branch('80', 'publish')
    label('irq_result')
    emit('90 2e 00 e0 6c 54 0e')
    branch('70', 'bad_ack')
    emit('ef')
    branch('20 e0', 'bad_reserved')
    emit('e0 54 f1')
    branch('b4 81', 'result')
    emit('ec 44 a1')
    branch('80','publish')
    label('result')
    emit('ef')                                    # expose complete raw IRQ1
    branch('80', 'publish')
    label('bad_info')
    emit('74 e1')
    branch('80','publish')
    label('bad_ack')
    emit('74 e3')
    branch('80','publish')
    label('bad_reserved')
    emit('74 ed')
    label('publish')
    emit('90 2e 00 f0 d0 e0 ff d0 e0 fe d0 e0 fd d0 e0 fc')
    emit('90 2e 00 ef d0 d0 22')
    label('reset')
    # Replicate OEM clear of 2DFF and invalidate diagnostic continuity in
    # the charger initialization that follows its register reset command.
    emit('90 2e 00 74 69 f0 e4 90 2d ff f0 22')
    for pos, dest in fixups:
        relative = labels[dest] - pos - 1
        if not -128 <= relative <= 127:
            raise ValueError(f'Branch out of range: {dest}')
        code[pos] = relative & 255
    result = bytearray(stock)
    if stock[0xa198:0xa19d] != bytes.fromhex('90 2e 00 ef f0') or stock[0xadc1:0xadc7] != bytes.fromhex('e4 90 2d ff f0 22'):
        raise ValueError('Unexpected OEM hooks')
    if stock[CAVE:CAVE + len(code)] != bytes([255]) * len(code):
        raise ValueError('Expected unused padding')
    result[0xa198:0xa19d] = bytes.fromhex('12 b9 00 00 00')
    result[0xadc1:0xadc7] = bytes([2]) + (CAVE + labels['reset']).to_bytes(2, 'big') + bytes(3)
    result[CAVE:CAVE + len(code)] = code
    result[-2:] = cable.crc16_usb(result[:-2]).to_bytes(2, 'little')
    return result


def command(read, address, valid, previous):
    deadline = time.monotonic() + 21
    while time.monotonic() < deadline:
        cable.read_register(read, address)
        time.sleep(0.4)
        value = cable.read_register(read, RESULT)
        if valid(value):
            return value
        if value in ERRORS and value != previous:
            raise RuntimeError(ERRORS[value])
    raise TimeoutError(f'Diagnostic request {address:04X} timed out; last marker {value:02X}')


def capture(action):
    with cable.cable_reader() as read:
        info = cable.probe(read)
        if info['mode'] != 'runtime' or info['version_raw'] != '0c094906':
            raise ValueError('Expected C9.49.6 diagnostic runtime')
        cable.verify_xdata_addressing(read)
        previous = cable.read_register(read, RESULT)
        if action == 'peek':
            return {'cache': f'{previous:02X}'}
        if action == 'arm':
            if previous & TAG_MASK == ARMED:
                raise ValueError('A window is already armed')
            ready = command(read, PRIME, lambda value: value & TAG_MASK == READY, previous)
            armed = command(read, ARM, lambda value: value == (ready | 0x20), ready)
            return {'previous': f'{previous:02X}', 'cleared_and_armed': True,
                    'info_control_ack_bits': (armed >> 1) & 7}
        if previous & TAG_MASK != ARMED:
            raise ValueError(f'Cannot attribute an IRQ window: active marker lost, found {previous:02X}')
        raw = command(read, FINISH, lambda value: value & 1 == 0, previous)
        return {'armed_marker_preserved': True, 'irq1': f'{raw:02X}',
                'input_voltage_regulation_edge': bool(raw & 0x80),
                'input_current_regulation_edge': bool(raw & 0x40)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    builder = modes.add_parser('build')
    builder.add_argument('stock', type=Path)
    builder.add_argument('output', type=Path)
    for name in ('peek', 'arm', 'finish'):
        modes.add_parser(name)
    args = parser.parse_args()
    if args.mode == 'build':
        data = observer_image(args.stock.read_bytes())
        with args.output.open('xb') as f:
            f.write(data)
        print(json.dumps(cable.inspect_image(data)))
    else:
        print(json.dumps(capture(args.mode)))


if __name__ == '__main__':
    main()
