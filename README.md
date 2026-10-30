# Spy vs Spy — Picocomputer 6502

A native port of the supplied `xex/SpyVsSpy.xex` (Atari XL/XE, HOMESOFT).
The original game code runs directly on the 6502 CPU. The host layer provides
VGA graphics, keyboard input, two gamepads, and PSG audio.

**R12 is the reference release.** The user confirmed correct operation in the
emulator and on a physical Picocomputer on October 29, 2026, including the
splash screen and the transition to the working game with music.

## Current build: R16

R14 changes the background around the monitors, side panels, and cables to
black in the menu and during gameplay. It retains the original cabinet and
cable artwork, colors inside the monitors and panels, splash screen, controls,
and R12 music tempo. The background change is a static transparent/black VGA
overlay and adds no work to the game IRQ.
Compared with R13, R14 also removes the remaining background slivers above
and below the right-hand panels. The line beneath the playfields is retained;
the mask over the monitor area is unchanged.

R15 adds a two-pixel segment to the left end of each cable, connecting it to
the corresponding playfield frame. The extension copies the neighboring cable
pattern into the built ROM's graphics and updates the exterior mask to expose
it. The line beneath the playfields and the source XEX files are unchanged.

R16 restores the blinking white underline beneath the selected menu setting.
The cursor's eight glyph bytes are uploaded every VGA frame, so alternating
field uploads cannot repeatedly sample only its blank phase. All four cursor
positions are refreshed to clear the previous selection when moving between
settings. The visible cursor holds each phase for 16 VGA frames (about two
blinks per second), independent of the short menu delays. Gameplay glyphs and
music timing are unchanged.

Build output: **`build/cc65/release/spy-vs-spy-r16.rp6502`** (also available as
`spy-vs-spy.rp6502` in that directory). The footer reads
`SPY R16 MUSIC 49.6125 HZ`. R16 has been checked in the emulator; physical
hardware confirmation is pending. The archived R12 below remains unchanged.

## Reference release

- Preserved ROM: [spy-vs-spy-r12.rp6502](releases/r12/spy-vs-spy-r12.rp6502).
- Checksum file: [SHA256SUMS](releases/r12/SHA256SUMS).
- Release and environment record: [manifest.json](releases/r12/manifest.json).
- ROM size: **100,396 bytes**.
- ROM SHA-256: `7a991407346ef81cfc4edfc5dfea215fbe9128ea2b5411fb87435c83ac98faa4`.

The copy in `releases/r12/` is outside the build directory and is not overwritten
by CMake. Preserve it for comparisons with future versions. A fresh build writes
`build/cc65/release/spy-vs-spy.rp6502` and
`build/cc65/release/spy-vs-spy-r16.rp6502`; these are build outputs, not the archive.
The archived release's menu footer reads `SPY R12 MUSIC 49.6125 HZ`.

Verify the archived ROM from the repository root:

```powershell
Get-FileHash releases/r12/spy-vs-spy-r12.rp6502 -Algorithm SHA256
```

On systems with `sha256sum`, run `sha256sum -c SHA256SUMS` inside `releases/r12/`.

| Component | Recorded reference information |
| --- | --- |
| CPU speed | 8 MHz |
| Local RP6502-EMU executable | `--version`: `Oct 13 2026 13:09:10` |
| Local emulator SHA-256 | `4c901529dc69134be8fac82c8c467feae124ce7773196f3aa27a75aae1991217` |
| Physical RIA/VGA firmware | User-reported [Version 0.42](https://github.com/picocomputer/rp6502/releases/tag/v0.42), build made after commit `ad6293c`; previously reported branch: `mtRAM+PCM` |
| Automated validation | All eight existing tests passed for R12 before archiving |

The emulator fingerprint identifies the local executable used for automated
validation. The user also confirmed operation when launching the emulator
directly. The firmware release and build reference were supplied by the user
for the physical computer on which R12 was confirmed working. The description
"build made after commit `ad6293c`" is retained as reported; it does not assert
that the flashed binaries are identical to the v0.42 release assets or identify
their exact source revision. Separate RIA/VGA binary checksums were not recorded.

## Running

Run the preserved release in the emulator:

```powershell
.\tools\rp6502-emu.exe releases/r12/spy-vs-spy-r12.rp6502 --phi2 8000
```

The emulator executable is not included in the source repository. This workspace
has a local copy in `tools/`. On another machine, use
[RP6502-EMU](https://picocomputer.github.io/emu.html) with support for VGA mode 5
custom sprites. The VS Code F5 configuration explicitly selects 8 MHz and runs
the current build output.

Load and run the preserved ROM on a Picocomputer using the SDK tool:

```powershell
python tools/rp6502.py run releases/r12/spy-vs-spy-r12.rp6502
```

See `python tools/rp6502.py run --help` for serial connection options.
Use **8 MHz**: graphics updates may not keep up at 2 MHz.
To run a newly built version instead, substitute
`build/cc65/release/spy-vs-spy.rp6502` in either command.

## Controls

### Splash screen

The original v2 splash appears for about eight seconds. Press **Space**, **Enter**,
**F2**, **Left Shift**, or **A/B/Start on either gamepad** to skip it.
Release any launch key first: R12 requires a fresh press after the controls have
been released. Release the skip button to enter the menu; holding it cannot
also start a game. If a button is held when the timeout expires, the transition
waits for its release.

### Menu and starting a game

1. Use **Up/Down** or the first gamepad's directions to select a menu item.
2. Use **Left/Right** to change its value, including `NUMBER OF PLAYERS`.
3. For a single-player game, check `COMPUTER IS PLAYER` and use the controls
   for the human-controlled spy.
4. Press **Space / fire**, **Enter**, or **F2** to start. Gamepad **A/B** or
   **Start** provides the corresponding fire/start input.

### Keyboard

| Action | Key |
| --- | --- |
| Move the white spy / joystick 1 | Arrow keys |
| White spy fire/action | Space |
| Move the black spy / joystick 2 | W = up, A = left, S = down, D = right |
| Black spy fire/action | Left Shift |
| Atari START | Enter or F2 |
| Atari SELECT input | F3 |
| Return to the menu (Atari OPTION) | F4 |
| Pause during gameplay | Esc |
| Toggle music on/off | M |

Fire/action is the original game's context-dependent joystick button; the port
does not assign separate keys to individual actions. `M` mutes music only;
sound effects remain active. F3 forwards Atari SELECT rather than opening
a new settings screen.

### Gamepads

| Action | Control |
| --- | --- |
| White spy / joystick 1 | First gamepad |
| Black spy / joystick 2 | Second gamepad |
| Movement | D-pad or left stick |
| Fire/action | A or B |
| Atari START | Start |
| Return to the menu (Atari OPTION) | Home |

Keyboard and gamepad inputs can be used together. Pause and music control
remain available on the keyboard when using a gamepad. Button labels above
refer to the logical A/B/Start/Home inputs reported by the firmware or emulator.

## Release status and limitations

R11 introduced the original splash from `xex/Spy Vs Spy (v2).xex`, including
the palette changes made by its three display-list interrupts (DLIs). Gameplay
still uses `SpyVsSpy.xex`; it has not been replaced with the different v2 engine.

R12 separates splash startup from game initialization. It unmaps the keyboard
and gamepads after the splash, then performs the full R10 startup, including
clearing the emulated Atari registers. The game host code and its addresses
match R10 byte for byte; its tables differ only in the footer version number.
The splash startup occupies a separate region at `$E000–$E3FB`, entered through
the reset vector at `$E000`.

The user reported premature splash dismissal in the emulator and a menu freeze
with a sustained note on hardware in R11, then confirmed correct operation on
both platforms with R12. Music retains the hardware-approved R10 tempo:
**49.6125 sequencer updates per second**.

Automated emulator checks cover boot, menu navigation, two-player selection,
starting a game, movement of both spies, action buttons, gamepad input, return
to the menu, and extended execution without overwriting the checked game code.
They also verify 60 vertical-blank interrupt (VBI) calls per second in the menu.

A complete playthrough to victory has **not** been validated. Colors approximate
the Atari palette. PSG synthesis approximates POKEY and does not reproduce its
noise polynomials or all channel-joining modes exactly. Hardware confirmation
does not replace testing every gameplay situation.

## Graphics and timing

Original four-color 4×8 glyphs are copied to XRAM without conversion. VGA draws
them as small sprites with their width doubled to eight pixels. Glyph images
occupy `$0000–$21FF`; fixed descriptors occupy `$4000–$6A2F`.
Each VSYNC interrupt uploads either the complete upper or lower field, plus
the status row. Both fields refresh within two interrupts, about 33 ms at
60 Hz, without a cache or a queue of changed bytes.

R14 initializes a static 320×200, 1 bpp exterior mask in XRAM `$9000–$AF3F`
after the normal XRAM clear. Its bitmap configuration and transparent/black
palette occupy `$CE80–$CE91`. The mask uses a fill on plane 2 above the glyphs;
the existing player sprites remain on that plane as sprites. A compact mask
is generated from cabinet bounds and the original artwork at build time.

The graphics test uses separate RIA and VGA memory copies. It checks positions,
palettes, glyph format, complete redraws, and recovery within two interrupts
after a simulated lost burst of PIX writes. It does not model physical Pico
bus timing. Duplicate IRQ notifications in the same VGA frame do not run the
original VBI or music update twice.

The foreground loop is limited to 60 iterations per second, or up to 30 updates
per spy because the original game processes them alternately. Waiting uses the
VGA clock, not a CPU cycle count, and does not produce catch-up bursts after
a delay. Menu and longer sequence delays use the same clock, with durations
calculated for a 1.773447 MHz Atari clock and rounded to frames. This is pacing
for the port, not cycle-exact Atari emulation.

## Music and sound effects

The port retains the original melody, all 19 sound-effect sequences, and their
volume envelopes. Four PSG voices handle two music parts and both spies' effects.
Audio registers are sampled immediately after VBI, before the raster handlers,
so the first music voice is no longer accidentally muted on alternate frames.
Held notes also use sequencer state because it does not rewrite the POKEY
registers on every frame. POKEY `$Ax` and `$Ex` modes produce pure tones.

The music sequencer runs at 49.6125 updates per second, 5% above R09's 47.25 Hz,
following listening adjustments on hardware. Redirecting the original call at
`$7550` produces 1323 updates per 1600 VGA ticks, without changing pitch,
gameplay speed, or effect timing.

Pitch is calculated for the PAL clock of 1.773447 MHz. Volume conversion accounts
for the PSG's logarithmic scale and leaves mixing headroom for four simultaneous
voices. Mild stereo placement separates the spies' effects and music parts while
keeping every voice audible in both speakers. Noise modes remain approximations;
the checked game sequences use `AUDCTL=0`.

The audio test writes register traces to `build/cc65/release/audio/`.
Generate listening previews with:

```powershell
python tools/preview_audio.py build/cc65/release/audio/menu.json build/cc65/release/audio/menu.wav
python tools/preview_audio.py build/cc65/release/audio/effects.json build/cc65/release/audio/effects.wav
```

These WAV files come from a software PSG model, not a recording of a physical
Picocomputer. Adjacent `*.stats.json` files report peaks and clipped sample counts.

## Building and testing

Requirements: Python 3, CMake 3.28+, Ninja, and cc65's `ca65` and `ld65` on PATH.
No C runtime or modified cc65 compiler is required. Ordinary builds use only
Python's standard library; they need neither XEX files nor py65 or network access.
The extracted inputs are included in `assets/native/`: `game.bin`, `title.bin`,
and `manifest.json`. Keep these files together; their sizes and SHA-256 hashes
are checked during the build. The resulting ROM is byte-identical to R16 built
from the original XEXs.

```powershell
cmake --preset cc65/Release
cmake --build --preset cc65/Release
```

These commands also work with the entire `xex/` directory absent. The VS Code
Build command uses the same process. The source XEX files are kept only for
optional extraction and comparison against the originals.

The execution tests additionally require py65. Prepare it explicitly, then run
the default suite (which also works without XEX files):

```powershell
cmake --build build/cc65/release --target python-deps
ctest --test-dir build/cc65/release --output-on-failure
```

The explicit `python-deps` target checks the Python interpreter selected by
CMake and installs `requirements-build.txt` into `build/python-deps` only when
needed. Installing missing dependencies requires pip package access. They are
used on the development computer, never included in the ROM. The target is
not part of ordinary builds. Installation into the active Python environment
is also supported. The helper repairs inherited Windows permissions for its
project-local installation.

The nine tests are:

| Test | Coverage |
| --- | --- |
| `native-assets` | Extracted asset integrity, rejection of damaged inputs, parser boundaries, and patch anchors |
| `title-pixels` | Native splash fingerprint, palette, layout, doubled pixels, and PNG preview |
| `timing` | Delay timing, VGA counter wrap, register/flag contracts, and pacing |
| `graphics` | 1080 glyph descriptors, field/status uploads, and lost-write recovery |
| `music-tempo` | Original sequencer state after 1323 updates versus 1600 VGA ticks, including note/envelope state and duplicate IRQ rejection |
| `native-title` | Preloaded XRAM, keyboard and both gamepads, timeout, held buttons, and launch-key release |
| `native-game` | Actual ROM boot, menu, two players, movement, action buttons, gamepad, and return to menu |
| `menu-cursor` | White/blank phases in VGA memory and rendered frames on all four rows, blink timing, clearing the previous selection, and changing a setting |
| `audio` | Both music voices, all 19 effects, simultaneous effects, mute/resume, PSG registers, and mixer headroom |

The four native/emulator tests are registered when CMake finds `rp6502-emu`
in `tools/` or on PATH. Set `-DSPY_EMULATOR=/path/to/rp6502-emu` to specify it.
Gameplay checks drive keyboard/gamepad input without compiled-in test hooks
or setting character positions. Audio checks additionally submit effect IDs
through the original game's request queue.

Generated screenshots in the build directory are `test-title.png`,
`test-game.png`, and `test-menu.png`. `title.png` is the splash extracted from
the saved native asset. CI checks out the project without `xex/`, builds before
installing py65, and runs tests that do not require the local emulator;
it does not overwrite the archived reference release.

### Optional XEX extraction

Only regeneration of `assets/native/` requires the two inspected XEX files and
py65. From the repository root:

```powershell
python tools/ensure_build_deps.py
python tools/extract_assets.py xex/SpyVsSpy.xex "xex/Spy Vs Spy (v2).xex" assets/native
```

This executes the original depacker and splash DLIs, checks the source hashes,
and writes both unpatched assets and their manifest. Do not substitute a built
`spy.bin` for `game.bin`: it already contains host patches.

To additionally verify extraction against the original XEXs, including every
splash pixel and DLI palette, enable the two optional tests:

```powershell
cmake --preset cc65/Release -DSPY_TEST_XEX=ON
ctest --test-dir build/cc65/release --output-on-failure -R "xex-original|title-original"
cmake --preset cc65/Release -DSPY_TEST_XEX=OFF
```

## Project layout

- `releases/r12/`: preserved reference ROM, checksum, and validation/environment record.
- `assets/native/`: extracted game and splash inputs, checksums and provenance.
- `tools/extract_assets.py`: optional regeneration of those inputs from the XEXs.
- `tools/prepare_spy.py`: native asset validation, generated tables/mask, and
  assembly of the patched memory image; also contains the optional XEX depacker.
- `tools/prepare_title.py`: preparation of the saved 320×200, 4 bpp VGA splash
  and PNG preview; also contains the optional XEX extractor.
  The ROM preloads the image and configuration into XRAM `$0000–$807B`.
  After the splash, the host clears XRAM and reuses it for gameplay graphics.
- `src/spy.asm`, `src/ria.inc`: hardware support without borrowing game zero-page variables.
- `src/spy.cfg`: host at `$C000–$CFFF`, tables at `$D800–$DFFF`, and startup/splash
  at `$E000–$E3FB`. `$E3FC–$E3FF` remains the overlay loader's scratch space.
- `build/cc65/release/analysis.json`: segment and overlay map.
- `tests/`: source checks and execution tests.

The original game entry is `$0C00`. The RP6502 interrupt calls the VBI and nine
DLIs, mapping their palette and sprite changes to VGA bands. The Atari SETVBV
service at `$E45C` is redirected to the host. The overlays fit into Picocomputer
RAM without Atari ROM banking.

After the game takes over, address `$14` is the menu cursor, not the OS clock.
The port deliberately does not increment it.

Hardware documentation: [VGA](https://picocomputer.github.io/vga.html),
[RIA](https://picocomputer.github.io/ria.html).
The source XEX files remain unchanged. The game and its original assets belong
to their respective owners; the port does not grant them a new license.
