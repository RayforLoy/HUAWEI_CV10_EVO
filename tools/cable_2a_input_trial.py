"""Reproduce the 2.00 A C9.49.6 input-monitor image used in the 2026-11-26 PC trial."""

import argparse
import json
from pathlib import Path

import cable
from cable_rt9471_observer import observer_image


def build(stock):
    # observer_image rejects stock images other than this unit's verified C9.49.6.
    image = observer_image(stock, profile='input')
    address = 0xadc7
    original = bytes.fromhex('7b 14 7d 03 7f 53 12 99 99 22')
    if image[address:address + len(original)] != original:
        raise ValueError('Unexpected RT9471 input-current initialization')
    # Only IAICR changes within the charger configuration. AUTO_AICR stays clear.
    image[address + 1] = 0x28
    image[-2:] = cable.crc16_usb(image[:-2]).to_bytes(2, 'little')
    return bytes(image)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stock', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = build(args.stock.read_bytes())
    metadata = cable.inspect_image(result)
    with args.output.open('xb') as output:
        output.write(result)
    print(json.dumps(metadata))
