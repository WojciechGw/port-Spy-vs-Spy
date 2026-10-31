"""Check capture ownership/cleanup with an injected PktMon command runner."""
from pathlib import Path
import sys
import json
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import capture_net_probe as capture


class FakePktMon:
    def __init__(self, active=False, existing=False, fail=None, changed=False):
        self.active = active
        self.existing = existing
        self.fail = fail
        self.changed = changed
        self.calls = []
        self.name = None
        self.had_start = False

    def __call__(self, args):
        self.calls.append(args)
        if args[:len(self.fail or [])] == self.fail:
            raise capture.CaptureError('injected command failure')
        if args == ['status']:
            return 'Packet Monitor is running.' if self.active else 'Packet Monitor is not running.\n'
        if args == ['filter', 'list']:
            if self.existing:
                return '# Name Port\n1 SomeoneElse 80\n'
            if not self.name:
                # Actual output from commands.json on the user's Windows.
                return 'Packet Filters:\n    None\n'
            result = f'# Name IP Address Protocol Port\n1 {self.name} 192.168.1.11 TCP 6502\n'
            if self.changed and self.had_start:
                result += '2 SomeoneElse 80\n'
            return result
        if args[:2] == ['filter', 'add']:
            self.name = args[2]
        if args[0] == 'start':
            self.had_start = True
            self.active = True
        if args == ['stop']:
            self.active = False
        if args == ['filter', 'remove']:
            self.name = None
        return ''


class CaptureTests(unittest.TestCase):
    def run_capture(self, runner, probe=lambda: 0):
        return capture.capture(Path('test-capture'), '192.168.1.11', '192.168.1.100',
                               'nics', runner, probe)

    def test_success_scoped_filter_stop_convert(self):
        runner = FakePktMon()
        result = self.run_capture(runner)
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['probe_exit_code'], 0)
        self.assertFalse(runner.active)
        added = next(c for c in runner.calls if c[:2] == ['filter', 'add'])
        self.assertEqual(added[3:], ['-i', '192.168.1.100', '192.168.1.11', '-t', 'TCP', '-p', '6502'])
        self.assertLess(runner.calls.index(['stop']),
                        next(i for i,c in enumerate(runner.calls) if c[0] == 'etl2pcap'))
        self.assertIn(['filter', 'remove'], runner.calls)
        start = next(c for c in runner.calls if c[0] == 'start')
        self.assertEqual(start[start.index('--log-mode')+1], 'multi-file')
        self.assertIn(['counters'], runner.calls)

    def test_existing_session_or_filters_left_alone(self):
        for runner in (FakePktMon(active=True), FakePktMon(existing=True)):
            with self.assertRaises(capture.CaptureError):
                self.run_capture(runner)
            self.assertTrue(all(c in (['status'], ['filter', 'list']) for c in runner.calls))

    def test_unknown_localized_output_refused(self):
        self.assertFalse(capture.inactive('An unexpected status'))
        self.assertFalse(capture.no_filters('Unknown text'))
        self.assertFalse(capture.one_filter('something SpyProbe', 'SpyProbe'))

    def test_empty_filter_output_from_hardware(self):
        self.assertTrue(capture.no_filters('Packet Filters:\r\n    None\r\n'))
        self.assertTrue(capture.no_filters('No packet filters specified.\n'))
        self.assertFalse(capture.no_filters('Packet Filters:\n    None\n1 OtherFilter 80'))
        self.assertFalse(capture.no_filters('Packet Filters:\n1 None 6502'))

    def test_real_multiline_filter_and_truncated_name(self):
        actual = ('Packet Filters:\n'
                  '     # Name                        Protocol IP Address   Port \n'
                  '     - ----                        -------- ----------   ---- \n'
                  '     1 SpyProbe20261031T0651130... TCP      192.168.1.100 6502 \n'
                  '                                            192.168.1.11      \n')
        self.assertFalse(capture.one_filter(actual, 'SpyProbe20261031T065113068399Zcapture'))
        short = actual.replace('SpyProbe20261031T0651130...', 'SpyProbe1234abcd')
        self.assertTrue(capture.one_filter(short, 'SpyProbe1234abcd'))
        self.assertFalse(capture.one_filter(short+'2 AnotherFilter TCP 6502\n', 'SpyProbe1234abcd'))

    def test_new_filter_name_fits_pktmon_column(self):
        runner = FakePktMon()
        self.run_capture(runner)
        added = next(c for c in runner.calls if c[:2] == ['filter', 'add'])
        self.assertLessEqual(len(added[2]), 20)

    def test_recovery_requires_exact_snapshot(self):
        old_name = 'SpyProbe20261031T065113068399Zcapture'
        snapshot = 'Packet Filters:\n1 SpyProbe20261031T0651130... TCP 192.168.1.100 6502\n'
        log = [dict(args=['filter','list'], exit=0, stdout='Packet Filters:\n None\n'),
               dict(args=['filter','add',old_name], exit=0, stdout='Filter added.'),
               dict(args=['filter','list'], exit=0, stdout=snapshot)]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'commands.json'
            path.write_text(json.dumps(log))
            for changed in (False, True):
                calls = []
                def run(args):
                    calls.append(args)
                    if args == ['status']: return 'Packet Monitor is not running.'
                    if args == ['filter','list']:
                        if ['filter','remove'] in calls: return 'Packet Filters:\n None\n'
                        return snapshot + ('2 SomeoneElse TCP 80\n' if changed else '')
                    return ''
                if changed:
                    with self.assertRaises(capture.CaptureError):
                        capture.recover_own_filter(path, run)
                    self.assertNotIn(['filter','remove'], calls)
                else:
                    capture.recover_own_filter(path, run)
                    self.assertIn(['filter','remove'], calls)

    def test_probe_fail_and_interrupt_cleanup(self):
        def abort():
            raise KeyboardInterrupt()
        for probe in (lambda: 1, abort):
            runner = FakePktMon()
            result = self.run_capture(runner, probe)
            self.assertTrue(result['capture_stopped'])
            self.assertFalse(runner.active)
            self.assertIn(['filter', 'remove'], runner.calls)

    def test_start_failure_does_not_stop_another_session(self):
        runner = FakePktMon(fail=['start'])
        result = self.run_capture(runner)
        self.assertFalse(result['capture_started'])
        self.assertNotIn(['stop'], runner.calls)
        self.assertIn(['filter', 'remove'], runner.calls)
        self.assertTrue(result['errors'])

    def test_changed_filters_not_removed(self):
        runner = FakePktMon(changed=True)
        result = self.run_capture(runner)
        self.assertIn(['stop'], runner.calls)
        self.assertNotIn(['filter', 'remove'], runner.calls)
        self.assertTrue(result['errors'])

    def test_stop_or_conversion_failure_reported(self):
        for fail in (['stop'], ['etl2pcap']):
            runner = FakePktMon(fail=fail)
            result = self.run_capture(runner)
            self.assertTrue(result['errors'])
            if fail == ['stop']:
                self.assertFalse(any(c[0] == 'etl2pcap' for c in runner.calls))


if __name__ == '__main__':
    unittest.main()
