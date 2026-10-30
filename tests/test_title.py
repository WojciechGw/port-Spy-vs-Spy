"""Check the fingerprinted native splash, palette, layout and generated preview."""
from pathlib import Path
import struct
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from native_assets import load_asset
from prepare_spy import atari_color
from prepare_title import preview


class TitleTests(unittest.TestCase):
    def test_native_pixels_and_preview(self):
        image = load_asset(ROOT/'assets/native/title.bin')
        self.assertEqual(len(image), 0x807c)
        colors = sorted({0x06, 0xda, 0x42, 0x01, 0x0d, 0xc6, 0x47, 0x82})
        palette = struct.unpack_from('<16H', image, 0x8000)
        self.assertEqual(palette[:len(colors)], tuple(map(atari_color, colors)))
        for pixel in image[:32000]:
            self.assertEqual(pixel >> 4, pixel & 15)
            self.assertLess(pixel >> 4, len(colors))
        self.assertEqual(struct.unpack_from('<BB6H', image, 0x8020),
                         (0, 0, 0, 20, 320, 200, 0, 0x8000))

        self.assertEqual(image[0x8054:0x807c], b'SPACE / ENTER / FIRE'.center(40))
        png = preview(image)
        self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
        self.assertEqual(struct.unpack_from('>2I5B', png, 16), (320, 200, 8, 2, 0, 0, 0))
        pos, compressed = 8, bytearray()
        while pos < len(png):
            size = struct.unpack_from('>I', png, pos)[0]
            if png[pos+4:pos+8] == b'IDAT':
                compressed.extend(png[pos+8:pos+8+size])
            pos += size+12
        raw = zlib.decompress(compressed)
        self.assertEqual(len(raw), 200*961)
        for y in range(200):
            self.assertEqual(raw[y*961], 0)
            for x in range(320):
                color = palette[image[y*160+x//2] & 15]
                rgb = bytes(round(((color >> shift) & 31)*255/31) for shift in (0, 6, 11))
                self.assertEqual(raw[y*961+1+x*3:y*961+4+x*3], rgb)


if __name__ == '__main__':
    unittest.main()
