"""Native input integrity and patch anchors; no XEX or py65 required."""
import json
from pathlib import Path
import sys
import unittest
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from prepare_spy import segments, unpack, patch_timing, patch_music, SOURCE_SHA
from native_assets import load_asset, load_manifest


class AssetTests(unittest.TestCase):
    def test_segments(self):
        parts = list(segments(bytes.fromhex('ffff 0004 0204 aabbcc ffff e202 e302 5a93')))
        self.assertEqual(parts, [(0x400, bytes.fromhex('aabbcc')), (0x2e2, b'\x5a\x93')])

    def test_invalid_and_truncated(self):
        for data in [b'', b'abc', b'\xff\xff\x01', b'\xff\xff\x00\x04',
                     b'\xff\xff\x00\x04\x02\x04\x55',
                     b'\xff\xff\x02\x04\x00\x04']:
            with self.subTest(data=data), self.assertRaises(ValueError):
                list(segments(data))

    def test_wrong_release_rejected(self):
        with self.assertRaisesRegex(ValueError, 'SHA-256 differs'):
            unpack(b'not the inspected XEX')

    def test_native_game(self):
        memory = load_asset(ROOT/'assets/native/game.bin')
        manifest = load_manifest(ROOT/'assets/native')
        self.assertEqual(manifest['sources']['game']['sha256'], SOURCE_SHA)
        self.assertEqual(manifest['game_analysis']['depacker_instructions'], 560754)
        self.assertEqual(len(memory), 65536)
        self.assertEqual(memory[0xc00:0xc0a], bytes.fromhex('78 a9 00 8d 0e d4 d8 a2 ff 9a'))
        self.assertEqual(memory[0x74bb:0x74c0], bytes.fromhex('58 a9 34 8d 1a'))
        self.assertEqual(memory[0xe400:0xe404], bytes.fromhex('a2 03 b5 00'))
        self.assertEqual(memory[0xff00:], bytes(256))

    def test_damaged_assets_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory)
            manifest = load_manifest(ROOT/'assets/native')
            (dest/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            for name in ('game.bin', 'title.bin'):
                original = load_asset(ROOT/'assets/native'/name)
                damaged = bytearray(original)
                damaged[100] ^= 1
                for data in (damaged, original[:-1]):
                    (dest/name).write_bytes(data)
                    with self.subTest(name=name, size=len(data)), self.assertRaisesRegex(ValueError, 'SHA-256 differs'):
                        load_asset(dest/name)

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
