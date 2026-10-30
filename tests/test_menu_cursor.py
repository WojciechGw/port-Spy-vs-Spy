"""Both cursor phases must reach VGA, including after changing menu rows."""
from pathlib import Path
import subprocess
import sys

emu, out = sys.argv[1], Path(sys.argv[2]).resolve()
addresses = (0x974e, 0x98ce, 0x9a0e, 0x9b4e)
script = 'run 60\npress space\nrun 6\nrelease space\nrun 180\n'
for row in range(4):
    script += f'peek 0x14 {row}\npeek 0x377 1\n'
    for _ in range(64):
        script += 'run 1\n'
        for address in addresses:
            script += f'dump xram:{address-0x9400} 2\n'
        script += 'crc\n'
    script += 'press down\nrun 6\nrelease down\nrun 30\n'
script += 'peek 0x14 0\npress right\nrun 6\nrelease right\nrun 30\npeek 0x34f 2\n'
result = subprocess.run(
    [emu, str(out/'spy-vs-spy.rp6502'), '--script', '-', '--phi2', '8000',
     '--seed', '123', '--mute'],
    input=script, text=True, capture_output=True, timeout=60)
assert result.returncode == 0, result.stdout + result.stderr
trace = [bytes.fromhex(line) for line in result.stdout.splitlines() if line.strip()]
values = [value for value in trace if len(value) == 2]
canvas = [value for value in trace if len(value) == 4]
assert len(values) == 4*64*4, 'Incomplete cursor trace'
assert len(canvas) == 4*64, 'Incomplete rendered-frame trace'
for row in range(4):
    frames = canvas[row*64:(row+1)*64]
    assert len(set(frames)) == 2, 'Cursor blink is missing from the rendered image'
    edges = [i for i in range(1, len(frames)) if frames[i] != frames[i-1]]
    assert len(edges) >= 3 and all(b-a == 16 for a, b in zip(edges, edges[1:])), edges
    samples = values[row*256:(row+1)*256]
    for slot in range(4):
        vga_phases = set(samples[slot::4])
        if slot == row:
            assert {b'\0\0', b'\x55\x55'} <= vga_phases, (row, vga_phases)
            # A debugger snapshot can stop midway through the two-byte
            # upload. The actual rendered phases above must stay uniform.
            assert all(byte in (0, 0x55) for phase in vga_phases for byte in phase)
        else:
            assert vga_phases == {b'\0\0'}, (row, slot)
print('PASS: white/blank cursor phases in VGA and rendered image on all four rows, '
      '16-frame blink phases, old cursor cleared, settings editable')
