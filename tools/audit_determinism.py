"""Offline determinism audit of the shipping ROM and a fixed-seed experiment.

This is a diagnostic, not a network implementation or a lockstep acceptance
test. Snapshots are taken at emulator video-frame boundaries, not at identical
6502 instructions. Candidate state hashes deliberately exclude graphics,
audio, the CPU stack and host scratch; they are not a complete state schema.
Full RAM traces are retained for investigating anything the schema misses.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import subprocess
import sys

RAM_SIZE = 0xff00  # Exclude hardware registers at FFxx: reads may have effects.
SEED_ANCHOR = bytes.fromhex('adc52eae9db6')
REGIONS = {
    'position': (0x88, 6),         # X[2], vertical animation offsets[2], Y[2]
    'room': (0x90, 2),            # Used by $376D to obtain the room record.
    'trapulator': (0xb4, 2),      # $37BB: bit 7 = active.
    'action_state': (0xb6, 2),
    'trap_cursor': (0x320, 4),    # $3811: column * 2 + row.
    'damage': (0x32e, 2),
    'time_bomb': (0x348, 4),      # Room[2], countdown[2]; armed by $3858.
    'map_visible': (0x357, 2),
    'game_mode': (0x377, 1),
    'ending': (0x37f, 4),
    'clock': (0xc2, 8),          # $32FA: BCD clock and time penalties.
    'prng': (0x368, 5),          # $2EE0: original game PRNG, distinct from D20A.
}
REQUIRED_COVERAGE = ('room_transition', 'trapulator_opened', 'map_opened',
                     'time_bomb_armed', 'time_bomb_expired',
                     'combat_damage_observed', 'game_over_observed')


@dataclass(frozen=True)
class Case:
    name: str
    phi2: int = 8000
    emulator_seed: int = 123
    launch_extra: int = 0
    menu_extra: int = 0
    input_gap: int = 0


CASES = (
    Case('baseline'), Case('repeat'), Case('ram-seed', emulator_seed=456),
    Case('launch-plus-17', launch_extra=17), Case('menu-plus-1', menu_extra=1),
    Case('menu-plus-17', menu_extra=17), Case('cpu-7900', phi2=7900),
    Case('input-gap-6', input_gap=6),
)

# Held keys are absolute sets. Every change releases keys that are no longer
# requested. This includes the releases needed for the original double Fire.
SCENARIO = (
    ('start', 0, ()),
    ('left-door', 90, ('left',)), ('left-door-stop', 6, ()),
    ('open-door', 6, ('space',)), ('open-door-release', 6, ()),
    ('cross-door', 90, ('left',)), ('new-room', 6, ()),
    ('fire-one', 6, ('space',)), ('fire-one-release', 6, ()),
    ('fire-two', 6, ('space',)), ('trapulator', 12, ()),
    ('map-column-one', 6, ('right',)), ('map-column-one-release', 6, ()),
    ('map-column-two', 6, ('right',)), ('map-column-two-release', 6, ()),
    ('map-row', 6, ('down',)), ('map-row-release', 6, ()),
    ('map-confirm', 18, ('space',)), ('map-view', 60, ()),
    ('map-close', 12, ('space',)), ('map-close-release', 60, ()),
    ('trap-fire-one', 6, ('space',)), ('trap-fire-one-release', 6, ()),
    ('trap-fire-two', 6, ('space',)), ('trap-select', 12, ()),
    ('select-column', 6, ('right',)), ('select-column-release', 6, ()),
    ('select-row', 6, ('down',)), ('select-row-release', 6, ()),
    ('arm-time-bomb', 18, ('space',)), ('bomb-armed', 12, ()),
    ('bomb-wait', 210, ()), ('bomb-detonated', 210, ()),
    ('recovery', 300, ()),
    ('black-move', 30, ('a',)), ('black-stop', 6, ()),
    ('restart-menu', 12, ('f4',)), ('restart-menu-release', 180, ()),
    ('restart-game', 12, ('space',)), ('restart-game-release', 180, ()),
    ('combat-approach', 6, ('right',)), ('combat-approach-stop', 6, ()),
    ('combat-up', 12, ('space', 'up')),
    ('combat-down', 12, ('space', 'down')),
    ('combat-left', 12, ('space', 'left')),
    ('combat-right', 12, ('space', 'right')),
    ('settled', 60, ()),
    ('timeout-fixture', 60, ()), ('timeout-aftermath', 240, ()),
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fixed_seed_image(binary, seed):
    """Bypass the original D20A + zero-page seed mix; retain the actual PRNG."""
    if not 0 <= seed <= 255:
        raise ValueError('Diagnostic game seed must be a byte')
    if binary[0x2ec5:0x2ecb] != SEED_ANCHOR:
        raise ValueError('Original seed entry at $2EC5 differs')
    patched = bytearray(binary)
    patched[0x2ec5:0x2ecb] = bytes((0xa9, seed, 0x4c, 0xd8, 0x2e, 0xea))
    return bytes(patched)


def state_regions(memory):
    if len(memory) != RAM_SIZE:
        raise ValueError('Incomplete RAM snapshot')
    result = {name: memory[address:address+size] for name, (address, size) in REGIONS.items()}
    # $8200 initialisation sets $0345 to room_count-1. $2904 looks up the
    # 41-byte records through $57C9/$57ED. Include only active rooms.
    count = memory[0x345]+1
    if not 1 <= count <= 36:
        raise ValueError(f'Unexpected active room count: {count}')
    for room in range(count):
        address = memory[0x57c9+room] | memory[0x57ed+room] << 8
        if address != 0x7a00 + room*41:
            raise ValueError(f'Unexpected room record address: {address:04X}')
        result[f'room_record_{room:02d}'] = memory[address:address+41]
    return result


def describe(memory, labels):
    regions = state_regions(memory)
    spatial = ['position', 'room'] + [key for key in regions if key.startswith('room_record_')]
    return {
        'candidate_sha256': digest(b''.join(regions.values())),
        'world_and_position_sha256': digest(b''.join(regions[key] for key in spatial)),
        'regions': {key: value.hex() for key, value in regions.items()},
        'diagnostics': {
            'd20a': memory[0xd20a], 'foreground_player': memory[0x76],
            'vbi_count': memory[labels['frame_count']],
            'main_tick': memory[labels['main_tick']],
            'video_stamp': memory[labels['video_stamp']],
        },
    }


def script_for(case):
    lines = [f'run {60+case.launch_extra}', 'press space', 'run 6', 'release space',
             f'run {600+case.menu_extra}', 'peek 0x377 1', 'press right', 'run 6',
             'release right', 'run 30', 'peek 0x34f 2', 'press space', 'run 12',
             'release space', 'run 180', 'peek 0x377 2', 'peek 0x39d 0 0']
    held, elapsed, checkpoints = set(), 0, []
    for index, (name, frames, keys) in enumerate(SCENARIO):
        if index == 1 and case.input_gap:
            # Models late delivery without a synchronized simulation pause.
            # No TCP transport or real network timing is implied.
            lines.append(f'run {case.input_gap}')
            elapsed += case.input_gap
        keys = set(keys)
        if held-keys:
            lines.append('release '+' '.join(sorted(held-keys)))
        if keys-held:
            lines.append('press '+' '.join(sorted(keys-held)))
        held = keys
        if name == 'timeout-fixture':
            # Separate, explicitly marked ending fixture: shorten both clocks
            # to three ticks. This is NOT a naturally completed playthrough.
            lines.append('poke 0xc2 3 3 0 0 0 0')
        if frames:
            lines.append(f'run {frames}')
        elapsed += frames
        lines.append(f'dump 0 {RAM_SIZE}')
        checkpoints.append({'name': name, 'elapsed_video_frames': elapsed})
    return '\n'.join(lines)+'\n', checkpoints


def coverage(states):
    regions = [state['regions'] for state in states]
    initial_room = regions[0]['room']
    bombs = [bytes.fromhex(state['time_bomb'])[2:] for state in regions]
    armed = next((i for i, value in enumerate(bombs) if any(value)), None)
    return {
        'two_human_players': True,  # Enforced by emulator peeks.
        'room_transition': any(state['room'] != initial_room for state in regions),
        'trapulator_opened': any(any(b & 0x80 for b in bytes.fromhex(state['trapulator'])) for state in regions),
        'time_bomb_armed': armed is not None,
        'time_bomb_expired': armed is not None and any(not any(b) for b in bombs[armed+1:]),
        'combat_damage_observed': any(any(bytes.fromhex(state['damage'])) for state in regions),
        'map_opened': any(any(bytes.fromhex(state['map_visible'])) for state in regions),
        'game_over_observed': any(any(bytes.fromhex(state['ending'])) for state in regions),
        'timeout_uses_injected_clock_fixture': True,
        'victory_verified': False,
    }


def run_case(emu, rom, output, case, labels, timeout):
    script, checkpoints = script_for(case)
    output.mkdir(parents=True, exist_ok=True)
    (output/f'{case.name}.script').write_text(script, encoding='utf-8')
    result = subprocess.run(
        [str(emu), str(rom), '--script', '-', '--phi2', str(case.phi2),
         '--seed', str(case.emulator_seed), '--mute'],
        input=script, text=True, capture_output=True, timeout=timeout)
    (output/f'{case.name}.stderr.txt').write_text(result.stderr, encoding='utf-8')
    if result.returncode:
        (output/f'{case.name}.failed.txt').write_text(result.stdout, encoding='utf-8')
        raise RuntimeError(f'{case.name}: emulator failed ({result.returncode}): {result.stderr}')
    data = bytes.fromhex(result.stdout)
    if len(data) != len(checkpoints)*RAM_SIZE:
        raise RuntimeError(f'{case.name}: incomplete trace, {len(data)} bytes')
    (output/f'{case.name}.ram.bin').write_bytes(data)
    states = [dict(checkpoint, **describe(data[i*RAM_SIZE:(i+1)*RAM_SIZE], labels))
              for i, checkpoint in enumerate(checkpoints)]
    report = {'case': asdict(case), 'full_trace_sha256': digest(data),
              'coverage': coverage(states), 'checkpoints': states}
    (output/f'{case.name}.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


def compare(reference, other):
    before, after = reference['checkpoints'], other['checkpoints']
    if [x['name'] for x in before] != [x['name'] for x in after]:
        raise ValueError('Different checkpoint sequences cannot be compared')
    differences = []
    for left, right in zip(before, after):
        changed = {name: {'reference': left['regions'].get(name), 'other': right['regions'].get(name)}
                   for name in sorted(left['regions'].keys() | right['regions'].keys())
                   if left['regions'].get(name) != right['regions'].get(name)}
        if changed:
            differences.append({'checkpoint': left['name'], 'regions': changed})
    return {
        'candidate_state_matches': not differences,
        'world_and_position_matches': all(a['world_and_position_sha256'] == b['world_and_position_sha256']
                                          for a, b in zip(before, after)),
        'full_trace_matches': reference['full_trace_sha256'] == other['full_trace_sha256'],
        'different_checkpoints': len(differences),
        'first_difference': differences[0] if differences else None,
        'differences': differences,
    }


def markdown_report(summary):
    lines = ['# Remote game determinism audit', '',
             f'Shipping ROM SHA-256: `{summary["shipping_rom_sha256"]}`.', '',
             f'Emulator: `{summary["emulator_version"]}`.', '',
             f'Identical-run control: {"PASS" if summary["repeatability_control_passed"] else "FAIL"}.', '',
             '**Sampling:** '+summary['sampling'], '',
             'A difference is a diagnostic finding. A match does not establish lockstep readiness.', '',
             '| ROM | Change | Candidate state | World/position | First differing checkpoint |',
             '| --- | --- | --- | --- | --- |']
    for variant, result in summary['variants'].items():
        for name, comparison in result['comparisons'].items():
            first = comparison['first_difference']
            detail = (first['checkpoint']+' ('+', '.join(first['regions'])+')') if first else '-'
            lines.append(f'| {variant} | {name} | '
                         f'{"MATCH" if comparison["candidate_state_matches"] else "DIFF"} | '
                         f'{"MATCH" if comparison["world_and_position_matches"] else "DIFF"} | {detail} |')
    lines += ['', '## Baseline scenario coverage', '', '| Check | Shipping | Fixed seed |', '| --- | --- | --- |']
    before = summary['variants']['shipping']['baseline_coverage']
    after = summary['variants']['fixed-seed']['baseline_coverage']
    for key in before:
        lines.append(f'| {key} | {before[key]} | {after[key]} |')
    lines += ['', '## Limits', ''] + ['- '+item for item in summary['limitations']]
    lines += ['', 'The fixed-seed ROM is an isolated experiment, not a release. The shipping ROM is unchanged.',
              'The timeout fixture writes six clock bytes at `$00C2` before observing the ending.',
              'Complete comparisons are in `report.json`; per-case scripts, RAM traces and checkpoint metadata',
              'are in `shipping/` and `fixed-seed/`. Each RAM snapshot is 65,280 bytes.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emulator', type=Path, required=True)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    # $A9 reproduces the initial world of the seed-123/8-MHz baseline.
    parser.add_argument('--game-seed', type=int, default=169)
    parser.add_argument('--cases', nargs='+', choices=[case.name for case in CASES])
    parser.add_argument('--jobs', type=int, choices=range(1, 5), default=2)
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    cases_to_run = [case for case in CASES if args.cases is None or case.name in args.cases]
    if not {'baseline', 'repeat'} <= {case.name for case in cases_to_run}:
        parser.error('--cases must include baseline and repeat')
    emu, build, output = args.emulator.resolve(), args.build.resolve(), args.output.resolve()
    if output == build:
        parser.error('--output must be a separate diagnostic directory')
    output.mkdir(parents=True, exist_ok=True)
    labels = {}
    for line in (build/'host.lbl').read_text().splitlines():
        fields = line.split()
        if len(fields) == 3:
            labels[fields[2].lstrip('.')] = int(fields[1], 16)
    original = build/'spy-vs-spy.rp6502'
    original_hash = digest(original.read_bytes())
    experimental = output/'fixed-seed.bin'
    experimental.write_bytes(fixed_seed_image((build/'spy.bin').read_bytes(), args.game_seed))
    seeded = output/'fixed-seed.rp6502'
    pack = subprocess.run([sys.executable, str(Path(__file__).with_name('rp6502.py')),
                           'create', str(experimental), str(build/'title.rp6502'),
                           '-a', '0', '-r', '0xe000', '-o', str(seeded)],
                          text=True, capture_output=True, timeout=30)
    if pack.returncode:
        raise RuntimeError(pack.stdout+pack.stderr)
    version = subprocess.run([str(emu), '--version'], text=True, capture_output=True, timeout=10)
    summary = {
        'format': 1, 'shipping_rom_sha256': original_hash,
        'experimental_rom_sha256': digest(seeded.read_bytes()),
        'emulator_sha256': digest(emu.read_bytes()), 'emulator_version': version.stdout.strip(),
        'fixed_game_seed': args.game_seed,
        'state_regions': {name: {'address': f'{address:04X}', 'size': size}
                          for name, (address, size) in REGIONS.items()},
        'sampling': 'Relative VGA frames after boot script; NOT instruction-aligned logical steps.',
        'limitations': ['Candidate state map is incomplete.', 'No physical hardware or network exercised.',
                        'Matching traces do not prove lockstep determinism.', 'Victory is not validated.',
                        'The timeout ending uses explicitly injected shortened clocks.'],
        'scenario': [{'name': name, 'frames': frames, 'keys': list(keys)} for name, frames, keys in SCENARIO],
        'variants': {},
    }
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(run_case, emu, rom, output/variant, case, labels, args.timeout): (variant, case.name)
                   for variant, rom in [('shipping', original), ('fixed-seed', seeded)] for case in cases_to_run}
        reports = {'shipping': {}, 'fixed-seed': {}}
        for future in as_completed(futures):
            variant, name = futures[future]
            reports[variant][name] = future.result()
            print(f'Captured {variant}/{name}', flush=True)
    repeatable = True
    for variant, cases in reports.items():
        comparisons = {name: compare(cases['baseline'], cases[name]) for name in sorted(cases) if name != 'baseline'}
        repeatable &= comparisons['repeat']['full_trace_matches']
        summary['variants'][variant] = {
            'baseline_coverage': cases['baseline']['coverage'],
            'cases': {name: cases[name]['case'] for name in sorted(cases)},
            'case_coverage': {name: cases[name]['coverage'] for name in sorted(cases)},
            'comparisons': comparisons,
        }
        for name, comparison in comparisons.items():
            print(f"{variant}/{name}: candidate={'MATCH' if comparison['candidate_state_matches'] else 'DIFF'}, "
                  f"world/position={'MATCH' if comparison['world_and_position_matches'] else 'DIFF'}")
    summary['repeatability_control_passed'] = repeatable
    summary['baseline_scenarios_complete'] = all(
        result['baseline_coverage'][key]
        for result in summary['variants'].values() for key in REQUIRED_COVERAGE)
    if digest(original.read_bytes()) != original_hash:
        raise RuntimeError('Shipping ROM changed during audit')
    (output/'report.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    (output/'report.md').write_text(markdown_report(summary), encoding='utf-8')
    print(f'Audit report: {output/"report.json"}')
    if not repeatable:
        raise SystemExit('Identical-run control failed; audit conclusions are unreliable')
    if not summary['baseline_scenarios_complete']:
        raise SystemExit('Baseline scenario coverage is incomplete; inspect report before drawing conclusions')


if __name__ == '__main__':
    main()
