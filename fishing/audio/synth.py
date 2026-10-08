"""Tiny stdlib synthesiser: oscillators, noise, envelopes and plucked strings.

Signals are lists of floats in -1..1 at ``rate`` Hz (mono). ``to_bytes`` turns
one into interleaved int16 frames for the mixer's channel count; a buffer in
the wrong format plays at the wrong speed.
"""
from __future__ import annotations

import array
import math
import random

Signal = list[float]


class Synth:
    def __init__(self, rate: int = 44100, channels: int = 2, seed: int = 7) -> None:
        self.rate = rate
        self.channels = channels
        self.rng = random.Random(seed)

    # -- building blocks ---------------------------------------------------
    def n(self, dur: float) -> int:
        return max(1, int(dur * self.rate))

    def silence(self, dur: float) -> Signal:
        return [0.0] * self.n(dur)

    def tone(
        self, freq: float, dur: float, vol: float = 0.5, wave: str = "sine",
        freq_end: float | None = None, attack: float = 0.004, release: float = 0.04,
        duty: float = 0.5, vibrato: float = 0.0, vibrato_hz: float = 6.0,
    ) -> Signal:
        n = self.n(dur)
        out = [0.0] * n
        phase = 0.0
        f_end = freq if freq_end is None else freq_end
        for i in range(n):
            p = i / n
            f = freq * (f_end / freq) ** p if f_end > 0 and freq > 0 else freq + (f_end - freq) * p
            if vibrato:
                f *= 1 + vibrato * math.sin(2 * math.pi * vibrato_hz * i / self.rate)
            phase = (phase + f / self.rate) % 1.0
            if wave == "sine":
                s = math.sin(2 * math.pi * phase)
            elif wave == "square":
                s = 1.0 if phase < duty else -1.0
            elif wave == "triangle":
                s = 4 * abs(phase - 0.5) - 1
            else:  # saw
                s = 2 * phase - 1
            out[i] = s * vol
        return self.envelope(out, attack, release)

    def noise(
        self, dur: float, vol: float = 0.5, attack: float = 0.002, release: float = 0.05,
        lowpass: float = 1.0, highpass: float = 0.0, lowpass_end: float | None = None,
    ) -> Signal:
        """White noise through one-pole filters (0..1 coefficients; 1 = no filtering)."""
        n = self.n(dur)
        out = [0.0] * n
        lp = hp_prev_in = hp_prev_out = 0.0
        lp_end = lowpass if lowpass_end is None else lowpass_end
        for i in range(n):
            a = lowpass + (lp_end - lowpass) * i / n
            x = self.rng.uniform(-1.0, 1.0)
            lp += a * (x - lp)
            y = lp
            if highpass > 0:
                hp = highpass * (hp_prev_out + y - hp_prev_in)
                hp_prev_in, hp_prev_out = y, hp
                y = hp
            out[i] = y * vol
        return self.envelope(out, attack, release)

    def pluck(self, freq: float, dur: float, vol: float = 0.6, decay: float = 0.996) -> Signal:
        """Karplus-Strong plucked string."""
        period = max(2, int(self.rate / freq))
        buf = [self.rng.uniform(-1.0, 1.0) for _ in range(period)]
        n = self.n(dur)
        out = [0.0] * n
        for i in range(n):
            j = i % period
            nxt = buf[(i + 1) % period]
            out[i] = buf[j] * vol
            buf[j] = decay * 0.5 * (buf[j] + nxt)
        return self.envelope(out, 0.001, 0.05)

    # -- shaping and combining ---------------------------------------------------
    def envelope(self, sig: Signal, attack: float, release: float) -> Signal:
        n = len(sig)
        a = min(n, int(attack * self.rate))
        r = min(n, int(release * self.rate))
        for i in range(a):
            sig[i] *= i / a
        for i in range(r):
            sig[n - 1 - i] *= i / r
        return sig

    def decay(self, sig: Signal, half_life: float) -> Signal:
        k = math.log(2) / max(1e-4, half_life * self.rate)
        return [s * math.exp(-k * i) for i, s in enumerate(sig)]

    @staticmethod
    def mix(*signals: Signal) -> Signal:
        n = max(len(s) for s in signals)
        out = [0.0] * n
        for s in signals:
            for i, v in enumerate(s):
                out[i] += v
        return out

    def seq(self, *parts: Signal | float) -> Signal:
        """Concatenate signals; a float is a gap in seconds."""
        out: Signal = []
        for p in parts:
            out += self.silence(p) if isinstance(p, (int, float)) else p
        return out

    def at(self, sig: Signal, start: float) -> Signal:
        return self.silence(start) + sig

    # -- output --------------------------------------------------------------
    def to_bytes(self, sig: Signal, gain: float = 1.0) -> bytes:
        frames = array.array("h")
        ch = self.channels
        for s in sig:
            v = int(max(-1.0, min(1.0, s * gain)) * 32767)
            frames.extend([v] * ch)
        return frames.tobytes()

    def duration(self, sig: Signal) -> float:
        return len(sig) / self.rate
