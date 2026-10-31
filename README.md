# Spy vs Spy — Picocomputer 6502

<!-- rp6502
preset: cc65/Release
publish: spyvsspy.zip
-->

A port of the Atari XL/XE action and strategy game for Picocomputer 6502.
Play against the computer or challenge a friend in local two-player mode.
Search rooms, collect the secret items, set traps, and escape before your opponent.

[![Play Spy vs Spy](https://wojciechgw.github.io/port-Spy-vs-Spy/spyvsspy/screenshot.png)](https://wojciechgw.github.io/port-Spy-vs-Spy/spyvsspy/)

**[Play in your browser](https://wojciechgw.github.io/port-Spy-vs-Spy/spyvsspy/)** · **[Download the ROM](https://wojciechgw.github.io/port-Spy-vs-Spy/spyvsspy/spy-vs-spy.rp6502)**

## Running the game

**Browser:** click **Click to play** to start with sound. Keyboard and gamepad
controls are listed below.

**Picocomputer 6502:** download the ROM and run it at **8 MHz**. Use RIA/VGA
firmware with VGA mode 5 custom sprite support; the port was tested with
firmware from the 0.42 series. To upload using the tools in this repository,
place the downloaded ROM in the repository folder and run:

```sh
python tools/rp6502.py run spy-vs-spy.rp6502
```

**Desktop emulator:** open the ROM in
[RP6502-EMU](https://picocomputer.github.io/emu.html) at **8 MHz**. For example:

```sh
rp6502-emu spy-vs-spy.rp6502 --phi2 8000
```

## Starting a game

The splash screen waits about eight seconds. To skip it, press and release
**Space**, **Enter**, **F2**, **Left Shift**, or **A/B/Start** on either gamepad.
Release any key held while launching the game before pressing it again.

1. Use **Up/Down** to select a menu item and **Left/Right** to change it.
2. Set `NUMBER OF PLAYERS` to one or two. For solo play, check
   `COMPUTER IS PLAYER` and use the controls for the human-controlled spy.
3. Press **Space**, **Enter**, **F2**, or gamepad **A/B/Start** to begin.

## Keyboard controls

| Action | Key |
| --- | --- |
| Move the white spy | Arrow keys |
| White spy fire/action | Space |
| Move the black spy | W/A/S/D |
| Black spy fire/action | Left Shift |
| Start game | Enter or F2 |
| Atari SELECT | F3 |
| Return to the menu | F4 |
| Pause during gameplay | Esc |
| Toggle music; sound effects stay on | M |

Fire/action depends on the situation. Use it with the direction controls to
interact with the game.

**Double fire — Trapulator:** quickly press and release your fire button twice
to activate the panel to the right of your playfield. Use the directions to
choose a trap or the map, then press fire once to confirm. The Trapulator is
unavailable during combat when both spies are in the same room.

## Gamepads

The first gamepad controls the white spy; the second controls the black spy.

| Action | Control |
| --- | --- |
| Move / navigate menu | D-pad or left stick |
| Fire/action | A or B |
| Start game | Start |
| Return to the menu | Home |

Keyboard and gamepads can be used together. **Esc** and **M** remain available
on the keyboard when playing with a gamepad. Double fire also works on gamepads.

## Further information

Build instructions, technical details, tests, and the development history
are preserved in [docs/INFO.md](docs/INFO.md).

The original game and its assets belong to their respective owners; this port
does not grant them a new license.
