"""Package only the public game files, never the repository or build logs."""
import argparse
from pathlib import Path
import shutil
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--player', type=Path, required=True)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--screenshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    game = args.output / 'spyvsspy'
    game.mkdir(parents=True, exist_ok=True)
    # Read named members instead of extracting arbitrary archive paths.
    with ZipFile(args.player) as player:
        for name in ('rp6502.js', 'rp6502.wasm'):
            (game / name).write_bytes(player.read(name))
    for source, name in (
        (ROOT / 'web/index.html', 'index.html'),
        (ROOT / 'src/help.txt', 'help.txt'),
        (args.rom, 'spy-vs-spy.rp6502'),
        (args.screenshot, 'screenshot.png'),
    ):
        shutil.copyfile(source, game / name)
    (args.output / 'index.html').write_text(
        '<!doctype html>\n<html lang="en"><meta charset="utf-8">\n'
        '<title>Spy vs Spy</title>\n'
        '<meta http-equiv="refresh" content="0; url=spyvsspy/">\n'
        '<a href="spyvsspy/">Play Spy vs Spy</a></html>\n', encoding='utf-8')
    with ZipFile(args.output / 'spyvsspy.zip', 'w', ZIP_DEFLATED) as bundle:
        for name in ('index.html', 'rp6502.js', 'rp6502.wasm',
                     'spy-vs-spy.rp6502', 'screenshot.png', 'help.txt'):
            bundle.write(game / name, name)
    print(f'Web player: {game / "index.html"}')


if __name__ == '__main__':
    main()
