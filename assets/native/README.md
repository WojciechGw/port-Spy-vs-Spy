# Native build inputs

These extracted assets replace the XEX files in the normal build:

- `game.bin`: 65,536-byte Atari memory image after the inspected HOMESOFT
  depacker reaches `$0C00`. It contains the original game, graphics, music and
  overlays, before any Picocomputer patches.
- `title.bin`: 32,892-byte native VGA splash image, palette and configuration,
  extracted from the loading screen in `Spy Vs Spy (v2).xex`.
- `manifest.json`: asset sizes and SHA-256 hashes, original XEX fingerprints,
  and the original segment/overlay analysis.

Keep all three files together. The build verifies both binary assets against
the manifest and applies the current host patches to copies in the build
directory. No XEX files, py65, or network access are needed to build the ROM.

To regenerate these inputs from the originals, see the optional extraction
instructions in the repository's [technical documentation](../../docs/INFO.md#optional-xex-extraction).
The game and its original assets retain their original ownership and licensing.
