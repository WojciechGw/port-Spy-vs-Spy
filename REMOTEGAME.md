# Spy vs Spy — online two-player experiment

Network addresses in this document are anonymized examples in `192.168.1.0/24`.
Use your actual addresses at runtime. Raw measurement files are kept locally
and excluded from Git. Loopback addresses retain their technical meaning.

Created: 2026-10-30. Last updated: 2026-10-31, Europe/Warsaw.

## Current status and conclusion

**Network gameplay development is deferred at the measurement stage.** The
current transport and proposed lockstep design have not demonstrated the
responsiveness needed for comfortable Spy vs Spy gameplay. There is no playable
networked version of the game and no deployed Internet relay.

The experiment established that two Wi-Fi Picocomputers can exchange validated
binary data over `AT:`/TCP while updating graphics. However, repeated local-network
tests produced unpredictable round-trip delays of roughly 1–1.5 seconds, with
one earlier series reaching 2.091 seconds. Successful connections and complete
data delivery are therefore insufficient evidence of suitability for this game.

Median RTTs can be good: about 33 ms in several Pico–PC runs. The rare long
stalls are the practical obstacle. With the proposed lockstep design, waiting
for missing input would interrupt movement, combat and trap placement. An input
buffer large enough to conceal those stalls would impose unacceptable control
latency for the intended experience. Neither buffer sizing nor gameplay comfort
has been validated in an integrated network game.

Prediction and rollback might reduce the visible effects of delay, but would
require substantial work on state snapshots, deterministic replay, audio and
memory/CPU use in this port. Their effectiveness here is unproven. That effort
is not justified as a small extension to the existing local game.

The current direction is to:

- Preserve the `remotegame` branch, prototypes, tools and diagnostic records.
- Defer further network gameplay integration and routine connection experiments.
- Focus development on the established local version of the game.
- Retain the networking work as useful groundwork for turn-based games or a
  future transport experiment with demonstrably better latency behavior.

**This is a conclusion about the tested solution, not proof that comfortable
network gaming on Picocomputer is impossible.** The exact cause of the stalls
has not been isolated between RIA firmware handling and the network/Wi-Fi/AP
path. The last discussion about AP topology was left unanswered when the focus
shifted to assessing whether further work was worthwhile.

Chess and other turn-based games would tolerate these delays much more readily.
They would still need connection handling, timeouts and a suitable protocol;
none was implemented as part of this Spy vs Spy experiment.

The preserved R12 release remains the accepted local reference. The normal
build still produces local R16. The historical proposals and unfinished steps
below are retained for reference, not as an active implementation schedule.

## Work completed and supporting reports

Work began on `remotegame` after the user requested implementation of the original
plan. Following the R16 audit, a separate prototype introduced shared game
initialization and a logical clock driven by numbered input from both players.
Network transport was tested independently of the game.

- [R16 determinism audit](docs/remotegame-audit-r16.md): findings and reproduction.
- [Logical-clock prototype](docs/remotegame-clock.md): emulator results, mailbox
  addresses and limitations.
- [AT/TCP hardware probe](docs/remotegame-network-probe.md): Pico–Pico measurements
  and procedures.
- [PC peer and packet captures](docs/remotegame-pc-peer.md): Pico–PC measurements,
  capture setup, interpretation and raw artifact references.

The user confirmed access to **two Wi-Fi Picocomputers**. Hardware tests verified
`AT:` and TCP operation, including runs with a synthetic graphics workload.
Automated emulator and mock tests do not measure Wi-Fi performance.

## Hardware measurements

All RTT figures below are in milliseconds. The five-value format is
**minimum / average / p50 / p95 / maximum**. Each listed series contains
300 completed samples unless stated otherwise. PASS means the protocol exchange
completed correctly; it does not mean gameplay would be comfortable.

### Pico–Pico

The first attempt failed with `WRITE TIMEOUT` on both machines. PROBE 2 fixed
consumption of the end of AT responses and the firmware's listen-port command
syntax. The subsequent successful measurements were:

| Series | Graphics load | RTT min / avg / p50 / p95 / max | Samples over 1000 ms |
| --- | --- | --- | --- |
| PROBE 2, first successful run | 0 | 52 / 74 / 62 / 100 / 1368 | Not counted by this version |
| PROBE 2, PHI2 8000 kHz confirmed | 1 | 59 / 94 / 74 / 120 / 1390 | Not counted by this version |
| PROBE 3 | 1 | 60 / 140 / 76 / 128 / 2091 | 12/300 (4%) |
| PROBE 4 | 1 | 61 / 106 / 78 / 124 / 1434 | 5/300 (1.67%) |

In the PROBE 3 series, the first sample took 75 ms. The long stalls recurred
during the session rather than being confined to connection startup.

PROBE 4 separated local timing phases. DIAL's maximum response wait was 1418 ms,
while LISTEN's local request-handling span never exceeded 31 ms and transmit
phases on either machine never exceeded 3 ms. The second-long delays were not
spent in that measured LISTEN processing interval. These timings alone could
not identify the delayed direction or the underlying cause.

### Pico–PC

The PC peer records every completed sample in CSV/JSON. The Ethernet PC address
used for these tests was `192.168.1.100`; Pico A was associated with
`192.168.1.10` and Pico B with `192.168.1.11`. The initial A/B mapping follows
test order and matching timing patterns in the reports.

| Direction and configuration | RTT min / avg / p50 / p95 / max | Long-delay observations |
| --- | --- | --- |
| A DIAL → PC LISTEN, load=1 | 29 / 56 / 59 / 67 / 82 | No RTT over 200 ms |
| B DIAL → PC LISTEN, load=1 | 29 / 34 / 33 / 40 / 133 | No RTT over 200 ms |
| PC DIAL → A LISTEN | 29.475 / 57.067 / 58.724 / 79.936 / 114.420 | No RTT over 200 ms |
| PC DIAL → B LISTEN, **chunk=1** | 56.232 / 143.984 / 69.091 / 1117.340 / 1597.139 | 16 RTTs over 1000 ms |
| PC DIAL → B LISTEN, **chunk=32** | 29.494 / 42.420 / 32.390 / 39.711 / 1435.388 | 2 RTTs over 1000 ms |

The `chunk=1` run was not a like-for-like comparison. B transmitted one byte
per API call, with a maximum transmit phase of 1556 ms and 43177 writes accepting
no data. Repeating with `chunk=32` restored transmit phases of at most 3 ms,
a local LISTEN span of at most 31 ms and zero empty writes. Nevertheless,
two second-long RTTs remained. Their delay preceded the first response bytes
read on the PC.

The chunk-size issue therefore did not explain the earlier Pico–Pico stalls
with confirmed `chunk=32`. A similar timing profile was reproduced with a
wired PC as the other endpoint.

### Packet captures and confirmed retransmissions

`tools/capture_net_probe.py` combines filtered PktMon capture of TCP/6502 with
the PC probe and saves ETL, PCAPNG and reports together. It requires an
Administrator terminal on Windows; access to the driver was denied even outside
the agent sandbox without elevation.

Initial capture setup needed two fixes: recognizing the actual empty-filter
output and avoiding long filter names that PktMon truncated in its table.
The capture controller now has 11 passing command-mock tests. An elevated
`--check` run verified real start/stop, filter cleanup and PCAPNG conversion
without sending probe traffic. The PowerShell launcher performs this check
before a measurement.

The first real capture reproduced a 1356.634 ms RTT in sample #111, but contained
only 65 distinct requests and four distinct replies out of 300. Neither side
of sample #111 was present. No retransmission conclusions were drawn from that
incomplete trace, despite PktMon reporting no lost events.

A coverage audit was added (`coverage.json`), along with counters recorded before
stopping capture. Logging changed from a 32 MiB circular file to `multi-file`
with a 1024 MiB threshold and conversion of all parts. The cause of the first
incomplete trace was not established. A local `127.0.0.1` traffic check produced
no probe packets in PCAPNG and did not validate physical-interface coverage.
The coverage checker has four synthetic tests; it counts validated full probe
frames inside individual TCP payloads and does not perform stream reassembly.

Subsequent physical captures established complete coverage:

| Capture directory under `build/net-probe-pc` | Result |
| --- | --- |
| `20261031T065330.098468Z-capture` | Incomplete trace; sample #111 RTT 1356.634 ms |
| `20261031T070049.249215Z-capture` | Complete P/R and Q/A; median 32.658 ms, maximum 73.021 ms; no RTT over 200 ms |
| `20261031T071133.224695Z-capture` | Complete coverage; maximum 84.364 ms; no RTT over 200 ms |
| `20261031T071823.386893Z-capture` | Complete coverage; 7/300 RTTs over 1000 ms; maximum 1480.464 ms |

In the first complete, quiet series, one Ethernet component contained 661
packets with no repeated data segments. The original trace recorded each packet
at two components of the same Realtek NIC. Those copies were not retransmissions.

The last series had RTTs of **29.406 / 62.658 / 32.662 / 49.685 / 1480.464 ms**.
Exporting one NIC component confirmed six retransmissions of PC requests after
245–259 ms, distinct from duplicate observations at different capture points.

| Sample | Application RTT | PC request retransmission | Request ACK seen on PC | Reply seen on PC |
| --- | ---: | ---: | ---: | ---: |
| 85 | 1336.486 | None | 2.151 | 1336.234 |
| 89 | 1292.096 | 258.919 | 372.298 | 1291.884 |
| 100 | 1152.483 | 251.167 | 343.290 | 1152.272 |
| 128 | 1105.329 | 248.702 | 345.411 | 1105.114 |
| 134 | 1324.625 | 248.974 | 345.297 | 1324.408 |
| 150 | 1480.464 | 245.223 | 349.634 | 1480.271 |
| 284 | 1043.051 | 248.592 | 352.797 | 1042.887 |

Packet times are milliseconds from the first captured transmission of the
request on the PC. An ACK covering all 32 request bytes establishes reception
by TCP, not when the 6502 application processed them. See
[RFC 9293](https://www.rfc-editor.org/rfc/rfc9293.html#section-3.4).

In sample #85, the request was acknowledged almost immediately, but the reply
arrived about 1.334 seconds later. In the other six slow samples, 690–1131 ms
still elapsed between acknowledgment of the request and arrival of the reply.
The same-run LISTEN report from B showed a maximum local span of 31 ms,
transmit of 3 ms, poll gap of 21 ms and zero empty writes, with `load=1, chunk=32`.

This confirms retransmissions and long waits outside the measured application
processing interval. It does not isolate RIA firmware queues from the Wi-Fi/AP
path. The PC-side trace does not directly show the original transmission of
a reply that failed to arrive. Detailed events and interpretation are retained
in the [PC capture report](docs/remotegame-pc-peer.md), `tcp-events.json` and
`tcp-summary.json` in the last capture directory.

No further AP comparison or RIA instrumentation was performed before the decision
to defer network gameplay work. The earlier proposals for those experiments
remain possible future investigations, not current tasks.

## Original objective

Allow two people to play on two Picocomputers connected over the Internet,
with each person controlling one spy. The initial version could retain the
existing split screen on both displays and the original game rules.

The port already supports local two-player mode and two joysticks. The main
challenge is maintaining consistent game state on two independent machines.

## Network access and hardware context

The documentation reviewed during the original discussion described the
RP6502-PICO-W configuration using a Pico 2 W as RIA with RIA-W firmware.
A 6502 program can open the `AT:` device, which provides Hayes modem emulation
and raw TCP or Telnet connections. RIA runs the network stack.

Source: [RP6502-PICO-W — Modem Emulation](https://picocomputer.github.io/ria_w.html#modem-emulation).

Raw TCP was selected for the first experiment. The local firmware code supports
partial modem reads and writes. A protocol must handle them and measure API
costs so communication does not block game, video or audio servicing. TCP read
boundaries are not game-message boundaries.

The original prerequisites were:

- Confirm Wi-Fi-capable RIA hardware and the appropriate firmware variant.
- Verify `AT:` and the required TCP mode in the installed build.
- Check reads, writes and connection loss under game-like workloads.
- Establish how to test transport in the emulator. The reviewed documentation
  described networking as an RP6502-PICO-W feature; equivalent emulator support
  was not assumed.

Hardware connectivity was subsequently verified as described above. Full
network-game behavior was not tested; the standalone graphics workload is not
an integrated game benchmark. Emulator network tests use mocked modem I/O.

The known R12 hardware reference is firmware Version 0.42, a build after commit
`ad6293c`, with `mtRAM+PCM` mentioned earlier. That reference alone does not
establish support for every proposed networking feature. Recheck documentation
and installed firmware compatibility if work resumes.

## Originally preferred first design: lockstep

Both computers run the same game version and exchange player input assigned to
specific numbered simulation steps. A step executes only when both players'
commands for that step are available.

Proposed message contents:

- Game-step number.
- Movement direction and fire-button state.
- Shared commands such as starting a game or pausing.
- Periodic checksum of relevant game state.

Session setup would also require matching ROM/protocol versions, game settings,
player assignments and shared random-state initialization.

For illustration, a 12-byte message sent 60 times per second would carry
720 bytes of game data per second in each direction before protocol overhead.
This illustrates modest bandwidth demand; it is neither an agreed packet format
nor a measured result.

## Determinism of the existing port

Identical joystick commands do not by themselves guarantee identical gameplay.
The R12 code examined during the initial discussion had these dependencies:

- `pace_main` ties the main loop to the local VGA clock.
- IRQ servicing calls the original game's VBI routine.
- The emulated random register `$D20A` is updated in the interrupt handler.
- DLI routines also affect state used by the game.
- The local loop services players alternately: up to 60 loop iterations per
  second means up to 30 updates per spy.

Independent hardware clocks require a shared logical game step, identical
initialization, controlled randomness and a fixed simulation execution order.

Stopping only the main loop while waiting for network data is insufficient.
Relevant counters and interrupt routines must also follow the synchronization
scheme. Simulation work must be distinguished from video/audio presentation
that can run locally.

Checksums should cover defined logical state at the same step boundary, rather
than all memory including local counters and hardware state. In an initial
prototype, a mismatch should stop the test and preserve diagnostic information.

## Input delay and missing data

The original proposal used an input buffer: execute commands a few steps after
collecting them to give the network time to deliver them.

For example, four to six steps at 60 Hz add about 67–100 ms of control latency.
That was a starting point for experiments, not a chosen value or a promise of
smooth play. Combat responsiveness would need particular attention. The measured
second-long stalls exceed this illustrative buffer by a wide margin.

TCP provides an ordered stream, but retransmission of missing data can delay
subsequent delivery. A basic lockstep implementation would then pause gameplay.
It needs bounded queues, timeouts, a shared pause and session termination after
disconnection. Seamless reconnection to an ongoing match was not part of the
initial scope.

## Design alternatives considered

| Design | Benefit | Main difficulty | Original assessment |
| --- | --- | --- | --- |
| Lockstep | Low bandwidth; both machines execute the original game | Identical simulation and input latency | Preferred for the first experiment; now deferred |
| One machine owns authoritative game state | One definitive outcome for events | Identifying and transferring rooms, traps, items, characters and counters | Requires deeper game-state analysis |
| Prediction and rollback | Prompt response to local input | State snapshots, rewind/replay, audio handling, memory and CPU cost | Reserved for possible later research; not implemented |

The main host-code area had little free space in the R12 map: 135 bytes.
This is a historical R12 figure, not a current free-memory measurement.
Network buffers and additional code need their own memory plan. TCP connectivity
does not remove those constraints or the synchronization cost.

## Proposed relay server

```text
Picocomputer A <-> room server <-> Picocomputer B
```

Both Picocomputers would make outbound connections. A server would match players
using a room code and forward commands; in the lockstep design it would not run
the game. This was intended to reduce port-forwarding and CGNAT difficulties.

Direct LAN communication was the earlier experiment. Relay hosting, session
protocol and room selection were not finalized. No server was deployed or
purchased. A relay is not an established remedy for the observed stalls.

## Original work sequence and present completion state

1. **Determinism without networking.** Feed identical recorded input to two
   instances and compare state at successive steps, covering room changes,
   traps, combat and game completion. The audit and isolated logical-clock
   prototype were implemented; full state coverage and a history-independent
   session reset remain unfinished.
2. **Standalone communication experiment on Pico.** Verify `AT:`/TCP and measure
   latency, stalls, partial transfers and graphics servicing costs. Implemented
   and tested on hardware. The results led to deferring network gameplay work.
3. **Two machines playing over LAN.** Add a fixed input buffer, shared
   initialization, state checks and stopping on connection loss. Not implemented.
4. **Internet play through a relay.** Select buffering from measurements and
   evaluate gameplay comfort, especially combat. Not implemented.
5. **User experience.** Add rooms, spy selection and clear connection messages
   after the underlying design proves suitable. Not implemented.

## Historical discussion and start of implementation

The initial discussion judged the idea technically promising but dependent on
determinism tests and transport measurements. It was not considered a small
change equivalent to connecting a remote joystick. Work was to remain a separate
port variant, preserving `releases/r12/` as the local reference. At that time,
returning to the note did not itself authorize implementation.

The user's later instruction to start according to the plan authorized the
experimental work on `remotegame`; the initial discussion-only restriction was
not an additional approval requirement. The current decision to defer further
network gameplay work supersedes the earlier active work sequence.

Findings after implementation began:

- Identical R16 launches are repeatable in the tested emulator.
- Game startup mixes `$D20A` with zero-page bytes and initializes a five-byte
  generator at `$0368–$036C`, requiring a shared session seed.
- A shared seed alone does not align counters, player-service phases or command
  timing. Shared initialization and a logical game step are also necessary.
- VGA-frame observations are diagnostic. State comparisons need the same logical
  step boundary, independent of where IRQ execution happens.
- Communication measurements remained separate from the game; neither Internet
  gameplay nor a relay server was deployed.

## Logical-clock prototype

The next implementation step introduced shared startup and numbered input
without network transport. `remote-clock` has a separate ROM and CMake target;
normal builds still produce local R16.

The prototype applies both spies' input once after checking the step number.
Missing input stops simulation, including inside the original game's delays
and pause handling. End-of-game processing waits for controller acknowledgment.
Shared settings include the seed, level, AI option and number of exits; player
count is forced to two. Music phase and counters were normalized as well.

Tests cover different start times, 2/7.9/8 MHz operation and gaps in input
delivery. Full results, mailbox addresses and limitations are in the
[logical-clock report](docs/remotegame-clock.md).

Before integrating LAN gameplay, full state checks and a session reset independent
of previous history would still be required. Current comparisons assume fresh
launches of both ROMs followed by the same match history. Transport measurements
were subsequently performed as a separate hardware experiment.

## Standalone tools retained for future use

`net-probe.rp6502`, built by the `net-probe` target, supports listening and dialing,
numbered binary frames with CRC, partial transfers, timeout/cancellation and RTT
measurements with an optional 4 KiB graphics update per frame. It is not linked
to the game.

PROBE 3 added numbers and start times for the five slowest samples, a separate
first-sample result and counts above 200/500/1000 ms. Diagnostics are printed
after measurement, including completed samples from an interrupted run.
PROBE 4 added local transmit/wait phases on DIAL and receive/preparation/transmit
phases on LISTEN, retaining sample numbers without subtracting unsynchronized
clocks on different machines.

`tools/net_probe_peer.py` supplies the PC LISTEN/DIAL endpoint, validates the
protocol and saves all completed samples. Its eight tests include local TCP
and compatibility with frames generated by the actual C implementation.

`tools/capture_net_probe.py` and its PowerShell launcher collect filtered PktMon
traces with the PC test. `tools/audit_probe_capture.py` checks trace coverage.
See the [PC procedure](docs/remotegame-pc-peer.md) for commands, elevation,
filter ownership, interpretation and capture limitations. Early PC peer reports
are under `tools/build/net-probe-pc` because the program was launched from
`tools`; capture directories are under the repository's `build/net-probe-pc`.

These artifacts are retained for reference. No further game integration, full
state checksum, reset redesign, AP comparison or RIA instrumentation is currently
scheduled. Revisiting them should begin with evidence that the chosen transport
can meet the game's latency requirements, rather than treating connection
success as sufficient proof of feasibility.
