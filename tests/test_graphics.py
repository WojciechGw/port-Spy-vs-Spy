"""Run the linked font renderer with separate RIA and VGA XRAM copies.

The desktop emulator shares XRAM. This model can lose a PIX write while
the local RIA copy still reads correctly, as a physical-link fault would do.
It tests recovery, not a claim to emulate Pico bus timing.
"""
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


class Portals(list):
    def __init__(self, data):
        super().__init__(data)
        self.ria = bytearray(65536)
        self.vga = bytearray(65536)
        self.address = [0, 0]
        self.step = [1, 1]
        self.address_reads = 0
        self.drop = set()
        self.dropped = 0
        self.allow_config = False

    def __getitem__(self, addr):
        if isinstance(addr, int) and 0xffe4 <= addr <= 0xffeb:
            port, reg = divmod(addr-0xffe4, 4)
            if reg == 0:
                result = self.ria[self.address[port]]
                self.address[port] = (self.address[port]+self.step[port]) & 65535
                return result
            if reg >= 2:
                self.address_reads += 1
                return (self.address[port] >> (8*(reg-2))) & 255
        return super().__getitem__(addr)

    def __setitem__(self, addr, value):
        if isinstance(addr, int) and 0xffe4 <= addr <= 0xffeb:
            port, reg = divmod(addr-0xffe4, 4)
            if reg == 0:
                target = self.address[port]
                assert target < 0x2200 or (self.allow_config and 0x4000 <= target < 0x6a30), hex(target)
                self.ria[target] = value
                if target in self.drop:
                    self.drop.remove(target)
                    self.dropped += 1
                else:
                    self.vga[target] = value
                self.address[port] = (target+self.step[port]) & 65535
            elif reg == 1:
                self.step[port] = value if value < 128 else value-256
            elif reg == 2:
                self.address[port] = (self.address[port] & 0xff00) | value
            else:
                self.address[port] = (self.address[port] & 255) | value << 8
        super().__setitem__(addr, value)


binary = (out/'spy.bin').read_bytes()
mem = Portals(list(binary)+[0]*(65536-len(binary)))
cpu = MPU(memory=mem)
cycle_counts = []
source = bytearray((i*37+(i>>8)*53) & 255 for i in range(0x2400))
mem[0x9400:0xb800] = source


def call(address):
    cpu.pc = address
    cpu.sp = 0xff
    cpu.stPushWord(0x03ff)
    start = cpu.processorCycles
    for _ in range(200000):
        if cpu.pc == 0x0400:
            return cpu.processorCycles-start
        cpu.step()
    raise AssertionError('Graphics routine failed to return')


mem.allow_config = True
call(labels['configure_glyphs'])
mem.allow_config = False
for band in range(9):
    for glyph in range(120):
        p = 0x4000 + band*1200 + glyph*10
        d = mem.vga[p:p+10]
        words = [int.from_bytes(d[i:i+2],'little') for i in (0,2,4,6)]
        assert words == [glyph%40*8,20+band*24+glyph//40*8,
                         band*1024+glyph*8,0xc800+band*32], (band,glyph,words)
        assert d[8:] == bytes([0x10,0x41]), 'Glyph size, depth or horizontal doubling'


def render():
    cycle_counts.append(call(labels['fonts']))


def matches():
    return mem.vga[:0x2200] == source[:0x2200]


for _ in range(2):
    render()
assert matches(), 'Initial glyph data differs from original Atari bytes'

# Dense erases and room changes must meet the same two-frame deadline.
for start_half in (0,16):
    mem[labels['font_page']] = start_half
    source = bytearray(b ^ 255 for b in source)
    mem[0x9400:0xb800] = source
    render()
    assert mem.vga[0x2000:0x2200] == source[0x2000:0x2200], 'Status did not refresh immediately'
    render()
    assert matches(), ('Dense redraw/erase missed deadline',start_half)

# Losing an entire field transfer must recover without further source changes.
mem[labels['font_page']] = 0
source = bytearray(b ^ 255 for b in source)
mem[0x9400:0xb800] = source
mem.drop = set(range(4096))
render()
assert mem.dropped == 4096 and not mem.drop
assert not matches()
render()
render()
assert matches(), 'Lost erase burst remains after two IRQs'
assert mem.address_reads == 0
assert max(cycle_counts) < 55000, 'Graphics leaves too little CPU time at 8 MHz'
print('PASS: 1080 glyph descriptors, native 2bpp doubling, status each IRQ, both fields within 2 IRQs; '
      f'max font cycles={max(cycle_counts)}')
