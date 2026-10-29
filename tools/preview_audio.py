"""Render offline listening previews from this port's PSG register traces.

These are offline PSG models, not recordings from the host audio device.
The sine, square, noise, sawtooth and triangle waves are implemented. Wave, phase,
envelope and mixer arithmetic follow Picocomputer's BSD-licensed PSG core:
https://github.com/picocomputer/rp6502/blob/main/src/core/aud/psg.c
Copyright (c) 2026 Rumbledethumps, SPDX-License-Identifier: BSD-3-Clause.
The preview omits the host's resampler and analogue output filtering.

License for the adapted PSG model:
Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:
1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software without
   specific prior written permission.
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
import argparse
import json
import math
import struct
import wave
from pathlib import Path

RATE = 49716
GAINS = (256, 204, 168, 142, 120, 102, 86, 73,
         61, 50, 40, 31, 22, 14, 7, 0)
ATTACK_MS = (2, 8, 16, 24, 38, 56, 68, 80,
             100, 250, 500, 800, 1000, 3000, 5000, 8000)
RELEASE_MS = (6, 24, 48, 72, 114, 168, 204, 240,
              300, 750, 1500, 2400, 3000, 9000, 15000, 24000)


def increment(milliseconds):
    return (1 << 24) // (RATE * milliseconds // 1000)


class Oscillator:
    def __init__(self):
        self.phase = self.sample = self.volume = 0
        self.noise1, self.noise2 = 0x67452301, 0xEFCDAB89
        self.envelope = "release"

    def configure(self, data):
        self.freq, self.duty, self.attack, self.decay, self.wave, self.pan, _ = \
            struct.unpack("<H6B", bytes(data))
        self.phase_inc = (self.freq << 32) // (3 * RATE)
        if self.pan & 1:
            if self.envelope == "release":
                self.envelope = "attack"
        else:
            self.envelope = "release"

    def output(self):
        sample = (self.sample * (self.volume >> 12) + 2048) >> 12
        pan = (self.pan if self.pan < 128 else self.pan - 256) >> 1
        if pan == -64:
            return 0, 0
        return sample * (63 - pan), sample * (63 + pan)

    def step(self):
        self.phase = (self.phase + self.phase_inc) & 0xffffffff
        phase=self.phase>>24
        kind=self.wave>>4
        if kind==3:
            half=self.duty>>1
            if phase<128-half or phase>=128+half:
                self.sample=-32767
            elif phase>=128:
                self.sample=32767-((self.phase-0x80000000)>>15)
            else:
                self.sample=(self.phase>>15)-32768
        elif kind==0:
            half=self.duty>>1
            self.sample=round(-math.cos(phase*2*math.pi/256)*32767) \
                if 128-half<=phase<128+half else -32767
        elif phase > self.duty:
            self.sample = -32767
        elif self.wave >> 4 == 4:
            self.noise1 ^= self.noise2
            raw = self.noise2 & 0xffff
            self.sample = raw if raw < 32768 else raw - 65536
            self.noise2 = (self.noise2 + self.noise1) & 0xffffffff
        elif self.wave >> 4 == 1:
            self.sample = 32767
        elif kind==2:
            self.sample=32767-(self.phase>>16)
        else:
            raise ValueError("Unknown PSG waveform")
        target_attack = GAINS[self.attack >> 4] << 16
        target_decay = GAINS[self.decay >> 4] << 16
        if self.envelope == "attack":
            self.volume = min(target_attack, self.volume + increment(ATTACK_MS[self.attack & 15]))
            if self.volume == target_attack:
                self.envelope = "decay"
        elif self.envelope == "decay":
            self.volume = max(0, self.volume - increment(RELEASE_MS[self.decay & 15]))
            if self.volume <= target_decay:
                self.envelope = "sustain"
                if target_decay <= target_attack:
                    self.volume = target_decay
        elif self.envelope == "sustain":
            if target_decay <= target_attack:
                self.volume = target_decay
        else:
            self.volume = max(0, self.volume - increment(RELEASE_MS[self.wave & 15]))


def render(trace, output):
    oscillators = [Oscillator() for _ in range(4)]
    pcm = bytearray()
    peak = clipped = total = 0
    energy = 0
    for frame, entry in enumerate(trace):
        for voice, oscillator in enumerate(oscillators):
            oscillator.configure(entry['psg'][voice*8:voice*8+8])
        # Alternate 828/829 samples so the preview does not drift at 60 Hz.
        count = (frame+1)*RATE//60-frame*RATE//60
        for _ in range(count):
            left = right = 0
            for oscillator in oscillators:
                l, r = oscillator.output()
                left += l
                right += r
                oscillator.step()
            left, right = (left+64)>>7, (right+64)>>7
            peak = max(peak, abs(left), abs(right))
            clipped += int(left < -32768 or left > 32767 or right < -32768 or right > 32767)
            energy += left*left+right*right
            total += 1
            pcm.extend(struct.pack('<hh', max(-32768,min(32767,left)), max(-32768,min(32767,right))))
    with wave.open(str(output), 'wb') as wav:
        wav.setparams((2,2,RATE,total,'NONE','not compressed'))
        wav.writeframes(pcm)
    return dict(frames=len(trace), seconds=total/RATE, peak_before_clamp=peak,
                clipped_samples=clipped, rms=round(math.sqrt(energy/max(1,2*total)),1))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = render(json.loads(args.trace.read_text()), args.output)
    args.output.with_suffix('.stats.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))


