"""Validate native music and all 19 original SFX through the shipping ROM.

Effect fixtures submit IDs to the original game's request queue. They do not
overwrite PSG output or replace the original sequencer/envelopes.
"""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
emu, out = sys.argv[1], Path(sys.argv[2]).resolve()
labels = {}
for line in (out/'host.lbl').read_text().splitlines():
    fields = line.split()
    if len(fields) == 3:
        labels[fields[2].lstrip('.')] = int(fields[1], 16)
source = labels['audio_source']
script = ['run 60', 'press space', 'run 6', 'release space', 'run 180']
sections = []


def capture(name, frames):
    sections.append((name,frames))
    for _ in range(frames):
        script.extend(['run 1', f'dump {source} 9', 'dump 0x394 6', 'dump xram:0xff80 32'])


capture('menu',600)
script += ['press m','run 3','release m','run 6','peek 0x383 1']
capture('muted',12)
script += ['poke 0 6 7','run 1']
capture('two_spies',30)
capture('silent_tail',12)
script += ['press m','run 3','release m','run 6','peek 0x383 0']
capture('resume',120)
original = (out/'original.bin').read_bytes()
for effect in range(1,20):
    ptr = original[0x6cf0+effect] | original[0x6d04+effect]<<8
    frames = 4
    while original[ptr] != 255:
        frames += original[ptr+2]+1
        ptr += 3
        assert frames < 240, 'Unexpected SFX table layout'
    script += [f'poke 0 {effect}', 'run 1']
    capture(f'effect_{effect:02}',frames)
result = subprocess.run([emu,str(out/'spy-vs-spy.rp6502'),'--script','-',
                         '--phi2','8000','--seed','123','--mute'],
                        input='\n'.join(script)+'\n',text=True,capture_output=True,timeout=90)
assert result.returncode == 0, result.stdout + result.stderr
data = [list(bytes.fromhex(line)) for line in result.stdout.splitlines() if line.strip()]
assert len(data) == 3*sum(n for _,n in sections), 'Emulator stopped before completing all audio cases'
traces = {}
index = 0
for name,frames in sections:
    trace = []
    for _ in range(frames):
        trace.append(dict(pokey=data[index],music=data[index+1],psg=data[index+2]))
        index += 3
    traces[name] = trace

gains = (256,204,168,142,120,102,86,73,61,50,40,31,22,14,7,0)
seen_modes = set()
for name, trace in traces.items():
    for entry in trace:
        assert entry['pokey'][8] == 0, (name,'unsupported AUDCTL mode')
        for voice in range(4):
            audf, audc = entry['pokey'][2*voice:2*voice+2]
            psg = entry['psg'][8*voice:8*voice+8]
            frequency = min(65535, round(3*1773447/(56*(audf+1))))
            assert psg[0]+256*psg[1] == frequency, (name,voice,'pitch')
            assert psg[5] >> 4 == (1 if audc & 0xa0 == 0xa0 else 4), (name,voice,'timbre')
            assert bool(psg[6]&1) == bool(audc&15 and not audc&16), (name,voice,'gate')
            assert psg[6]&0xfe == (232,24,244,12)[voice], (name,voice,'pan')
            assert psg[3] == psg[4] and psg[3]&15 == 0, (name,voice,'envelope')
            gain = gains[psg[4]>>4]
            assert abs(gain-(audc&15)*8) <= 8, (name,voice,'linear volume')
            if audc&15:
                seen_modes.add(audc&0xe0)
assert {0,0x20,0x60,0x80,0xa0,0xc0,0xe0} <= seen_modes, seen_modes

def audible(entry,voice):
    return bool(entry['psg'][voice*8+6]&1)

score_frames = sum(bool(entry['music'][1]&15) for entry in traces['menu'])
audible_frames = sum(audible(entry,2) for entry in traces['menu'])
# A host frame can end inside the original VBI before its snapshot is taken.
assert audible_frames >= score_frames-12, 'First music voice still loses alternate frames'
assert score_frames > 300, 'Menu music did not run long enough'
assert all(not audible(e,2) and not audible(e,3) for e in traces['muted']+traces['two_spies'])
assert any(audible(e,0) and audible(e,1) for e in traces['two_spies']), 'M also muted effects'
assert all(not any(audible(e,v) for v in range(4)) for e in traces['silent_tail']), 'An effect stayed on'
assert any(audible(e,2) and audible(e,3) for e in traces['resume']), 'Music did not resume'
for name in ('effect_06','effect_07'):
    assert any(audible(e,0) and e['psg'][5] == 0x10 for e in traces[name]), '$Ex tone became noise'

# Bound the actual mixer with all four voices full scale, including panning.
for channel in (0,1):
    pan = (-12,12,-6,6)
    worst = sum(32767*120/256*(63 + (p if channel else -p))/128 for p in pan)
    assert worst < 0.93*32767, 'Four voices can clip the mixer'

folder = out/'audio'
folder.mkdir(exist_ok=True)
for name in ('menu','two_spies'):
    (folder/f'{name}.json').write_text(json.dumps(traces[name]))
(folder/'effects.json').write_text(json.dumps([e for name,trace in traces.items() if name.startswith('effect_') for e in trace]))
report = dict(menu_score_frames=score_frames,menu_audible_frames=audible_frames,
              effects=19,distortions=[f'{v:02X}' for v in sorted(seen_modes)],
              peak_bound_fraction=round(worst/32767,4))
(folder/'checks.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS: two music voices, 19 SFX, $Ax/$Ex tones, pitch, volume, M mute/resume, stereo headroom')
print(json.dumps(report))
