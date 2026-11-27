"""Build and observe the C9.49.6 charging experiment. Programming is handled by cable.py."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import time

import cable


STOCK_SHA256 = 'f16057065c4c29d6d86901239371f2a6aab2bcf03c6976505c8f5971fba93e02'
PHASES = {
    0: 'sleep', 1: 'VBUS ready', 2: 'trickle charge', 3: 'precharge',
    4: 'fast charge', 5: 'end-of-charge current', 6: 'background charge',
    7: 'charge done', 8: 'charge fault', 15: 'OTG',
}


def build(stock, output, guarded=False):
    data = bytearray(stock.read_bytes())
    if cable.inspect_image(data)['sha256'] != STOCK_SHA256:
        raise ValueError('Expected the verified stock C9.49.6 dump from this unit')
    if data[0xa193:0xa19d] != bytes.fromhex('7d 0b 12 a3 3e 90 2e 00 ef f0'):
        raise ValueError('Unexpected RT9471 read and cache instruction sequence')
    # Sample IC_STATUS in the existing diagnostic slot in place of chip identity.
    # This preserves the number of I2C reads and every instruction deciding a charger write.
    data[0xa194] = 0x0f
    if guarded:
        # All non-FF levels resume the original high threshold comparison, with
        # A and carry restored. Low-level writes still take the original route.
        # On FF the guard reads only the three caches refreshed in this pass.
        # No I2C access, charger register write, or subroutine call is added.
        guard = bytes.fromhex(
            'e5 5f b4 ff 3c '           # B900: load level, branch to B941 if not FF
            'c0 82 c0 83 '              # save DPL and DPH
            '90 2e 00 e0 '              # current IC_STATUS, observer cache
            '24 0f 50 2a c3 94 07 50 25 '  # accept only F1..F7 seen/defined for this port
            '90 2e 02 e0 b4 0b 0b '    # temperature high byte: 0B or 0C
            '90 2e 01 e0 c3 94 0f 40 15 80 0c '  # 0Bxx: require low >= 0F
            'b4 0c 10 90 2e 01 e0 c3 94 3c 50 07 '  # 0Cxx: require low < 3C
            'd0 83 d0 82 02 a1 f7 '    # B934: hold, skip this charge-register write
            'd0 83 d0 82 e5 5f '       # B93B: invalid temperature or charger status
            'd3 02 a1 db'               # B941: resume OEM comparison
        )
        if data[0xa1d8:0xa1db] != bytes.fromhex('e5 5f d3'):
            raise ValueError('Unexpected original upper threshold instructions')
        if data[0xb900:0xb900 + len(guard)] != b'\xff' * len(guard):
            raise ValueError('Expected unused FF padding after the descriptor tables')
        data[0xb900:0xb900 + len(guard)] = guard
        data[0xa1d8:0xa1db] = bytes.fromhex('02 b9 00')
    data[-2:] = cable.crc16_usb(data[:-2]).to_bytes(2, 'little')
    result = cable.inspect_image(data)
    if output.exists():
        if output.read_bytes() != data:
            raise FileExistsError(output)
    else:
        with output.open('xb') as dest:
            dest.write(data)
    print(json.dumps(result, indent=2))


def sample(seconds, interval, output):
    # Both images report their original compatibility version. Sampling must follow a
    # verified full-image readback. An INFO sample of 0x69 is invalid as IC_STATUS.
    deadline = time.monotonic() + seconds
    with output.open('x', encoding='utf-8', buffering=1) as log:
        while True:
            row = {'at': datetime.now().astimezone().isoformat(timespec='milliseconds')}
            try:
                with cable.cable_reader() as read:
                    status = cable.battery_status(read)
                raw = status['charger_info_raw']
                phase = PHASES.get(raw & 0x0f, 'unrecognized') if raw != 0xff else 'ambiguous all-ones read'
                row.update(level=status['level_raw'], temperature_word=status['temperature_raw'],
                           port=status['port_status_raw'], ic_status_raw=raw,
                           phase=phase)
            except (OSError, RuntimeError, ValueError) as exc:
                row['error'] = str(exc)
            log.write(json.dumps(row, ensure_ascii=False) + '\n')
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(interval, remaining))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('build-observer', 'build-guarded'):
        builder = sub.add_parser(name)
        builder.add_argument('stock', type=Path)
        builder.add_argument('output', type=Path)
    sampler = sub.add_parser('sample-observer')
    sampler.add_argument('output', type=Path)
    sampler.add_argument('--seconds', type=int, default=30)
    sampler.add_argument('--interval', type=float, default=1)
    args = parser.parse_args()
    if args.command.startswith('build-'):
        build(args.stock, args.output, guarded=args.command == 'build-guarded')
    else:
        if args.seconds < 0 or args.interval <= 0:
            parser.error('seconds must be nonnegative and interval must be positive')
        sample(args.seconds, args.interval, args.output)


if __name__ == '__main__':
    main()
