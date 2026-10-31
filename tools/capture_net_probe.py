"""Capture one PC DIAL -> Pico LISTEN test with Windows PktMon.

Run from an Administrator terminal. Uses only Python's standard library and
Windows tools. Refuses existing PktMon sessions/filters. No firewall changes.
"""
import argparse
import ctypes
from datetime import datetime, timezone
import ipaddress
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]


class CaptureError(Exception):
    pass


def ipv4(value):
    try:
        return str(ipaddress.IPv4Address(value))
    except ipaddress.AddressValueError as exc:
        raise argparse.ArgumentTypeError('expected IPv4 address') from exc


def inactive(text):
    return text.strip().rstrip('.').casefold() == 'packet monitor is not running'


def no_filters(text):
    # Fail closed for unrecognized/localized output; never clear unknown filters.
    return ' '.join(text.split()).rstrip('.').casefold() in (
        'no filters', 'no packet filters', 'no filters found',
        'no packet filters found', 'no packet filters specified',
        'packet filters: none')


def one_filter(text, name):
    rows = re.findall(r'^\s*\d+\s+(.+)$', text, flags=re.MULTILINE)
    return len(rows) == 1 and rows[0].split()[0] == name


def capture(directory, host, local, component, run, probe):
    """Inject command runners for testing ownership and cleanup without admin."""
    # PktMon truncates the Name column. Keep the complete ownership token visible.
    name = 'SpyProbe' + uuid.uuid4().hex[:8]
    if not inactive(run(['status'])):
        raise CaptureError('PktMon is active or status is unrecognized; nothing changed.')
    if not no_filters(run(['filter', 'list'])):
        raise CaptureError('Existing/unknown PktMon filters; nothing changed. See commands.json.')
    added = started = stopped = False
    own_filters = None
    errors = []
    code = None
    try:
        addresses = [local] if local == host else [local, host]
        run(['filter', 'add', name, '-i', *addresses, '-t', 'TCP', '-p', '6502'])
        added = True
        own_filters = run(['filter', 'list'])
        if not one_filter(own_filters, name):
            raise CaptureError('Cannot confirm our single filter; refusing to start capture.')
        run(['start', '--capture', '--comp', component, '--pkt-size', '0',
             '--file-name', str(directory/'packets.etl'), '--file-size', '1024',
             '--log-mode', 'multi-file'])
        started = True
        print('Capture running.', flush=True)
        code = probe()
    except (Exception, KeyboardInterrupt) as exc:
        errors.append('CANCELLED' if isinstance(exc, KeyboardInterrupt) else str(exc))
    finally:
        # Ctrl+C must not interrupt our stop/cleanup commands a second time.
        old_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            if started:
                try:
                    run(['counters'])
                except Exception as exc:
                    errors.append(f'Counters unavailable: {exc}')
                try:
                    run(['stop'])
                    stopped = True
                except Exception as exc:
                    errors.append(f'STOP FAILED: {exc}. Run pktmon stop as Administrator.')
            if added:
                try:
                    current = run(['filter', 'list'])
                    # remove has no per-name variant on this installed PktMon.
                    # Only clear when the sole filter is still ours and unchanged.
                    if (one_filter(current, name) and
                            (own_filters is None or current == own_filters)):
                        run(['filter', 'remove'])
                    else:
                        errors.append('Filters changed or format unknown; left untouched.')
                except Exception as exc:
                    errors.append(f'Filter cleanup failed: {exc}')
            if stopped:
                try:
                    for etl in sorted(directory.glob('packets*.etl')) or [directory/'packets.etl']:
                        run(['etl2pcap', str(etl), '--out', str(etl.with_suffix('.pcapng'))])
                except Exception as exc:
                    errors.append(f'Conversion failed; keep ETL: {exc}')
        finally:
            signal.signal(signal.SIGINT, old_handler)
    return dict(probe_exit_code=code, capture_started=started, capture_stopped=stopped,
                errors=errors)


def recover_own_filter(commands_path, run):
    """Recover only a filter proven to be ours by an exact saved CLI snapshot."""
    calls = json.loads(commands_path.read_text(encoding='utf-8'))
    additions = [c for c in calls if c['args'][:2] == ['filter', 'add'] and c['exit'] == 0]
    if len(additions) != 1 or not additions[0]['args'][2].startswith('SpyProbe'):
        raise CaptureError('Recovery log does not identify exactly one of our filters.')
    addition = additions[0]
    before = calls[:calls.index(addition)]
    if not any(c['args'] == ['filter', 'list'] and c['exit'] == 0 and no_filters(c['stdout'])
               for c in before):
        raise CaptureError('Recovery log does not prove the original filter list was empty.')
    snapshots = [c['stdout'] for c in calls[calls.index(addition)+1:]
                 if c['args'] == ['filter', 'list'] and c['exit'] == 0]
    if not snapshots or no_filters(snapshots[-1]):
        raise CaptureError('Recovery log has no nonempty ownership snapshot.')
    rows = re.findall(r'^\s*\d+\s+(\S+)', snapshots[-1], flags=re.MULTILINE)
    name = addition['args'][2]
    if len(rows) != 1 or not (rows[0] == name or
            (rows[0].endswith('...') and name.startswith(rows[0][:-3]) and len(rows[0]) > 12)):
        raise CaptureError('Recovery snapshot contains an unexpected filter.')
    if not inactive(run(['status'])):
        raise CaptureError('Recovery refused: PktMon is active or status unknown.')
    if run(['filter', 'list']) != snapshots[-1]:
        raise CaptureError('Recovery refused: current filters differ from the saved snapshot.')
    run(['filter', 'remove'])
    if not no_filters(run(['filter', 'list'])):
        raise CaptureError('Recovery did not leave an empty filter list.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', type=ipv4, default='192.168.1.11', help='Pico B IPv4')
    parser.add_argument('--component', default='nics',
                        help='PktMon NIC component ID, or nics (default)')
    parser.add_argument('--check', action='store_true',
                        help='test PktMon start/stop/conversion without contacting Pico')
    parser.add_argument('--check-traffic', action='store_true',
                        help='capture a local 300-sample TCP test; do not contact Pico')
    parser.add_argument('--recover-from', type=Path, metavar='COMMANDS_JSON',
                        help='remove only our stale filter matching this exact saved snapshot')
    args = parser.parse_args(argv)
    if args.component != 'nics' and not re.fullmatch(r'[1-9][0-9]*', args.component):
        parser.error('--component must be nics or a positive component ID')
    if args.check and args.check_traffic:
        parser.error('--check and --check-traffic are mutually exclusive')
    if args.check_traffic:
        args.host = '127.0.0.1'
        args.component = 'all'
    if os.name != 'nt' or not ctypes.windll.shell32.IsUserAnAdmin():
        print('PktMon requires an Administrator terminal. Capture has NOT started.', file=sys.stderr)
        return 2
    directory = ROOT/'build/net-probe-pc'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ-capture')
    directory.mkdir(parents=True, exist_ok=False)
    calls = []
    metadata = dict(host=args.host, component=args.component,
                    check_only=args.check or args.check_traffic,
                    traffic_check=args.check_traffic,
                    expected_pico_settings='PROBE 4 LISTEN port=6502 load=1 chunk=32 CPU=8MHz',
                    directory=str(directory), errors=[])

    def run(arguments):
        result = subprocess.run(['pktmon', *arguments], capture_output=True, text=True,
                                errors='replace', timeout=30)
        calls.append(dict(args=arguments, exit=result.returncode,
                          stdout=result.stdout, stderr=result.stderr))
        (directory/'commands.json').write_text(json.dumps(calls, indent=2)+'\n', encoding='utf-8')
        if result.returncode:
            raise CaptureError(f'pktmon {arguments[0]} failed: {result.stdout} {result.stderr}')
        return result.stdout

    def probe():
        # Keep terminal output, including errors, with the capture. The peer logs
        # only setup/summary, so this adds no per-packet printing or disk writes.
        print('Starting 300-sample DIAL test.', flush=True)
        command = [sys.executable, str(ROOT/'tools/net_probe_peer.py'), 'dial',
                   '--host', args.host, '--samples', '300', '--output', str(directory/'probe')]
        with (directory/'console.txt').open('w', encoding='utf-8') as out:
            process = subprocess.Popen(command, stdout=out, stderr=subprocess.STDOUT)
            try:
                return process.wait(timeout=180)
            except BaseException:
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=10)
                raise

    def local_probe():
        from concurrent.futures import ThreadPoolExecutor
        from net_probe_peer import measure
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(('127.0.0.1', 6502))
            listener.listen(1)
            listener.settimeout(10)
            def respond():
                conn, _ = listener.accept()
                with conn:
                    measure(conn, 'listen', 300, 5, {'records': []})
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(respond)
                result = probe()
                future.result(timeout=10)
                return result

    try:
        # UDP connect selects a route/local address without sending a datagram.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route:
            route.connect((args.host, 6502))
            local = route.getsockname()[0]
        metadata['local_ip'] = local
        run(['list', '--json'])
        if args.recover_from:
            recover_own_filter(args.recover_from, run)
        if args.check:
            print('Checking PktMon start/stop/conversion only; no TCP test.', flush=True)
        if args.check_traffic:
            print('Checking complete packet capture using local TCP only.', flush=True)
        if not args.check and not args.check_traffic:
            print(f'Pico {args.host}: prepare LISTEN 6502, load=1, chunk=32 at 8 MHz.')
            input('When Pico displays Waiting for connection, press Enter here: ')
        metadata.update(capture(directory, args.host, local, args.component, run,
                                (lambda: 0) if args.check else local_probe if args.check_traffic else probe))
    except (Exception, KeyboardInterrupt) as exc:
        metadata['errors'].append('CANCELLED' if isinstance(exc, KeyboardInterrupt) else str(exc))
    metadata['utc_end'] = datetime.now(timezone.utc).isoformat()
    pcaps = sorted(directory.glob('packets*.pcapng'))
    metadata['pcapng_exists'] = bool(pcaps)
    if pcaps and (directory/'probe.json').exists():
        try:
            from audit_probe_capture import audit
            coverage = audit(pcaps, json.loads((directory/'probe.json').read_text(encoding='utf-8')))
            (directory/'coverage.json').write_text(json.dumps(coverage, indent=2)+'\n', encoding='utf-8')
            metadata['all_completed_samples_observed'] = coverage['all_completed_samples_observed']
            if not metadata['all_completed_samples_observed']:
                metadata['errors'].append('Capture lacks complete request/reply coverage; see coverage.json.')
        except Exception as exc:
            metadata['errors'].append(f'Coverage check failed: {exc}')
    (directory/'capture.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')
    if (directory/'console.txt').exists():
        print((directory/'console.txt').read_text(encoding='utf-8', errors='replace'))
    print(f'Results: {directory}')
    for error in metadata['errors']:
        print(error, file=sys.stderr)
    return 0 if (metadata.get('probe_exit_code') == 0 and metadata['pcapng_exists']
                 and not metadata['errors']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
