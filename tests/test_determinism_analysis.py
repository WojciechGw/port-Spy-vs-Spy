"""Check that the offline audit detects relevant drift without hashing video."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from audit_determinism import (Case, RAM_SIZE, SCENARIO, SEED_ANCHOR, compare,
                               describe, digest, fixed_seed_image, script_for)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.memory = bytearray((ROOT/'assets/native/game.bin').read_bytes()[:RAM_SIZE])
        self.memory[0x345] = 5
        self.labels = {'frame_count': 0xd8cb, 'main_tick': 0xd921, 'video_stamp': 0xd8d0}

    def report(self, memory):
        return {'full_trace_sha256': digest(memory),
                'checkpoints': [dict(name='start', **describe(memory, self.labels))]}

    def test_world_change_is_detected(self):
        before = self.report(self.memory)
        self.memory[0x7a00+41] ^= 1
        result = compare(before, self.report(self.memory))
        self.assertFalse(result['candidate_state_matches'])
        self.assertFalse(result['world_and_position_matches'])
        self.assertIn('room_record_01', result['first_difference']['regions'])

    def test_timers_are_simulation_state(self):
        before = self.report(self.memory)
        self.memory[0xc2] ^= 1
        result = compare(before, self.report(self.memory))
        self.assertFalse(result['candidate_state_matches'])
        self.assertTrue(result['world_and_position_matches'])

    def test_presentation_is_not_candidate_state(self):
        before = self.report(self.memory)
        for address in (0x100, 0x9400, 0xbc00, 0xd200, 0xd20a, 0xd8cb):
            self.memory[address] ^= 1
        result = compare(before, self.report(self.memory))
        self.assertTrue(result['candidate_state_matches'])
        self.assertFalse(result['full_trace_matches'])

    def test_bad_snapshot_and_checkpoint_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            describe(self.memory[:-1], self.labels)
        self.memory[0x345] = 255
        with self.assertRaisesRegex(ValueError, 'room count'):
            describe(self.memory, self.labels)
        self.memory[0x345] = 5
        self.memory[0x57c9] ^= 1
        with self.assertRaisesRegex(ValueError, 'room record'):
            describe(self.memory, self.labels)
        with self.assertRaisesRegex(ValueError, 'checkpoint'):
            compare({'checkpoints': [{'name': 'a'}]}, {'checkpoints': [{'name': 'b'}]})

    def test_fixed_seed_patch_is_guarded_and_isolated(self):
        original = bytes(self.memory)
        self.assertEqual(original[0x2ec5:0x2ecb], SEED_ANCHOR)
        patched = fixed_seed_image(original, 123)
        self.assertEqual(patched[:0x2ec5], original[:0x2ec5])
        self.assertEqual(patched[0x2ecb:], original[0x2ecb:])
        self.assertEqual(patched[0x2ec5:0x2ecb], bytes.fromhex('a97b4cd82eea'))
        self.assertEqual(bytes(self.memory), original)
        with self.assertRaisesRegex(ValueError, 'entry'):
            fixed_seed_image(patched, 123)
        with self.assertRaisesRegex(ValueError, 'byte'):
            fixed_seed_image(original, 256)

    def test_delayed_input_preserves_actions(self):
        normal, normal_points = script_for(Case('normal'))
        delayed, delayed_points = script_for(Case('delayed', input_gap=6))
        self.assertEqual(len(normal_points), len(SCENARIO))
        self.assertEqual(normal_points[0], delayed_points[0])
        for a, b in zip(normal_points[1:], delayed_points[1:]):
            self.assertEqual(a['name'], b['name'])
            self.assertEqual(a['elapsed_video_frames']+6, b['elapsed_video_frames'])
        self.assertEqual([x for x in normal.splitlines() if x.startswith(('press ', 'release '))],
                         [x for x in delayed.splitlines() if x.startswith(('press ', 'release '))])


if __name__ == '__main__':
    unittest.main()
