"""Build the standalone modem probe with the RP6502 cc65 runtime."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def compile_program(compiler, target, sources, output, defines=None):
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    objects = []
    for source in sources:
        source = Path(source).resolve()
        obj = output.parent/(output.stem+'-'+source.stem+'.o')
        flags = (defines or {}).get(source.name, [])
        subprocess.run([str(compiler), '-t', target, '-O', '-g', *flags, '-I', str(ROOT/'src/net-probe'),
                        '-c', '-o', str(obj), str(source)], check=True)
        objects.append(str(obj))
    subprocess.run([str(compiler), '-t', target, '-o', str(output), '-m', str(output.with_suffix('.map')),
                    '-Ln', str(output.with_suffix('.lbl')), *objects], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cl65', default='cl65')
    args = parser.parse_args()
    out = args.output.resolve()
    compile_program(args.cl65, 'rp6502', [ROOT/'src/net-probe'/name for name in ('main.c', 'protocol.c', 'pico.c')], out/'net-probe.bin')
    subprocess.run([sys.executable, str(ROOT/'tools/rp6502.py'), 'create', str(out/'net-probe.bin'),
                    '-a', '0x200', '-r', '0x200', '-o', str(out/'net-probe.rp6502')], check=True)


if __name__ == '__main__':
    main()
