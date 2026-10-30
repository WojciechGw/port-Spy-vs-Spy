"""Compare every decoded title pixel with the inspected Atari bitmap/palettes."""
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from prepare_spy import atari_color, segments
from prepare_title import extract


class TitleTests(unittest.TestCase):
    def test_original_pixels_and_dli_colors(self):
        source = (ROOT/'xex/Spy Vs Spy (v2).xex').read_bytes()
        parts = list(segments(source))
        self.assertEqual([(a, len(b)) for a, b in parts[:3]],
                         [(0xe00, 378), (0x1010, 8048), (0x2e2, 2)])
        image = extract(source)
        self.assertEqual(image, (ROOT/'assets/native/title.bin').read_bytes())
        native_palette = struct.unpack_from('<16H', image, 0x8000)
        # Independent reference: the three inspected handlers change colors
        # after screen lines 48, 95, 175; the picture starts at screen line 20.
        for y in range(200):
            colors = ([0x06, 0xda, 0x42, 0x01] if y < 29 else
                      [0x06, 0x0d, 0xc6, 0x01] if y < 76 else
                      [0x06, 0x0d, 0x47, 0x01] if y < 156 else
                      [0x06, 0x0d, 0x42, 0x82])
            for x in range(160):
                source_byte = parts[1][1][y*40+x//4]
                expected = atari_color(colors[(source_byte >> (6-2*(x%4))) & 3])
                pixel_pair = image[y*160+x]
                self.assertEqual(native_palette[pixel_pair >> 4], expected, (x, y))
                self.assertEqual(pixel_pair >> 4, pixel_pair & 15)
        self.assertEqual(struct.unpack_from('<BB6H', image, 0x8020),
                         (0, 0, 0, 20, 320, 200, 0, 0x8000))

    def test_wrong_source_rejected(self):
        with self.assertRaises(ValueError):
            extract((ROOT/'xex/SpyVsSpy.xex').read_bytes())


if __name__ == '__main__':
    unittest.main()
