"""Shipping ROM: preloaded title, keyboard/pad dismissal, held input, timeout."""
from pathlib import Path
import subprocess
import sys

emu, out = sys.argv[1], Path(sys.argv[2]).resolve()
labels = {}
for line in (out/'host.lbl').read_text().splitlines():
    fields = line.split()
    if len(fields) == 3:
        labels[fields[2].lstrip('.')] = int(fields[1], 16)
active = labels['title_active']
image = (out/'title.bin').read_bytes()
cases = [
    ('space', ['press space'], ['release space']),
    ('enter', ['press enter'], ['release enter']),
    ('pad-fire', ['pad 0 connect western', 'pad 0 press a'], ['pad 0 release a']),
    ('pad-start', ['pad 1 connect western', 'pad 1 press start'], ['pad 1 release start']),
    ('timeout', [], []),
    ('launch-enter', ['press enter'], ['release enter']),
    ('launch-pad', ['pad 0 connect western', 'pad 0 press a'], ['pad 0 release a']),
]
for name, press, release in cases:
    script = press.copy() if name.startswith('launch-') else []
    script += ['run 60', f'peek {active} 1', f'dump xram:0 {len(image)}']
    if name.startswith('launch-'):
        # Releasing the key used to launch the application must not dismiss
        # the title. A later, fresh press does dismiss it.
        script += release + ['run 60', f'peek {active} 1']
    if name == 'space':
        script += [f'shot "{(out/"test-title.png").as_posix()}"']
    if press:
        script += press + ['run 600', f'peek {active} 1'] + release + ['run 180']
    else:
        script += ['run 400', f'peek {active} 1', 'run 120']
    script += [f'peek {active} 0', 'peek 0x377 1', 'peek 0x14 0',
               'peek xram:0xe414 0x53 0x50 0x59 0x20 0x52 0x31 0x36']
    result = subprocess.run([emu, str(out/'spy-vs-spy.rp6502'), '--script', '-',
                             '--phi2', '8000', '--seed', '123', '--mute'],
                            input='\n'.join(script)+'\n', text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, (name, result.stdout, result.stderr)
    assert bytes.fromhex(result.stdout) == image, (name, 'XRAM title differs from original asset')
    print(f'PASS: title -> menu ({name}), no accidental gameplay')
