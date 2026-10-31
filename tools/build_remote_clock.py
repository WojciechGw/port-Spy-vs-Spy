"""Build the separate cooperative-clock experiment, leaving R16 unchanged."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

from prepare_spy import patch_cable_extensions, patch_timing, patch_music

ROOT = Path(__file__).resolve().parents[1]


def labels_at(path):
    result = {}
    for line in path.read_text().splitlines():
        fields = line.split()
        if len(fields) == 3:
            result[fields[2].lstrip('.')] = int(fields[1], 16)
    return result


def guarded_patch(memory, address, before, after):
    if memory[address:address+len(before)] != before:
        raise ValueError(f'Patch anchor differs at ${address:04X}')
    if len(before) != len(after):
        raise ValueError('Patch length differs')
    memory[address:address+len(after)] = after


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ca65', default='ca65')
    parser.add_argument('--ld65', default='ld65')
    args = parser.parse_args()
    build, out = args.build.resolve(), args.output.resolve()
    if build == out:
        parser.error('Use a separate output directory for the experiment')
    out.mkdir(parents=True, exist_ok=True)
    shipping_hash = hashlib.sha256((build/'spy-vs-spy.rp6502').read_bytes()).hexdigest()
    for source, obj, defines in [('spy.asm', 'host.o', ['-D', 'REMOTE_CLOCK=1']),
                                  ('remote-clock.asm', 'clock.o', [])]:
        subprocess.run([args.ca65, '-g', *defines, '-I', str(build), '-I', str(ROOT/'src'),
                        '-o', str(out/obj), str(ROOT/'src'/source)], check=True)
    host = out/'host.bin'
    subprocess.run([args.ld65, '-C', str(ROOT/'src/remote-clock.cfg'), '-o', str(host),
                    '-Ln', str(out/'host.lbl'), '-m', str(out/'host.map'),
                    '--dbgfile', str(out/'host.dbg'), str(out/'host.o'), str(out/'clock.o')], check=True)
    labels = labels_at(out/'host.lbl')
    memory = bytearray((build/'original.bin').read_bytes())
    patch_cable_extensions(memory)
    for path, address, size in [(host, 0xc000, 0x1000), (out/'host.bin.tables', 0xd800, 0xbfc),
                                 (out/'host.bin.clock', 0xd500, 0x300), (out/'host.bin.mailbox', 0xd100, 0x100)]:
        data = path.read_bytes()
        if len(data) != size:
            raise ValueError(f'Unexpected segment size for {path}')
        memory[address:address+size] = data
    memory[0xe45c:0xe45f] = b'\x4c'+struct.pack('<H', labels['setvbv'])
    patch_timing(memory, dict(labels, pace_main=labels['remote_pace']))
    patch_music(memory, labels)
    guarded_patch(memory, 0x0c6e, bytes.fromhex('20c52e'), b'\x20'+struct.pack('<H', labels['remote_begin']))
    guarded_patch(memory, 0x0c25, bytes.fromhex('a9008d7703'), b'\x4c'+struct.pack('<H', labels['remote_menu'])+b'\xea\xea')
    guarded_patch(memory, 0x0d2e, bytes.fromhex('a9008d7d03'), b'\x4c'+struct.pack('<H', labels['remote_pause'])+b'\xea\xea')
    # The startup footer is data after its 20-byte config/palette.
    address = labels['footer']+20
    memory[address:address+40] = b' SPY REMOTE CLOCK - EXPERIMENTAL '.center(40)
    (out/'spy.bin').write_bytes(memory[:0xff00])
    subprocess.run([sys.executable, str(ROOT/'tools/rp6502.py'), 'create', str(out/'spy.bin'),
                    str(build/'title.rp6502'), '-a', '0', '-r', '0xe000', '-o', str(out/'remote-clock.rp6502')], check=True)
    if hashlib.sha256((build/'spy-vs-spy.rp6502').read_bytes()).hexdigest() != shipping_hash:
        raise RuntimeError('Shipping ROM changed')
    metadata = {'shipping_rom_sha256': shipping_hash,
                'experimental_rom_sha256': hashlib.sha256((out/'remote-clock.rp6502').read_bytes()).hexdigest(),
                'mailbox': {key: value for key, value in labels.items() if key.startswith('remote_') and 0xd100 <= value < 0xd200}}
    (out/'protocol.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')
    print(f'Built {out/"remote-clock.rp6502"}')


if __name__ == '__main__':
    main()
