"""Exercise numbered inputs at cooperative boundaries in the native emulator.

This tests the isolated clock experiment, not a network connection. RAM traces
and the exact emulator scripts are retained so failures can be investigated.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
from threading import Timer

from audit_determinism import Case, RAM_SIZE, SCENARIO, digest, state_regions, coverage
from build_remote_clock import labels_at

CASES = (Case('baseline'), Case('repeat'), Case('ram-seed', emulator_seed=456),
         Case('launch-plus-17', launch_extra=17), Case('menu-plus-17', menu_extra=17),
         Case('cpu-7900', phi2=7900), Case('cpu-2000', phi2=2000),
         Case('delivery-gaps', input_gap=6))


class Script:
    def __init__(self, labels, case):
        self.labels, self.case = labels, case
        self.lines, self.points = [], []
        self.sequence = 0

    def add(self, *lines):
        self.lines.extend(lines)

    def address(self, name):
        return self.labels['remote_'+name]

    def poke(self, name, *values):
        self.add(f'poke {self.address(name)} '+ ' '.join(map(str, values)))

    def peek(self, name, *values):
        self.add(f'peek {self.address(name)} '+ ' '.join(map(str, values)))

    def wait(self, name, value):
        self.add(f'wait {self.address(name)} {value} 120')

    def snapshot(self, name):
        self.add(f'dump 0 {RAM_SIZE}')
        self.points.append({'name': name, 'next': self.sequence})

    def start(self, first=False):
        if first:
            self.add(f'run {60+self.case.launch_extra}', 'press space', 'run 6',
                     'release space', f'run {600+self.case.menu_extra}', 'peek 0x377 1')
        else:
            self.poke('ready', 2)
            # Allow the original menu drawing to finish even at 2 MHz.
            self.add('run 600', 'peek 0x377 1')
        self.add('press space', 'run 12', 'release space')
        self.wait('status', 1)
        self.peek('active', 2)
        self.peek('next', 0, 0)
        self.add('peek 0x34e 2 2', 'peek 0x377 2')
        self.sequence = 0

    def packet(self, sequence, p0=31, p1=31, console=7, key=0):
        self.poke('sequence', sequence & 255, sequence >> 8)
        self.poke('p0', p0, p1, console, key)
        self.poke('ready', 1)

    def tick(self, p0=31, p1=31, console=7, key=0, end=False):
        if self.case.input_gap and self.sequence % 19 == 0:
            self.add(f'run {self.case.input_gap}')
        self.packet(self.sequence, p0, p1, console, key)
        self.sequence = (self.sequence+1) & 65535
        self.wait('next', self.sequence & 255)
        self.wait('status', 3 if end else 1)
        self.peek('next', self.sequence & 255, self.sequence >> 8)
        self.peek('error', 0)

    def keys(self, keys):
        p0, p1 = 31, 31
        for key, bit in [('up', 1), ('down', 2), ('left', 4), ('right', 8), ('space', 16)]:
            if key in keys:
                p0 &= ~bit
        for key, bit in [('w', 1), ('s', 2), ('a', 4), ('d', 8), ('lshift', 16)]:
            if key in keys:
                p1 &= ~bit
        return p0, p1


def script_for(labels, case, output):
    s = Script(labels, case)
    s.start(first=True)
    s.snapshot('start')
    # No input -> no simulation, even when physical keyboard state changes.
    s.add('press left space', 'run 60', 'release left space')
    s.snapshot('frozen')
    for name, seq, key, error in [('future', 1, 0, 1), ('bad-key', 0, 3, 3)]:
        s.packet(seq, key=key)
        s.wait('ready', 0)
        s.peek('error', error)
        s.peek('next', 0, 0)
        s.snapshot(name)
    for name, ticks, keys in SCENARIO[1:]:
        if name == 'restart-menu':
            break
        for _ in range(ticks):
            s.tick(*s.keys(keys))
        s.snapshot(name)
    s.packet(s.sequence-1)
    s.wait('ready', 0)
    s.peek('error', 1)
    s.snapshot('duplicate')
    s.tick()
    s.snapshot('after-duplicate')
    # Pause must also poll the logical mailbox, not the physical keyboard.
    for _ in range(4):
        s.tick(key=1)
    s.peek('kind', 3)
    s.add('peek 0x37d 0 0')
    s.tick()
    s.snapshot('paused')
    for _ in range(20):
        s.tick()
    s.snapshot('paused-later')
    s.tick(key=1)
    s.tick()
    s.add('peek 0x37d 1 1')
    s.snapshot('resumed')
    if case.name == 'baseline':
        s.add(f'shot "{(output/"clock-game.png").as_posix()}"')
    s.tick(console=3, end=True)
    s.snapshot('ended')
    s.add('run 60')
    s.snapshot('ended-frozen')
    s.start()
    s.snapshot('second-start')
    active = False
    for name, ticks, keys in SCENARIO:
        if name == 'combat-approach':
            active = True
        if name == 'timeout-fixture':
            break
        if active:
            for _ in range(ticks):
                s.tick(*s.keys(keys))
            s.snapshot(name)
    # Explicit sequence-wrap fixture; both counters change at a waiting gate.
    s.poke('next', 255, 255)
    s.add(f'poke {labels["remote_last_main"]} 255 255')
    s.sequence = 65535
    s.tick()
    s.snapshot('wrapped-zero')
    s.tick()
    s.snapshot('wrapped-one')
    s.tick(key=2)
    s.add('peek 0x383 1')
    s.snapshot('music-muted')
    s.tick()
    s.tick(key=2)
    s.add('peek 0x383 0')
    s.tick()
    s.snapshot('music-restored')
    return '\n'.join(s.lines)+'\n', s.points


def describe(memory, labels):
    regions = state_regions(memory)
    # Extend the earlier candidate schema with logical-clock and sound state.
    regions['music'] = memory[0x383:0x399]
    regions['phase'] = memory[0x76:0x77]
    regions['clock_enabled'] = memory[0x37d:0x37f]
    for name in ('frame_count', 'music_phase', 'remote_kind'):
        start = labels[name]
        regions[name] = memory[start:start+(2 if name == 'music_phase' else 1)]
    return {name: value.hex() for name, value in regions.items()}


def run_case(emu, out, labels, case, timeout):
    script, points = script_for(labels, case, out)
    (out/f'{case.name}.script').write_text(script, encoding='utf-8')
    result = subprocess.run([str(emu), str(out.parent/'remote-clock.rp6502'), '--script', '-',
                             '--phi2', str(case.phi2), '--seed', str(case.emulator_seed), '--mute'],
                            input=script, text=True, capture_output=True, timeout=timeout)
    (out/f'{case.name}.stderr.txt').write_text(result.stderr, encoding='utf-8')
    data = bytes.fromhex(result.stdout)
    (out/f'{case.name}.ram.bin').write_bytes(data)
    if result.returncode or len(data) != RAM_SIZE*len(points):
        raise RuntimeError(f'{case.name}: emulator failed ({result.returncode}); '
                           f'{len(data)//RAM_SIZE}/{len(points)} snapshots; {result.stderr}')
    memories = [data[i*RAM_SIZE:(i+1)*RAM_SIZE] for i in range(len(points))]
    states = [dict(point, regions=describe(memory, labels)) for point, memory in zip(points, memories)]
    by_name = {state['name']: state for state in states}
    ram_by_name = dict(zip((point['name'] for point in points), memories))
    assert ram_by_name['start'] == ram_by_name['frozen'], 'RAM changed while waiting'
    assert ram_by_name['ended'] == ram_by_name['ended-frozen'], 'Ended session advanced'
    for name in ('future', 'bad-key'):
        assert by_name['start']['regions'] == by_name[name]['regions'], f'{name} advanced simulation'
    assert by_name['black-stop']['regions'] == by_name['duplicate']['regions'], 'Duplicate advanced'
    assert by_name['paused']['regions']['clock'] == by_name['paused-later']['regions']['clock'], 'Pause clock advanced'
    observed = coverage(states)
    observed['timeout_uses_injected_clock_fixture'] = False
    report = {'case': asdict(case), 'full_trace_sha256': digest(data), 'coverage': observed,
              'checks': ['frozen RAM', 'future rejected', 'duplicate rejected', 'invalid key rejected',
                         'pause/resume', 'terminal freeze', 'restart', '16-bit sequence wrap', 'music toggle'],
              'checkpoints': states}
    (out/f'{case.name}.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


def run_ending(emu, out, labels, case, timeout):
    # The ending can be reached from an internal delay. Observe either waiting
    # or ended after each tick; a fixed physical-frame sleep would race slow CPUs.
    s = Script(labels, case)
    s.start(first=True)
    for _ in range(60):
        s.tick()
    s.add('poke 0xc2 3 3 0 0 0 0')
    name = 'ending-'+case.name
    commands, data = [], bytearray()
    with (out/f'{name}.stderr.txt').open('w', encoding='utf-8') as errors:
        with subprocess.Popen([str(emu), str(out.parent/'remote-clock.rp6502'), '--script', '-',
                               '--phi2', str(case.phi2), '--seed', str(case.emulator_seed), '--mute'],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors,
                              text=True, bufsize=1) as process:
            timer = Timer(timeout, process.kill)
            timer.start()

            def command(line):
                commands.append(line)
                process.stdin.write(line+'\n')
                process.stdin.flush()
                reply = process.stdout.readline().strip()
                if reply != 'ok' and not reply.startswith('ok '):
                    raise RuntimeError(f'{name}: {line}: {reply or "emulator stopped"}')
                return bytes.fromhex(reply[2:])

            try:
                command('reply on')
                for line in s.lines:
                    command(line)
                s.lines.clear()
                ended = None
                for _ in range(600):
                    s.packet(s.sequence)
                    for line in s.lines:
                        command(line)
                    s.lines.clear()
                    s.sequence += 1
                    for _ in range(120):
                        command('run 1')
                        status = command(f'dump {s.address("status")} 1')[0]
                        next_bytes = command(f'dump {s.address("next")} 2')
                        step = int.from_bytes(next_bytes, 'little')
                        if step == s.sequence and status in (1, 3):
                            break
                    else:
                        raise AssertionError(f'{name}: step {s.sequence-1} did not complete')
                    data.extend(bytes([status])+next_bytes)
                    if status == 3:
                        ended = step
                        break
                assert ended is not None, f'{name}: no timeout ending'
                before = command(f'dump 0 {RAM_SIZE}')
                command('run 60')
                after = command(f'dump 0 {RAM_SIZE}')
                data.extend(before+after)
                assert before == after, f'{name}: terminal RAM changed'
                assert any(before[0x37f:0x383]), f'{name}: no game-over flags'
                process.stdin.close()
                assert process.wait(timeout=10) == 0, f'{name}: emulator failed'
            finally:
                timer.cancel()
                if process.poll() is None:
                    process.kill()
                (out/f'{name}.script').write_text('\n'.join(commands)+'\n', encoding='utf-8')
                (out/f'{name}.bin').write_bytes(data)
    return {'ended_at': ended, 'regions': describe(before, labels)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emulator', type=Path, required=True)
    parser.add_argument('--experiment', type=Path, required=True)
    parser.add_argument('--cases', nargs='+', choices=[case.name for case in CASES])
    parser.add_argument('--jobs', type=int, choices=range(1, 5), default=2)
    parser.add_argument('--timeout', type=int, default=240)
    args = parser.parse_args()
    experiment, emu = args.experiment.resolve(), args.emulator.resolve()
    out = experiment/'audit'
    out.mkdir(parents=True, exist_ok=True)
    labels = labels_at(experiment/'host.lbl')
    cases = [case for case in CASES if args.cases is None or case.name in args.cases]
    if 'baseline' not in {case.name for case in cases}:
        parser.error('Include baseline')
    reports = {}
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(run_case, emu, out, labels, case, args.timeout): case.name for case in cases}
        for future in as_completed(futures):
            name = futures[future]
            reports[name] = future.result()
            print(f'Captured {name}: {len(reports[name]["checkpoints"])} boundaries', flush=True)
    reference = reports['baseline']['checkpoints']
    if 'repeat' in reports:
        assert reports['repeat']['full_trace_sha256'] == reports['baseline']['full_trace_sha256'], 'Identical-run RAM control failed'
    comparisons = {}
    for name, report in sorted(reports.items()):
        differences = []
        for left, right in zip(reference, report['checkpoints']):
            changed = [key for key in left['regions'] if left['regions'][key] != right['regions'][key]]
            if changed:
                differences.append({'name': left['name'], 'regions': changed})
        comparisons[name] = {'matches': not differences, 'differences': differences}
    endings = {}
    for case in cases:
        if case.name in ('baseline', 'cpu-2000'):
            endings[case.name] = run_ending(emu, out, labels, case, args.timeout)
            print(f'Timeout {case.name}: ended at step {endings[case.name]["ended_at"]}', flush=True)
    assert all(result == endings['baseline'] for result in endings.values()), 'Timeout ending diverged'
    observed = reports['baseline']['coverage']
    observed['game_over_observed'] = True
    observed['timeout_uses_injected_clock_fixture'] = True
    summary = {'rom_sha256': digest((experiment/'remote-clock.rp6502').read_bytes()),
               'emulator_sha256': digest(emu.read_bytes()), 'comparisons': comparisons,
               'coverage': observed, 'timeout_ending': endings,
               'checks': reports['baseline']['checks'],
               'sampling': 'Cooperative waiting boundaries after numbered inputs.',
               'limitations': ['Candidate state schema remains incomplete.', 'No hardware or network test.',
                               'No victory test. Timeout uses an explicitly shortened clock fixture.']}
    (out/'report.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    for name, comparison in comparisons.items():
        print(f'{name}: '+('MATCH' if comparison['matches'] else 'DIFFERENT'))
    print(f'Report: {out/"report.json"}')
    if not all(item['matches'] for item in comparisons.values()):
        raise SystemExit('Logical state diverged; inspect audit/report.json')
    required = ('room_transition', 'trapulator_opened', 'time_bomb_armed', 'time_bomb_expired',
                'combat_damage_observed', 'map_opened', 'game_over_observed')
    if not all(observed[key] for key in required):
        raise SystemExit('Scenario coverage incomplete')


if __name__ == '__main__':
    main()
