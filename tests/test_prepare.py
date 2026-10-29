"""XEX boundary checks and regression anchors for the inspected release."""
import hashlib
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from prepare_spy import segments, unpack, patch_timing, patch_music, SOURCE_SHA


class XexTests(unittest.TestCase):
    def test_segments(self):
        parts = list(segments((ROOT/'xex/SpyVsSpy.xex').read_bytes()))
        self.assertEqual([(s, len(b)) for s,b in parts],
                         [(0x2020,27),(0x244,1),(0x20ac,29524),(0x2e2,2)])
        self.assertEqual(parts[-1][1], b'\x5a\x93')

    def test_invalid_and_truncated(self):
        for data in [b'', b'abc', b'\xff\xff\x01', b'\xff\xff\x00\x04',
                     b'\xff\xff\x00\x04\x02\x04\x55',
                     b'\xff\xff\x02\x04\x00\x04']:
            with self.subTest(data=data), self.assertRaises(ValueError):
                list(segments(data))

    def test_wrong_release_rejected(self):
        data = bytearray((ROOT/'xex/SpyVsSpy.xex').read_bytes())
        data[100] ^= 1
        with self.assertRaisesRegex(ValueError, 'SHA-256 differs'):
            unpack(data)

    def test_depacker(self):
        data = (ROOT/'xex/SpyVsSpy.xex').read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), SOURCE_SHA)
        memory, steps = unpack(data)
        self.assertEqual(steps, 560754)
        self.assertEqual(len(memory), 65536)
        self.assertEqual(memory[0xc00:0xc0a], bytes.fromhex('78 a9 00 8d 0e d4 d8 a2 ff 9a'))
        self.assertEqual(memory[0x74bb:0x74c0], bytes.fromhex('58 a9 34 8d 1a'))
        self.assertEqual(memory[0xe400:0xe404], bytes.fromhex('a2 03 b5 00'))
        self.assertEqual(memory[0xff00:], bytes(256))

    def test_timing_patch_requires_original_instructions(self):
        memory = bytearray(65536)
        labels = dict(pace_main=0xc100, delay_short=0xc200, delay_long=0xc300)
        for addr, code in [(0xceb,'ad8103'), (0x2e94,'8e6d03'), (0x2ea9,'8e6d03')]:
            memory[addr:addr+3] = bytes.fromhex(code)
        patch_timing(memory, labels)
        self.assertEqual(memory[0xceb:0xcee], bytes.fromhex('2000c1'))
        self.assertEqual(memory[0x2e94:0x2e97], bytes.fromhex('4c00c2'))
        self.assertEqual(memory[0x2ea9:0x2eac], bytes.fromhex('4c00c3'))
        with self.assertRaisesRegex(ValueError, 'anchor differs'):
            patch_timing(memory, labels)

    def test_music_patch_requires_original_call(self):
        memory = bytearray(65536)
        memory[0x7550:0x7553] = bytes.fromhex('20ea34')
        patch_music(memory, {'music_tick': 0xc123})
        self.assertEqual(memory[0x7550:0x7553], bytes.fromhex('2023c1'))
        with self.assertRaisesRegex(ValueError, 'anchor differs'):
            patch_music(memory, {'music_tick': 0xc123})


if __name__ == '__main__':
    unittest.main()
