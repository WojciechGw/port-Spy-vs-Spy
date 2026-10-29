"""Execute the linked delay hooks at different CPU clocks and across VSYNC wrap."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'build/python-deps'))
sys.path.insert(0, str(ROOT/'tools'))
from py65.devices.mpu65c02 import MPU
from prepare_spy import delay_ticks

out = Path(sys.argv[1])
data = (out/'spy.bin').read_bytes()
labels = {}
for line in (out/'host.lbl').read_text().splitlines():
    fields = line.split()
    if len(fields) == 3:
        labels[fields[2].lstrip('.')] = int(fields[1], 16)


class VideoClock(list):
    def __getitem__(self, address):
        if address == 0xffe3:
            return (250 + cpu.processorCycles * 60 // hz) & 255
        return super().__getitem__(address)


for hz in (2_000_000, 8_000_000):
    for name, count in [('delay_short',20), ('delay_short',0), ('delay_long',1)]:
        memory = VideoClock(list(data) + [0] * (65536-len(data)))
        cpu = MPU(memory=memory, pc=labels[name])
        cpu.a = count if name == 'delay_long' else 0x42
        cpu.x, cpu.y, cpu.p = 0x53, count, 0x29  # exercise carry and decimal preservation
        cpu.stPushWord(0x01ff)
        while cpu.pc != 0x0200:
            cpu.step()
            assert cpu.processorCycles < hz, 'Delay hung'
        ticks = delay_ticks(count, name == 'delay_long')
        elapsed_ticks = cpu.processorCycles * 60 / hz
        assert ticks <= elapsed_ticks < ticks + 0.02, (hz, name, elapsed_ticks)
        assert cpu.x == 0x53 and cpu.y == count
        assert cpu.a == (0 if name == 'delay_long' else 0x42)
        assert cpu.p & 0x09 == 0x09, 'Carry/decimal flags were lost'

# A frame missed by a long operation grants one update, not a catch-up burst.
hz = 8_000_000
memory = VideoClock(list(data) + [0] * (65536-len(data)))
cpu = MPU(memory=memory, pc=labels['pace_main'])
memory[labels['main_tick']] = 240
memory[0x381] = 0x80
cpu.x, cpu.y = 0x12, 0x34
for iteration in range(2):
    cpu.pc = labels['pace_main']
    cpu.stPushWord(0x01ff)
    while cpu.pc != 0x0200:
        cpu.step()
        assert cpu.processorCycles < hz, 'Pacing hung'
    if iteration == 0:
        assert cpu.processorCycles < 1000, 'First update should consume the missed tick immediately'
    else:
        assert 1 <= cpu.processorCycles * 60 / hz < 1.02, 'Backlog caused an extra update'
    assert (cpu.a, cpu.x, cpu.y) == (0x80,0x12,0x34)
    assert cpu.p & 0x80, 'Displaced LDA flags were not restored'
print('PASS: delays at 2/8 MHz, VSYNC wrap, register/flag contracts, no catch-up burst')
