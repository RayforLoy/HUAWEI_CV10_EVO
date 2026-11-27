"""Build the C9.53.6 conditional 5 V / 2 A phone-PDO bench image."""

import argparse
import json
from pathlib import Path
import struct
import sys

from cable import crc16_usb, inspect_image


STOCK_SHA256 = '8e8d9d0df2809f2d3a673519834c83662acc5be6635060d75ef246133956843e'
PHONE_CURRENT_WRITE = 0x6D38
PHONE_CURRENT_CONTINUE = 0x6D41
PADDING_ENTRY = 0x9AED
STOCK_PHONE_CURRENT_WRITE = bytes.fromhex('90 28 6d e4 f0 a3 74 96 f0')


def phone_current_code():
    """Emit 8051 code that replaces the ordinary Source_Capabilities current."""
    # The stock caller already requires the selected upstream port's ready state.
    # Read the Accept flag for auxiliary port 1 and test its imported PDO and RDO.
    code = bytearray.fromhex('90 28 6d e4 f0')  # Clear upper current byte as in stock.
    code.extend(bytes.fromhex('e5 7e 54 10 60 00'))  # MOV A,7Eh / ANL / JZ fallback
    fallback_branches = [len(code) - 1]
    checks = (
        (0x2A5A, bytes.fromhex('01')),              # Selected upstream port.
        (0x2A5E, bytes.fromhex('00')),              # First requested PDO.
        (0x294A, bytes.fromhex('00')),              # Fixed PDO type.
        (0x294D, bytes.fromhex('00 64 01 2c')),    # 5 V, 3 A in imported PDO.
        (0x297C, bytes.fromhex('01 2c 01 2c')),    # RDO operating and max 3 A.
    )
    for address, expected in checks:
        code.extend((0x90, address >> 8, address & 0xFF))  # MOV DPTR,#address
        for index, value in enumerate(expected):
            if index:
                code.append(0xA3)  # INC DPTR
            code.extend((0xE0, 0x64, value, 0x70, 0))  # MOVX A,@DPTR / XRL / JNZ
            fallback_branches.append(len(code) - 1)

    # Write big-endian current in 10 mA units, returning with stock DPTR and carry.
    code.extend(bytes.fromhex('74 c8 80 02'))  # 2 A / SJMP write
    fallback = len(code)
    code.extend(bytes.fromhex('74 96'))  # Stock 1.5 A
    code.extend(bytes.fromhex('90 28 6e f0'))  # MOV DPTR,#286Eh / MOVX @DPTR,A
    code.extend((0x02, PHONE_CURRENT_CONTINUE >> 8, PHONE_CURRENT_CONTINUE & 0xFF))
    for branch in fallback_branches:
        displacement = fallback - branch - 1
        if not 0 <= displacement <= 127:
            raise ValueError('8051 fallback branch is out of range')
        code[branch] = displacement
    return code


def build_candidate(stock):
    metadata = inspect_image(stock)
    if metadata['sha256'] != STOCK_SHA256:
        raise ValueError('Expected the C9.53.6 D0DB stock image with its original SHA-256')
    if stock[PHONE_CURRENT_WRITE:PHONE_CURRENT_CONTINUE] != STOCK_PHONE_CURRENT_WRITE:
        raise ValueError('Unexpected phone PDO current write')
    helper = phone_current_code()
    end = PADDING_ENTRY + len(helper)
    if stock[PADDING_ENTRY:end] != b'\xff' * len(helper):
        raise ValueError('Expected erased bytes at the helper location')

    candidate = bytearray(stock)
    jump = bytes((0x02, PADDING_ENTRY >> 8, PADDING_ENTRY & 0xFF))
    candidate[PHONE_CURRENT_WRITE:PHONE_CURRENT_CONTINUE] = jump.ljust(len(STOCK_PHONE_CURRENT_WRITE), b'\x00')
    candidate[PADDING_ENTRY:end] = helper
    struct.pack_into('<H', candidate, len(candidate) - 2, crc16_usb(candidate[:-2]))
    result = bytes(candidate)
    inspect_image(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stock', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    candidate = build_candidate(args.stock.read_bytes())
    with args.output.open('xb') as output:
        output.write(candidate)
    print(json.dumps(inspect_image(candidate), indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        sys.exit(str(error))
