"""PC TCP peer for SPY NETWORK PROBE 2–4; Python standard library only.

Times are local monotonic durations. TX completion means socket acceptance,
not delivery. Reports are written only after the connection is closed.
"""
import argparse
import binascii
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import socket
import struct
import time


FRAME_SIZE = 32
MAX_SAMPLES = 300


class ProbeError(Exception):
    pass


def make_frame(kind, seq, stamp):
    frame = bytearray(b'\xa5\x5aN\x01' + kind.encode('ascii') + b'\x20')
    frame.extend(struct.pack('<HI', seq, stamp))
    frame.extend((seq + i * 17) & 255 for i in range(12, 30))
    frame[12:19] = b'\x00\xff+++\r\n'
    frame.extend(struct.pack('<H', binascii.crc_hqx(frame, 0xffff)))
    return bytes(frame)


def check_frame(frame):
    if (len(frame) != FRAME_SIZE or frame[:4] != b'\xa5\x5aN\x01'
            or frame[5] != FRAME_SIZE
            or binascii.crc_hqx(frame[:30], 0xffff) != int.from_bytes(frame[30:], 'little')):
        raise ProbeError('FRAME CRC/HEADER ERROR')
    seq, stamp = struct.unpack_from('<HI', frame, 6)
    kind = chr(frame[4])
    if kind not in ('P', 'R', 'Q', 'A'):
        raise ProbeError('FRAME TYPE ERROR')
    if frame != make_frame(kind, seq, stamp):
        raise ProbeError('FRAME PAYLOAD ERROR')
    return kind, seq, stamp


def receive_frame(conn, timeout):
    deadline = time.perf_counter() + timeout
    data = bytearray()
    first = None
    while len(data) < FRAME_SIZE:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            raise ProbeError(f'FRAME TIMEOUT ({len(data)}/32 bytes)')
        conn.settimeout(remaining)
        try:
            part = conn.recv(FRAME_SIZE - len(data))
        except socket.timeout as exc:
            raise ProbeError(f'FRAME TIMEOUT ({len(data)}/32 bytes)') from exc
        now = time.perf_counter()
        if not part:
            raise ProbeError(f'PEER CLOSED ({len(data)}/32 bytes)')
        if first is None:
            first = now
        data.extend(part)
    return bytes(data), first


def send_frame(conn, frame, timeout):
    conn.settimeout(timeout)
    begin = time.perf_counter()
    try:
        conn.sendall(frame)
    except socket.timeout as exc:
        raise ProbeError('WRITE TIMEOUT') from exc
    return begin, time.perf_counter()


def ms(seconds):
    return seconds * 1000


def measure(conn, role, samples, timeout, report):
    """Append only completed samples; retain them if a later exchange fails."""
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    origin = time.perf_counter()
    seq = 0
    while True:
        report['pending_sample'] = seq + 1
        if role == 'dial':
            finish = seq == samples
            report['stage'] = 'FINISH' if finish else 'MEASURE'
            if finish:
                report['pending_sample'] = None
            start = time.perf_counter()
            stamp = int(ms(start - origin)) & 0xffffffff
            request = make_frame('Q' if finish else 'P', seq, stamp)
            tx_begin, tx_end = send_frame(conn, request, timeout)
            response, first = receive_frame(conn, timeout)
            kind, got_seq, got_stamp = check_frame(response)
            if (kind, got_seq, got_stamp) != ('A' if finish else 'R', seq, stamp):
                raise ProbeError('REPLY SEQUENCE/PAYLOAD ERROR')
            end = time.perf_counter()
            if finish:
                return
            row = dict(sample=seq+1, start_ms=ms(start-origin),
                       first_rx_ms=ms(first-origin), end_ms=ms(end-origin),
                       span_ms=ms(end-start), tx_ms=ms(tx_end-tx_begin),
                       wait_ms=ms(end-tx_end), rx_ms=None,
                       other_ms=ms(tx_begin-start), prep_ms=None)
        else:
            report['stage'] = 'RECEIVE'
            request, first = receive_frame(conn, timeout)
            kind, got_seq, stamp = check_frame(request)
            received = time.perf_counter()
            if kind not in ('P', 'Q') or got_seq != seq:
                raise ProbeError('REQUEST SEQUENCE/PAYLOAD ERROR')
            if kind == 'P' and seq >= MAX_SAMPLES:
                raise ProbeError('SAMPLE LIMIT')
            finish = kind == 'Q'
            report['stage'] = 'FINISH' if finish else 'REPLY'
            if finish:
                report['pending_sample'] = None
            response = make_frame('A' if finish else 'R', seq, stamp)
            tx_begin, tx_end = send_frame(conn, response, timeout)
            if finish:
                # Match the Pico listener's grace period after the final ACK.
                time.sleep(1)
                return
            row = dict(sample=seq+1, start_ms=ms(first-origin),
                       first_rx_ms=ms(first-origin), end_ms=ms(tx_end-origin),
                       span_ms=ms(tx_end-first), tx_ms=ms(tx_end-tx_begin),
                       wait_ms=None, rx_ms=ms(received-first),
                       other_ms=None, prep_ms=ms(tx_begin-received))
        report['records'].append(row)
        report['pending_sample'] = None
        seq += 1
        if role == 'dial':
            # Same nominal cadence as Pico; no burst to catch up after stalls.
            delay = .017 - (time.perf_counter() - start)
            if delay > 0:
                time.sleep(delay)


def summarize(report):
    rows = report['records']
    if not rows:
        return {}
    spans = sorted(row['span_ms'] for row in rows)
    summary = dict(min_ms=spans[0], avg_ms=sum(spans)/len(spans),
                   p50_ms=spans[(len(spans)-1)//2],
                   p95_ms=spans[math.ceil(len(spans)*.95)-1], max_ms=spans[-1])
    summary['above_ms'] = {str(n): sum(v > n for v in spans) for n in (200, 500, 1000)}
    summary['slowest'] = sorted(rows, key=lambda r: -r['span_ms'])[:5]
    return summary


def write_reports(prefix, report):
    report['summary'] = summarize(report)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path = Path(str(prefix) + '.json')
    csv_path = Path(str(prefix) + '.csv')
    json_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    with csv_path.open('w', newline='', encoding='utf-8') as out:
        writer = csv.DictWriter(out, fieldnames=[
            'sample', 'start_ms', 'first_rx_ms', 'end_ms', 'span_ms',
            'tx_ms', 'wait_ms', 'rx_ms', 'other_ms', 'prep_ms'])
        writer.writeheader()
        writer.writerows(report['records'])
    return json_path, csv_path


def bounded_int(low, high):
    def parse(value):
        try:
            number = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError('expected an integer') from exc
        if not low <= number <= high:
            raise argparse.ArgumentTypeError(f'expected {low}..{high}')
        return number
    return parse


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('role', choices=('listen', 'dial'))
    parser.add_argument('--host', help='Pico IPv4 address (required for dial)')
    parser.add_argument('--bind', default='0.0.0.0', help='local IPv4 address for listen')
    parser.add_argument('--port', type=bounded_int(1, 65535), default=6502)
    parser.add_argument('--samples', type=bounded_int(1, MAX_SAMPLES), default=300,
                        help='DIAL sample count; LISTEN follows the peer')
    parser.add_argument('--output', type=Path, help='report prefix (without .json/.csv)')
    args = parser.parse_args(argv)
    if args.role == 'dial' and not args.host:
        parser.error('--host is required for dial')
    if args.host:
        try:
            socket.inet_pton(socket.AF_INET, args.host)
        except OSError:
            parser.error('--host must be an IPv4 address')
    now = datetime.now(timezone.utc)
    prefix = args.output or Path('build/net-probe-pc') / (
        now.strftime('%Y%m%dT%H%M%S.%fZ') + '-' + args.role)
    report = dict(tool='SPY PC NETWORK PEER 1', role=args.role,
                  utc_start=now.isoformat(), tcp_nodelay=True, records=[],
                  stage='CONNECT', pending_sample=None, passed=False,
                  requested_samples=args.samples if args.role == 'dial' else None,
                  timing='Local perf_counter only; TX means socket acceptance. '
                         'No clock synchronization; not one-way latency.')
    print(report['tool'])
    print('Connection limit 120 s; frame/write limit 5 s. Ctrl+C cancels.', flush=True)
    try:
        if args.role == 'listen':
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                listener.bind((args.bind, args.port))
                listener.listen(1)
                listener.settimeout(120)
                print(f'Listening on {args.bind}:{args.port}; start Pico DIAL.', flush=True)
                conn, _ = listener.accept()
        else:
            print(f'Connecting to {args.host}:{args.port}; Pico must be LISTEN.', flush=True)
            conn = socket.create_connection((args.host, args.port), timeout=120)
        with conn:
            report['local_address'] = conn.getsockname()
            report['peer_address'] = conn.getpeername()
            print(f'Connected: {conn.getpeername()}. Measuring; no per-packet printing.', flush=True)
            measure(conn, args.role, args.samples, 5, report)
        report['passed'] = True
        report['stage'] = 'DONE'
    except (OSError, ProbeError, KeyboardInterrupt) as exc:
        report['error'] = 'CANCELLED' if isinstance(exc, KeyboardInterrupt) else str(exc)
    report['utc_end'] = datetime.now(timezone.utc).isoformat()
    paths = write_reports(prefix, report)
    print(f"{args.role.upper()}: {'PASS' if report['passed'] else 'FAIL'}; samples={len(report['records'])}")
    if 'error' in report:
        print(f"Stage={report['stage']}: {report['error']}")
    summary = report['summary']
    if summary:
        print('RTT ms:' if args.role == 'dial' else 'LISTEN local span ms:',
              ' '.join(f'{key}={summary[key]:.3f}' for key in
                       ('min_ms', 'avg_ms', 'p50_ms', 'p95_ms', 'max_ms')))
        print('Counts:', summary['above_ms'])
        print('Slowest (all samples and phases saved to CSV/JSON):')
        for row in summary['slowest']:
            print(f"#{row['sample']} at={row['start_ms']:.3f} span={row['span_ms']:.3f} ms")
    for path in paths:
        print(path)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
