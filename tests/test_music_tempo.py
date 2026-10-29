"""Compare 60 Hz port updates with the original music sequencer at 49.6125 Hz."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'build/python-deps'))
from py65.devices.mpu65c02 import MPU

out = Path(sys.argv[1])
labels = {}
for line in (out/'host.lbl').read_text().splitlines():
    fields = line.split()
    if len(fields) == 3:
        labels[fields[2].lstrip('.')] = int(fields[1], 16)
data = (out/'spy.bin').read_bytes()
memory = list(data)+[0]*(65536-len(data))
port, reference = MPU(memory=memory.copy()), MPU(memory=memory.copy())
assert port.memory[0x7550:0x7553] == [0x20,labels['music_tick']&255,labels['music_tick']>>8]


def call(cpu, address):
    cpu.pc = address
    cpu.sp = 255
    cpu.stPushWord(0x03ff)
    for _ in range(10000):
        if cpu.pc == 0x400:
            return
        cpu.step()
    raise AssertionError('Music routine failed to return')


for cpu in (port,reference):
    cpu.memory[0x383] = 0
    call(cpu,0x3010)  # Original tune initialization.

updates = 0
for frame in range(1,1601):
    call(port,labels['music_tick'])
    expected = frame*1323//1600
    while updates < expected:
        call(reference,0x34ea)
        updates += 1
    assert port.memory[0x384:0x398] == reference.memory[0x384:0x398], frame
    assert port.memory[0xd204:0xd208] == reference.memory[0xd204:0xd208], frame
assert updates == 1323

# Repeated IRQ notifications must not advance VBI twice in one VGA frame.
# Disable the original VBI here to isolate the host's notification filter.
port.memory[0xd40e] = 0
port.memory[labels['video_stamp']] = 250
port.memory[labels['frame_count']] = 0
for tick in range(251,371):
    port.memory[0xffe3] = tick & 255
    for _ in range(3):
        port.a,port.x,port.y = 0x12,0x34,0x56
        port.p = 0x21
        port.sp = 255
        port.stPushWord(0x400)
        port.stPush(port.p)
        port.pc = labels['irq']
        for _ in range(10000):
            if port.pc == 0x400:
                break
            port.step()
        else:
            raise AssertionError('IRQ did not return')
        assert (port.a,port.x,port.y) == (0x12,0x34,0x56)
        assert port.memory[labels['frame_count']] == tick-250
print('PASS: 1600 VGA ticks match 1323 music updates; duplicate IRQs ignored across counter wrap')
