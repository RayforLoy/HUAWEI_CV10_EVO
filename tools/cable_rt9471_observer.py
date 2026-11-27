"""Build and sample a register-tagged observer from the verified C9.49.6 application."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import time

import cable
from cable_charge_trial import STOCK_SHA256


# Adjacent slots expose low then high nibbles, obtained in separate stock poll cycles.
# Status registers are live, non-clearing registers. The interrupt event bank is excluded.
REGISTERS = (0x0b, 0x02, 0x0f, 0x10, 0x11, 0x12, 0x13, 0x0c)
# In the input profile a different tag carries INFO. Each capture must follow
# verification of the programmed image. Both profiles read non-clearing registers.
PROFILES = {
    'status': REGISTERS,
    'input': (0x03, 0x0b, 0x04, 0x02, 0x0f, 0x10, 0x11, 0x12),
}
HOOK = 0xa193
CAVE = 0xb900
NATIVE_READ = bytes.fromhex('7d 0b 12 a3 3e 90 2e 00 ef f0')


def observer_image(stock, profile='status'):
    if cable.inspect_image(stock)['sha256'] != STOCK_SHA256:
        raise ValueError('Expected verified stock CV10 C9.49.6')
    code = bytes.fromhex(
        '90 2e 00 e0 '          # read previous tag in the only modified diagnostic slot
        'c4 04 54 0f c3 13 '    # index = (((old >> 4) + 1) & 15) >> 1
        '90 b9 2a 93 fd '       # MOVC from the fixed register allowlist into R5
        '12 a3 3e '             # native one-byte read of I2C slave 0x53, result R7
        '90 2e 00 e0 24 10 54 f0 fb '  # advance tag; R3 is reloaded at A19D
        '20 e4 03 ef 80 02 ef c4 '     # even: low nibble; odd: high nibble
        '54 0f 4b f0 '          # publish tag|nibble as one MOVX
        '02 a1 9d'              # resume at original temperature reads and charge policy
    )
    if CAVE + len(code) != 0xb92a or stock[HOOK:HOOK + len(NATIVE_READ)] != NATIVE_READ:
        raise ValueError('Unexpected instructions or table location')
    patch = code + bytes(PROFILES[profile])
    if stock[CAVE:CAVE + len(patch)] != b'\xff' * len(patch):
        raise ValueError('Expected unused code padding')
    result = bytearray(stock)
    result[HOOK:HOOK + len(NATIVE_READ)] = b'\x02\xb9\x00' + bytes(len(NATIVE_READ) - 3)
    result[CAVE:CAVE + len(patch)] = patch
    result[-2:] = cable.crc16_usb(result[:-2]).to_bytes(2, 'little')
    return result


def sample(path, rounds, profile='status'):
    # Run immediately after verified programming. The compatibility version is shared
    # with stock. Require ordered tags and the RT9471 INFO identity in every round.
    observed = PROFILES[profile]
    changes = []
    completed = []
    previous = None
    current = []
    deadline = time.monotonic() + (rounds + 2) * 110
    with path.open('x', encoding='utf-8', buffering=1) as stream, cable.cable_reader() as read:
        info = cable.probe(read)
        if info['mode'] != 'runtime' or info['version_raw'] != '0c094906':
            raise ValueError('Expected cable in C9.49.6 runtime')
        cable.verify_xdata_addressing(read)
        while len(completed) < rounds and time.monotonic() < deadline:
            payload = cable.read_register(read, 0x2e00)
            if payload != previous:
                reg_index = payload >> 4
                registers = [cable.read_register(read, addr) for addr in (0x2dfe, 0x2e02, 0x2e01, 0x2dff, 0x2aa3)]
                if cable.read_register(read, 0x2e00) != payload:
                    continue
                row = dict(at=datetime.now().astimezone().isoformat(timespec='milliseconds'),
                           profile=profile, tag=reg_index, nibble=payload & 15, register=observed[reg_index >> 1],
                           gauge_level=registers[0], gauge_temperature=(registers[1] << 8) | registers[2],
                           port=registers[3], protection_state=registers[4])
                changes.append(row)
                stream.write(json.dumps(row) + '\n')
                previous = payload
                if reg_index == 0:
                    current = [row]
                elif current and reg_index == len(current):
                    current.append(row)
                else:
                    current = []
                if len(current) == 16:
                    decoded = {f'{observed[i // 2]:02X}':current[i]['nibble'] | (current[i+1]['nibble'] << 4)
                               for i in range(0, 16, 2)}
                    if decoded['0B'] == 0x69:
                        completed.append(decoded)
                        print(json.dumps(dict(round=len(completed), values=decoded)), flush=True)
                    current = []
            time.sleep(0.2)
    if len(completed) != rounds:
        raise RuntimeError(f'Only {len(completed)} complete identity-checked rounds, {len(changes)} changes')
    return completed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='op', required=True)
    build = sub.add_parser('build')
    build.add_argument('stock', type=Path)
    build.add_argument('output', type=Path)
    capture = sub.add_parser('sample')
    capture.add_argument('output', type=Path)
    capture.add_argument('--rounds', type=int, default=2, choices=range(1, 11))
    for command in (build, capture):
        command.add_argument('--profile', choices=PROFILES, default='status')
    args = parser.parse_args()
    if args.op == 'sample':
        sample(args.output, args.rounds, args.profile)
    else:
        data = observer_image(args.stock.read_bytes(), args.profile)
        with args.output.open('xb') as stream:
            stream.write(data)
        print(json.dumps(cable.inspect_image(data)))


if __name__ == '__main__':
    main()
