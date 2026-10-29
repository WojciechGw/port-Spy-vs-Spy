"""Extract v2's original ANTIC E loading picture, including its three DLIs.

Only the two segments preceding the first INIT belong to the picture. Later
segments overwrite them with a different game version and must not be merged.
The result is a native 320x200 4bpp VGA bitmap, preloaded into XRAM by the ROM.
"""
import argparse
import hashlib
from pathlib import Path
import struct
import zlib

from prepare_spy import atari_color, segments

SOURCE_SHA = 'e9ebfa0037c87b573390c1c64b624b6e6265a550c4da80306c43942e5d97d4b0'


def extract(data):
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA:
        raise ValueError('Title requires the inspected Spy Vs Spy (v2).xex')
    from py65.devices.mpu6502 import MPU
    cpu = MPU()
    for address, block in segments(data):
        if address == 0x2e2:
            assert block == bytes.fromhex('5a0e')
            break
        cpu.memory[address:address+len(block)] = block
    m = cpu.memory
    m[0xd016:0xd01b] = m[0xea3:0xea8]
    m[0x200:0x202] = [0, 14]
    dl, screen, y = 0xea8, 0, 0
    rows, changes = [], []
    while True:
        op = m[dl]
        dl += 1
        if op & 15 == 1:
            break
        if op & 15 == 0:
            y += ((op >> 4) & 7)+1
            continue
        if op & 15 != 14:
            raise ValueError('Unexpected title ANTIC mode')
        if op & 0x40:
            screen = m[dl] | m[dl+1] << 8
            dl += 2
        palette = [m[0xd01a], *m[0xd016:0xd019]]
        row = []
        for x in range(40):
            byte = m[(screen & 0xf000) | ((screen+x) & 0xfff)]
            row.extend(palette[(byte >> shift) & 3] for shift in (6, 4, 2, 0))
        rows.append(row)
        screen = (screen & 0xf000) | ((screen+40) & 0xfff)
        y += 1
        if op & 0x80:
            # Each handler writes WSYNC first: new colors apply on the next row.
            cpu.pc = m[0x200] | m[0x201] << 8
            cpu.sp = 255
            for _ in range(100):
                if m[cpu.pc] == 0x40:  # RTI; no OS interrupt frame needed
                    break
                cpu.step()
            else:
                raise ValueError('Title DLI did not return')
            changes.append(y)
    if len(rows) != 200 or y != 220 or changes != [49, 96, 176]:
        raise ValueError('Unexpected title display list geometry')
    colors = sorted({color for row in rows for color in row})
    if len(colors) > 16:
        raise ValueError('Title exceeds the native 4bpp palette')
    image = bytearray(0x807c)
    for y, row in enumerate(rows):
        for x, color in enumerate(row):
            index = colors.index(color)
            image[y*160+x] = index*17  # each Atari pixel becomes two VGA pixels
    for index, color in enumerate(colors):
        struct.pack_into('<H', image, 0x8000+index*2, atari_color(color))
    struct.pack_into('<BB6H', image, 0x8020, 0, 0, 0, 20, 320, 200, 0, 0x8000)
    struct.pack_into('<BB7H', image, 0x8040, 0, 0, 0, 228, 40, 1, 0x8054, 0x8050, 0xffff)
    struct.pack_into('<2H', image, 0x8050, 0x20, 0xffff)
    image[0x8054:0x807c] = b'SPACE / ENTER / FIRE'.center(40)
    return image


def preview(image):
    """Lossless PNG of the decoded native asset, with the same RGB555 palette."""
    raw = bytearray()
    for y in range(200):
        raw.append(0)
        for byte in image[y*160:(y+1)*160]:
            for index in (byte >> 4, byte & 15):
                color = struct.unpack_from('<H', image, 0x8000+index*2)[0]
                raw.extend(round(((color >> shift) & 31)*255/31) for shift in (0, 6, 11))
    def chunk(name, payload):
        return struct.pack('>I', len(payload))+name+payload+struct.pack('>I', zlib.crc32(name+payload))
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('>2I5B', 320, 200, 8, 2, 0, 0, 0))
            +chunk(b'IDAT', zlib.compress(raw))+chunk(b'IEND', b''))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    image = extract(args.source.read_bytes())
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'title.bin').write_bytes(image)
    (args.output/'title.png').write_bytes(preview(image))
