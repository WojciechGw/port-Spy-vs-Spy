"""Execute shared initialization and its settings validation in 65C02 code."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'build/python-deps'))
sys.path.insert(0, str(ROOT/'tools'))
from py65.devices.mpu65c02 import MPU
from build_remote_clock import labels_at, guarded_patch

out = Path(sys.argv[1])
binary = (out/'spy.bin').read_bytes()
labels = labels_at(out/'host.lbl')


def initialize(seed=169, level=1, ai=1, exit_count=1, fill=0x17):
    memory = list(binary)+[0]*(65536-len(binary))
    # Disturb mutable menu/audio/input bytes before shared initialization.
    memory[0x383:0x399] = [fill]*22
    memory[0xc2:0xca] = [fill]*8
    memory[0x399:0x39d] = [fill]*4
    for name, value in [('seed', seed), ('level', level), ('ai', ai), ('exit', exit_count)]:
        memory[labels['remote_'+name]] = value
    cpu = MPU(memory=memory, pc=labels['remote_begin'])
    for _ in range(10000):
        if cpu.pc == 0x2ed8 or memory[labels['remote_status']] == 4:
            return cpu, memory
        cpu.step()
    raise AssertionError('Initialization neither completed nor reported a fault')


for seed, level, ai, exits in [(0, 1, 1, 1), (255, 8, 5, 2), (169, 4, 3, 1)]:
    results = []
    for fill in (0x17, 0xe3):
        cpu, memory = initialize(seed, level, ai, exits, fill)
        assert cpu.pc == 0x2ed8 and cpu.a == seed
        assert memory[0x34c:0x354] == [level-1, level, 2, 2, ai, ai, exits-1, exits]
        assert memory[0xc2:0xca] == [0, 0, 0, 0, memory[0x67a7+level-1], memory[0x67a7+level-1], 0, 0]
        assert memory[labels['remote_active']] == 1
        assert memory[labels['remote_next']:labels['remote_next']+2] == [0, 0]
        assert memory[0x399:0x39d] == [0, 0, 31, 31]
        results.append(memory[0x383:0x399])
    assert results[0] == results[1], 'Menu audio leaked into shared initialization'

for kwargs in ({'level': 0}, {'level': 9}, {'ai': 0}, {'ai': 6}, {'exit_count': 0}, {'exit_count': 3}):
    cpu, memory = initialize(**kwargs)
    assert memory[labels['remote_status']] == 4
    assert memory[labels['remote_error']] == 2
    for _ in range(100):
        cpu.step()
    assert memory[labels['remote_status']] == 4, 'Invalid settings did not stop initialization'

try:
    guarded_patch(bytearray(10), 2, b'\x01', b'\x02')
except ValueError:
    pass
else:
    raise AssertionError('Wrong original patch anchor accepted')

print('PASS: shared seed/settings/audio, settings bounds and fault stop, guarded patch anchors')
