"""Run the real probe on sim65 against a fragmented, fault-injecting modem."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from build_net_probe import compile_program

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--cl65', default='cl65')
parser.add_argument('--sim65', default='sim65')
args = parser.parse_args()
out = args.output.resolve()
binary = out/'net-probe-test'
compile_program(args.cl65, 'sim6502', [ROOT/'src/net-probe/main.c', ROOT/'src/net-probe/protocol.c',
                                      ROOT/'tests/net_probe_mock.c'], binary,
                {'main.c': ['-D', 'main=probe_main']})
cases = [(0, ['dial', 'localhost:6502', '0', str(chunk), '4'], 'DIAL: PASS', 0) for chunk in (1, 7, 32, 64)]
cases += [(0, ['listen', '6502', '1', str(chunk)], 'LISTEN: PASS', 0) for chunk in (1, 7, 64)]
cases += [(10, ['dial', 'localhost:6502', '0', '32', '4'], 'DIAL: PASS', 0)]
for role, target in [('listen', '6502'), ('dial', 'localhost:6502')]:
    for mode, expected, code in [(15, role.upper()+': PASS', 0), (16, role.upper()+': PASS', 0),
                                  (17, 'AT RESPONSE TIMEOUT', 1)]:
        cases.append((mode, [role, target, '0', '32', '4'], expected, code))
for mode, expected in [(1, 'Cannot open AT:'), (2, 'FRAME CRC/HEADER ERROR'),
                       (3, 'REPLY SEQUENCE/PAYLOAD ERROR'), (4, 'FRAME TIMEOUT'),
                       (5, 'WRITE TIMEOUT'), (6, 'READ ERROR'), (7, 'ERROR'),
                       (9, 'CANCELLED'), (12, 'FRAME TIMEOUT'), (13, 'REPLY SEQUENCE/PAYLOAD ERROR')]:
    cases.append((mode, ['dial', 'localhost:6502', '0', '32', '4'], expected, 1))
cases.append((14, ['listen', '6502'], 'REQUEST SEQUENCE/PAYLOAD ERROR', 1))
for target in ('localhost:0', 'localhost:65536', 'localhost:12\rATH', 'localhost', ':6502'):
    cases.append((0, ['dial', target], 'Usage:', 2))
cases += [(18, [], 'RTT counts: >200ms=7 >500ms=5 >1000ms=3', 0),
          (19, [], 'First: #1 at=0 ms rtt=0 ms', 0),
          (20, [], 'RTT counts: >200ms=100 >500ms=0 >1000ms=0', 0),
          (21, ['dial', 'localhost:6502', '0', '32', '4'], 'DIAL: PASS', 0),
          (22, ['dial', 'localhost:6502', '0', '32', '4'], 'DIAL: PASS', 0),
          (23, ['dial', 'localhost:6502', '0', '32', '4'], 'Incomplete sample #3', 1)]
cases += [(24, ['dial', 'localhost:6502', '0', '32', '4'], 'DIAL: PASS', 0),
          (25, ['listen', '6502'], 'LISTEN: PASS', 0),
          (26, ['listen', '6502'], 'LISTEN: PASS', 0),
          (27, ['listen', '6502'], 'SAMPLE LIMIT; samples=300', 1)]
records = []
for index, (mode, argv, expected, code) in enumerate(cases):
    result = subprocess.run([str(args.sim65), str(binary), str(mode), *argv], capture_output=True, text=True, timeout=30)
    (out/f'test-{index:02d}.txt').write_text(result.stdout+result.stderr, encoding='utf-8')
    assert result.returncode == code and expected in result.stdout, (mode, argv, result.returncode, result.stdout, result.stderr)
    slow = [tuple(map(int, row)) for row in re.findall(r'^#(\d+) at=(\d+) ms rtt=(\d+) ms$', result.stdout, re.M)]
    phases = [tuple(map(int, row)) for row in re.findall(r'^#(\d+) span=(\d+) tx=(\d+) (?:wait|rx)=(\d+) (?:other|prep)=(\d+)$', result.stdout, re.M)]
    for seq, span, tx, rx, other in phases:
        assert span == tx+rx+other, (mode, phases)
    if phases:
        assert result.stdout.index(': PASS' if code == 0 else '; samples=') < result.stdout.index('phases ms'), result.stdout
    if slow and phases:
        assert [(r[0], r[2]) for r in slow] == [(r[0], r[1]) for r in phases], (slow, phases)
    if mode in (21, 22, 25):
        assert phases[0][0] == (1 if mode == 21 else 3) and phases[0][2] > 1200, phases
        assert phases[0][3] < 1000, phases
    if mode in (24, 26):
        assert phases[0][0] == 3 and phases[0][3] > 1200, phases
        assert phases[0][2] < 1000, phases
    if mode == 18:
        assert slow == [(9, 4454, 1390), (6, 2402, 1001), (7, 3403, 1001), (5, 1402, 1000), (4, 901, 501)], slow
        assert 'min=50 avg=649 p50=501 p95=1390 max=1390' in result.stdout
    if mode == 19:
        assert result.stdout.startswith('EMPTY DONE\n') and slow == [(1, 0, 0)]
        assert 'min=0 avg=0 p50=0 p95=0 max=0' in result.stdout
    if mode == 20:
        assert slow == [(i, (i-1)*100, i) for i in range(300, 295, -1)], slow
        assert 'min=1 avg=150 p50=150 p95=285 max=300' in result.stdout
    if mode in (21, 22):
        assert slow[0][0] == (1 if mode == 21 else 3) and slow[0][2] > 1200, slow
        assert '>1000ms=1' in result.stdout
    if mode == 23:
        assert 'samples=2' in result.stdout and len(slow) == 2
        assert {row[0] for row in slow} == {1, 2}
    if 'DIAL:' in result.stdout and slow:
        # These application scenarios complete <=4 samples, so top-five retains
        # all of them. Recompute statistics from the independently parsed log.
        vals = sorted(row[2] for row in slow)
        times = sorted(slow)
        assert times[0][1] == 0 and all(a[1] <= b[1] for a, b in zip(times, times[1:])), times
        assert f'avg={sum(vals)//len(vals)} ' in result.stdout
        assert f'>200ms={sum(v > 200 for v in vals)} >500ms={sum(v > 500 for v in vals)} >1000ms={sum(v > 1000 for v in vals)}' in result.stdout
        assert result.stdout.index('DIAL:') < result.stdout.index('Slowest ('), 'Statistics printed during sampling'
    records.append({'mode': mode, 'args': argv, 'expected': expected, 'exit': code})
print(f'PASS: {len(cases)} cases; transport, AT timing, statistics, phase sums, TX/wait/fragment delays, sample limit', flush=True)

emu = ROOT/'tools/rp6502-emu.exe'
if emu.exists():
    # Production ROM: verify argv allocation, interactive prompts and clean
    # handling of a platform without a modem. Both graphics setup paths run.
    for load in (0, 1):
        result = subprocess.run([str(emu), str(out/'net-probe.rp6502'), '--script', '-', '--mute',
                                 '--', 'dial', '127.0.0.1:6502', str(load)],
                                input='wait "Cannot open AT:" 180\nexpect-exit 1\n',
                                capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout+result.stderr
    result = subprocess.run([str(emu), str(out/'net-probe.rp6502'), '--script', '-', '--mute'],
                            input='wait "Role (listen/dial):"\ntype "listen\\r"\nwait "Port (listen)"\n'
                                  'type "6502\\r"\nwait "Graphics load"\ntype "0\\r"\n'
                                  'wait "Cannot open AT:"\nexpect-exit 1\n',
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout+result.stderr
    # Real RP6502 runtime, clock, keyboard and VGA; only modem I/O is mocked.
    native = out/'net-probe-native-test.bin'
    compile_program(args.cl65, 'rp6502', [ROOT/'src/net-probe/main.c', ROOT/'src/net-probe/protocol.c',
                                        ROOT/'src/net-probe/pico.c', ROOT/'tests/net_probe_mock.c'], native,
                    {'main.c': ['-D', 'main=probe_main'], 'net_probe_mock.c': ['-D', 'PROBE_NATIVE=1'],
                     'pico.c': ['-D', 'probe_open=unused_open', '-D', 'probe_read=unused_read',
                                '-D', 'probe_write=unused_write', '-D', 'probe_close=unused_close']})
    rom = native.with_suffix('.rp6502')
    subprocess.run([sys.executable, str(ROOT/'tools/rp6502.py'), 'create', str(native),
                    '-a', '0x200', '-r', '0x200', '-o', str(rom)], check=True)
    for hz, load in [(8000, 0), (8000, 1), (2000, 1)]:
        result = subprocess.run([str(emu), str(rom), '--script', '-', '--mute', '--phi2', str(hz),
                                 '--', '0', 'dial', 'localhost:6502', str(load), '32', '4'],
                                input='wait "DIAL: PASS" 3600\nwait "RTT counts:"\nwait "Slowest ("\nwait "DIAL phases ms"\nexpect-exit 0\n',
                                capture_output=True, text=True, timeout=90)
        (out/f'native-{hz}-{load}.txt').write_text(result.stdout+result.stderr, encoding='utf-8')
        assert result.returncode == 0, result.stdout+result.stderr
    result = subprocess.run([str(emu), str(rom), '--script', '-', '--mute', '--phi2', '8000',
                             '--', '0', 'listen', '6502', '1', '32'],
                            input='wait "LISTEN: PASS" 3600\nwait "LISTEN phases ms"\nexpect-exit 0\n',
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout+result.stderr
    # Exercise the actual RIA clock, not just simulated milliseconds: a silent
    # listener must remain alive for almost 120 seconds, then time out on CONNECT.
    for mode, script in [
        (16, 'wait "LISTEN: PASS" 4000\nexpect-exit 0\n'),
        (17, 'wait "Modem ready." 300\nrun 7100\nexpect-not "TIMEOUT"\n'
             'wait "AT RESPONSE TIMEOUT" 200\nexpect "Stage=CONNECT"\nexpect-exit 1\n')
    ]:
        result = subprocess.run([str(emu), str(rom), '--script', '-', '--mute', '--phi2', '8000',
                                 '--', str(mode), 'listen', '6502', '0', '32', '4'],
                                input=script, capture_output=True, text=True, timeout=90)
        (out/f'native-connect-{mode}.txt').write_text(result.stdout+result.stderr, encoding='utf-8')
        assert result.returncode == 0, result.stdout+result.stderr
    print('PASS: native argv/UI/no-modem handling and mocked transport with real VGA/clock at 2/8 MHz')
(out/'test-report.json').write_text(json.dumps({
    'rom_sha256': hashlib.sha256((out/'net-probe.rp6502').read_bytes()).hexdigest(),
    'sim65_cases_passed': records, 'native_smoke_cases_passed': 9 if emu.exists() else 0,
    'physical_network_tested': False,
    'note': 'Mock RTT values are artificial and must not be used as Wi-Fi measurements.'
}, indent=2)+'\n', encoding='utf-8')
