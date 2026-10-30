"""Optional one-time extraction of native build inputs from the inspected XEXs."""
import argparse
import hashlib
import json
from pathlib import Path

from prepare_spy import unpack, analysis_report, SOURCE_SHA as GAME_SHA
from prepare_title import extract, SOURCE_SHA as TITLE_SHA


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('game_xex', type=Path)
    parser.add_argument('title_xex', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    data = args.game_xex.read_bytes()
    memory, steps = unpack(data)
    title = extract(args.title_xex.read_bytes())
    files = {'game.bin': memory, 'title.bin': title}
    manifest = {
        'format': 1,
        'sources': {
            'game': {'filename': args.game_xex.name, 'sha256': GAME_SHA},
            'title': {'filename': args.title_xex.name, 'sha256': TITLE_SHA},
        },
        'files': {name: {'size': len(value), 'sha256': hashlib.sha256(value).hexdigest()}
                  for name, value in files.items()},
        'game_analysis': analysis_report(memory, steps, data),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    for name, value in files.items():
        (args.output/name).write_bytes(value)
    (args.output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print(f'Extracted and fingerprinted native assets in {args.output}')


if __name__ == '__main__':
    main()
