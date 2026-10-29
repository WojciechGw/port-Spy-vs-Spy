"""Drive the shipping ROM at 8 MHz; assertions use original game state.

No test hooks or state pokes are compiled into the game. A fixed seed makes
the test reproducible, including on RAM initially filled with random bytes.
"""
from pathlib import Path
import subprocess
import sys

emu, out = sys.argv[1], Path(sys.argv[2]).resolve()
labels = {}
for line in (out/'host.lbl').read_text().splitlines():
    fields = line.split()
    if len(fields) == 3:
        labels[fields[2].lstrip('.')] = int(fields[1], 16)
frame = labels['frame_count']
script = f'''
run 60
press space
run 6
release space
run 600
peek xram:0xe414 0x53 0x50 0x59 0x20 0x52 0x31 0x32
peek 0x14 0
peek 0x377 1
peek 0xc00 0x78 0xa9 0 0x8d 0x0e 0xd4 0xd8 0xa2 0xff 0x9a 0xa2 0x12
dump {frame} 1
run 60
dump {frame} 1
press right
run 6
release right
run 30
peek 0x34f 2
press space
run 12
release space
run 180
peek 0x377 2
peek 0x39d 0 0
dump 0xb69b 2
run 60
dump 0xb69b 2
dump 0x31 8
press up
run 60
release up
run 6
dump 0x31 8
press a
run 60
release a
run 6
dump 0x31 8
pad 0 connect western
pad 0 press right
run 30
peek 0xd300 0xf7
dump 0x31 8
pad 0 release right
run 6
peek 0xd300 0xff
press space lshift
run 6
peek 0xd010 0 0
release space lshift
run 6
peek 0xd010 1 1
run 1800
peek 0x377 2
peek 0xc00 0x78 0xa9 0 0x8d 0x0e 0xd4 0xd8 0xa2 0xff 0x9a 0xa2 0x12
shot "{(out/'test-game.png').as_posix()}"
press f4
run 12
release f4
run 180
peek 0x377 1
run 600
peek 0xc00 0x78 0xa9 0 0x8d 0x0e 0xd4 0xd8 0xa2 0xff 0x9a 0xa2 0x12
shot "{(out/'test-menu.png').as_posix()}"
'''
result = subprocess.run([emu, str(out/'spy-vs-spy.rp6502'), '--script', '-',
                         '--phi2', '8000', '--seed', '123', '--mute'],
                        input=script, text=True, capture_output=True, timeout=90)
if result.returncode:
    raise SystemExit(result.stdout + result.stderr)
values = [bytes.fromhex(line) for line in result.stdout.splitlines() if line.strip()]
assert len(values) == 8, f'Emulator stopped early: {result.stdout} {result.stderr}'
assert (values[1][0]-values[0][0]) % 256 == 60, 'VBI did not keep 60 Hz in menu'
idle_before, idle_after = [int.from_bytes(v, 'little') for v in values[2:4]]
# This original attract-mode countdown decrements once per foreground loop.
# It observes game execution rather than a counter in the new pacing code.
assert (idle_before-idle_after) % 65536 == 60, 'Foreground loop is not paced at 60 Hz'
initial, up, left, pad = values[4:]
assert up[0] < initial[0], 'Player one did not move up'
assert left[5] < up[5], 'Player two did not move left'
assert pad[4] > left[4], 'Gamepad did not move player one right'
print('PASS: boot, idle menu, 60 Hz, two players, keyboard, gamepad, fire, long play, return to menu')
