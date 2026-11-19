"""Original procedural score (numpy; nothing sampled or downloaded), composed to the picture.

Instruments: a soft felt-piano motif (additive partials with slight inharmonicity, two strings per note detuned by
under a cent, a quiet hammer, a two-stage decay, the pedal held through each chord), a warm string ensemble (four
detuned, slowly drifting saw voices per note through a low-pass), a soft sine bass on the roots, an optional light
pulse (a felt kick on beats 1 and 3, a quiet shaker on the off-beats), and accents: celesta-like chimes on the
picture's hit points and suspended-cymbal swells into section changes. A synthetic room (decaying noise IR) as reverb.

Timing: every section starts on a downbeat; inside a section the beat is stretched around 72 BPM so that a whole
number of beats fits exactly, so every cut lands on a bar line. Chords change every bar (4 beats; a spare beat
lengthens the last bar, two or three make a short bar). `resolve` is a downbeat too: the two half-bars before it are
IV and V, and it lands on I (Dadd9), which rings out to `end`.

cues: {end, resolve?, lufs, fade_in, fade_out, sections: [{start, end, prog?, lift?, pulse?, sparse?}],
       hits: [(t, kind)], swells: [(t, depth)]}    hit kinds: "chime", "big", "arrive", "thump"
Usage (module): render(cues) -> float32 stereo (2, n) at 48 kHz, normalised to `lufs` (the undocked level).
"""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, oaconvolve, sosfilt

from loud import SR, lufs

BPM = 72
BEAT = 60 / BPM
CHORDS = {"D": (2, (0, 4, 7)), "Bm": (11, (0, 3, 7)), "G": (7, (0, 4, 7)), "A": (9, (0, 4, 7)),
          "Em": (4, (0, 3, 7)), "Dadd9": (2, (0, 4, 7, 14))}
# the motif, two bars long: eighth-note position in the bar -> step on the chord-tone ladder (root upwards)
MOTIF = [{0: 0, 1: 2, 2: 3, 3: 4, 5: 3, 6: 2}, {0: 1, 2: 3, 3: 4, 4: 5, 6: 4, 7: 3}]
SPARSE = [{0: 0, 3: 2, 6: 3}, {0: 1, 3: 3, 6: 4}]  # dotted quarters (3 + 3 + 2) for the intro
HAMMER = butter(2, [700, 3500], "band", fs=SR, output="sos")
SHAKER = butter(2, [4500, 11000], "band", fs=SR, output="sos")
CYMBAL = butter(2, [2500, 12000], "band", fs=SR, output="sos")


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def tones(chord: str, lo: int, hi: int) -> list[int]:
    root, iv = CHORDS[chord]
    pcs = {(root + i) % 12 for i in iv}
    return [m for m in range(lo, hi + 1) if m % 12 in pcs]


def ladder(chord: str) -> list[int]:
    root = CHORDS[chord][0]
    r0 = next(m for m in range(55, 67) if m % 12 == root)
    return tones(chord, r0, r0 + 31)


def bass_root(chord: str) -> int:
    return next(m for m in range(35, 47) if m % 12 == CHORDS[chord][0])


def _saw_table(size: int = 4096, n: int = 24) -> np.ndarray:
    ph = np.arange(size) / size
    w = sum(np.sin(2 * np.pi * k * ph) / k for k in range(1, n + 1))
    return w / np.abs(w).max()


SAW = _saw_table()


def _reverb_ir(seconds=2.8, predelay=0.03, seed=3) -> np.ndarray:
    """Stereo synthetic room: decorrelated noise with an exponential decay that darkens as it fades."""
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    out = []
    for _ in range(2):
        noise = rng.standard_normal(n)
        bright = sosfilt(butter(2, 6000, "low", fs=SR, output="sos"), noise)
        dark = sosfilt(butter(2, 1600, "low", fs=SR, output="sos"), noise)
        w = np.clip(t / (seconds * 0.6), 0, 1)
        ir = ((1 - w) * bright + w * dark) * np.exp(-6.91 * t / seconds)
        ir[: int(0.004 * SR)] *= np.linspace(0, 1, int(0.004 * SR))
        ir = np.concatenate([np.zeros(int(predelay * SR)), ir])
        out.append(ir / np.sqrt((ir ** 2).sum()))
    return np.array(out)


# -- the plan: bars on a beat grid stretched to fit each section ------------------------------------------------------

def plan(cues: dict) -> list[dict]:
    secs, end, resolve = cues["sections"], cues["end"], cues.get("resolve")
    anchors = sorted({s["start"] for s in secs} | ({resolve} if resolve is not None else set()))
    bars = []
    for i, a in enumerate(anchors):
        b = anchors[i + 1] if i + 1 < len(anchors) else end
        sec = [s for s in secs if s["start"] <= a + 1e-6][-1]
        if resolve is not None and a >= resolve - 1e-6:
            bars.append({"t0": a, "t1": b, "beat": BEAT, "beats": max(1, round((b - a) / BEAT)), "chord": "Dadd9",
                         "sec": sec, "final": True})
            continue
        n = max(2, round((b - a) / BEAT))
        beat = (b - a) / n
        cadence = resolve is not None and abs(b - resolve) < 1e-6 and n >= 6
        body = n - 4 if cadence else n
        lens = [4] * (body // 4)
        r = body % 4
        if r >= 2 or (r and not lens):
            lens.append(r)
        elif r:
            lens[-1] += r
        prog = sec.get("prog", ["D", "Bm", "G", "A"])
        chords = [prog[k % len(prog)] for k in range(len(lens))]
        if cadence:  # IV then V, two beats each, into the resolve
            lens += [2, 2]
            chords += ["G", "A"]
        t = a
        for k, (L, ch) in enumerate(zip(lens, chords)):
            bars.append({"t0": t, "t1": t + L * beat, "beat": beat, "beats": L, "chord": ch, "sec": sec, "k": k})
            t += L * beat
    return bars


# -- instruments ------------------------------------------------------------------------------------------------------

def piano_note(m: float, vel: float, ring: float, rng) -> np.ndarray:
    """A felt piano note: partials stretched by string stiffness, two strings a cent apart, fast-then-slow decay,
    a soft attack and a quiet hammer, damped `ring` seconds after it starts."""
    f = hz(m)
    L = int((ring + 0.35) * SR)
    t = np.arange(L) / SR
    tau = float(np.clip(2.8 * (262 / f) ** 0.6, 0.7, 4.5))
    nb = 2.5 + 5 * vel  # harder notes are brighter
    out = np.zeros(L)
    for k in range(1, 11):
        fk = k * f * np.sqrt(1 + 0.00025 * k * k)
        if fk > 10000:
            break
        tk = tau / (1 + 0.5 * (k - 1))
        env = 0.55 * np.exp(-t / (0.22 * tk)) + 0.45 * np.exp(-t / tk)
        ph = rng.uniform(0, 2 * np.pi)
        out += np.exp(-(k - 1) / nb) / k ** 0.8 * env * (np.sin(2 * np.pi * fk * 0.99954 * t + ph) +
                                                          np.sin(2 * np.pi * fk * 1.00052 * t + 1.3 * ph))
    out *= 1 - np.exp(-t / 0.006)
    out *= np.where(t > ring, np.exp(-np.maximum(t - ring, 0) / 0.09), 1.0)
    h = int(0.03 * SR)
    out[:h] += sosfilt(HAMMER, rng.standard_normal(h)) * np.exp(-t[:h] / 0.005) * 0.25
    return out * vel


def strings_chord(notes: list[int], L: int, attack: float, rng) -> np.ndarray:
    """Four detuned saw voices per note with a slow drift each, spread across the stereo field."""
    t = np.arange(L) / SR
    out = np.zeros((2, L))
    for m in notes:
        f0 = hz(m)
        for j, (det, pan) in enumerate(((-10, 0.12), (-3.5, 0.38), (3.5, 0.62), (10, 0.88))):
            drift = 3.0 * np.sin(2 * np.pi * (0.11 + 0.05 * j) * t + rng.uniform(0, 2 * np.pi))
            ph = (rng.uniform() + np.cumsum(f0 * 2 ** ((det + drift) / 1200)) / SR) % 1.0
            idx = ph * len(SAW)
            i0 = idx.astype(int)
            fr = idx - i0
            w = SAW[i0] * (1 - fr) + SAW[(i0 + 1) % len(SAW)] * fr
            out[0] += w * np.cos(pan * np.pi / 2)
            out[1] += w * np.sin(pan * np.pi / 2)
    a, r = int(attack * SR), int(1.5 * SR)
    env = np.ones(L)
    env[:a] = np.sin(np.linspace(0, np.pi / 2, a)) ** 2
    env[-r:] *= np.cos(np.linspace(0, np.pi / 2, r)) ** 2
    return out * env / len(notes)


def bass_note(m: int, dur: float) -> np.ndarray:
    L = int((dur + 0.6) * SR)
    t = np.arange(L) / SR
    f = hz(m)
    x = np.sin(2 * np.pi * f * t) + 0.22 * np.sin(4 * np.pi * f * t) + 0.06 * np.sin(6 * np.pi * f * t)
    env = (1 - np.exp(-t / 0.05)) * (0.75 + 0.25 * np.exp(-t / 0.6))
    r = int(0.6 * SR)
    env[-r:] *= np.cos(np.linspace(0, np.pi / 2, r)) ** 2
    return x * env


def felt_kick(vel: float, low: float = 48.0) -> np.ndarray:
    t = np.arange(int(0.4 * SR)) / SR
    f = low + 60 * np.exp(-t / 0.035)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.15) * (1 - np.exp(-t / 0.002)) * vel


def shaker(vel: float, rng) -> np.ndarray:
    t = np.arange(int(0.14 * SR)) / SR
    return sosfilt(SHAKER, rng.standard_normal(len(t))) * (1 - np.exp(-t / 0.008)) * np.exp(-t / 0.045) * vel


def chime(m: float, vel: float) -> np.ndarray:
    """Celesta-like: a sine with a few soft upper partials, each fading faster than the last."""
    t = np.arange(int(3.0 * SR)) / SR
    f = hz(m)
    out = sum(a * np.exp(-t / d) * np.sin(2 * np.pi * f * r * t)
              for r, a, d in ((1, 1.0, 1.6), (2.0, 0.3, 0.8), (3.0, 0.1, 0.45), (4.16, 0.05, 0.25)))
    return out * (1 - np.exp(-t / 0.002)) * vel


def cymbal_swell(rise: float, depth: float, rng) -> np.ndarray:
    """A suspended cymbal rolled softly up into the hit, then let go."""
    n_r, n_f = int(rise * SR), int(0.9 * SR)
    noise = sosfilt(CYMBAL, rng.standard_normal((2, n_r + n_f)), axis=1)
    env = np.concatenate([np.linspace(0, 1, n_r) ** 3, np.exp(-np.arange(n_f) / SR / 0.22)])
    return noise * env * depth


# -- render -----------------------------------------------------------------------------------------------------------

def _add(buf: np.ndarray, t: float, x: np.ndarray, pan: float = 0.5):
    i = int(round(max(0.0, t) * SR))
    if i >= buf.shape[-1]:
        return
    x = x[..., : buf.shape[-1] - i]
    if buf.ndim == 1:
        buf[i:i + x.shape[-1]] += x
    elif x.ndim == 1:
        buf[0, i:i + len(x)] += x * np.cos(pan * np.pi / 2)
        buf[1, i:i + len(x)] += x * np.sin(pan * np.pi / 2)
    else:
        buf[:, i:i + x.shape[-1]] += x


def _norm(x: np.ndarray, target: float) -> np.ndarray:
    l = lufs(np.atleast_2d(x))
    return x * 10 ** ((target - l) / 20) if np.isfinite(l) else x


def render(cues: dict) -> np.ndarray:
    end = cues["end"]
    n = int(end * SR) + int(3 * SR)
    rng = np.random.default_rng(11)
    piano, strings, lifted = np.zeros((2, n)), np.zeros((2, n)), np.zeros((2, n))
    bass, kick, shake, bells, swells = np.zeros(n), np.zeros(n), np.zeros((2, n)), np.zeros((2, n)), np.zeros((2, n))
    bars = plan(cues)
    for bi, bar in enumerate(bars):
        t0, t1, beat, ch, sec = bar["t0"], bar["t1"], bar["beat"], bar["chord"], bar["sec"]
        final, lift = bar.get("final", False), sec.get("lift", False)
        # strings: the chord tones from G3 to B4 (to E5 in a lift), held into the next bar
        notes = tones(ch, 52, 76 if lift else 71)
        L = min(int((t1 - t0 + (3.0 if final else 1.4)) * SR), n - int(t0 * SR))
        _add(lifted if lift else strings, t0, strings_chord(notes, L, 2.5 if t0 < 0.5 else 0.9, rng))
        _add(bass, t0, bass_note(bass_root(ch), t1 - t0 + (1.5 if final else 0.0)))
        lad = ladder(ch)
        if final:  # the end card: a rolled chord, then one high note
            for j, step in enumerate((0, 1, 2, 3, 4)):
                _add(piano, t0 + 0.09 * j, piano_note(lad[step], 0.5, end - t0 - 0.09 * j, rng), 0.3 + 0.1 * j)
            _add(piano, t0 + 2 * beat, piano_note(lad[5], 0.4, end - t0 - 2 * beat, rng), 0.7)
            continue
        pat = (SPARSE if sec.get("sparse") else MOTIF)[bar.get("k", 0) % 2]
        for pos in range(2 * bar["beats"]):
            step = pat.get(pos % 8)
            if step is None or (pos >= 8 and pos % 2):
                continue
            tn = t0 + pos * beat / 2 + (rng.normal(0, 0.006) if pos else 0.0)
            vel = (0.8 if pos == 0 else 0.62 if pos % 4 == 3 else 0.55) + rng.uniform(-0.06, 0.06)
            ring = min(t1 - tn + 0.25, 3.2)
            _add(piano, tn, piano_note(lad[step], vel, ring, rng), 0.42 + 0.03 * step)
            if lift and pos % 4 == 1:  # a lift doubles the motif's upbeats an octave higher
                _add(piano, tn + 0.01, piano_note(lad[step] + 12, vel * 0.45, ring, rng), 0.7)
        if sec.get("pulse"):
            for b in range(bar["beats"]):
                if b % 2 == 0:
                    _add(kick, t0 + b * beat, felt_kick(1.0 if b == 0 else 0.55))
                _add(shake, t0 + (b + 0.5) * beat, shaker(0.85 if b % 2 else 0.65, rng), 0.62)
    # accents on the picture's hit points, pitched from the chord that is sounding
    for i, (t, kind) in enumerate(sorted(cues.get("hits", []))):
        bar = next((b for b in bars if b["t0"] <= t < b["t1"]), bars[-1])
        top = tones(bar["chord"], 76, 91)
        m = top[[2, 1, 3, 0][i % 4] % len(top)]
        pan = 0.35 if i % 2 else 0.65
        if kind == "big":  # two notes, the second a fifth or a fourth up
            _add(bells, t, chime(m, 0.9), pan)
            _add(bells, t + 0.08, chime(next(x for x in top if x > m + 4) if top[-1] > m + 4 else m - 5, 0.7),
                 1 - pan)
        elif kind == "arrive":  # two notes stepping down, a truck coming to rest
            _add(bells, t - 0.14, chime(m + (3 if m + 3 in top else 4), 0.6), pan)
            _add(bells, t, chime(m, 0.8), pan)
        else:
            _add(bells, t, chime(m, 0.8), pan)
        if kind == "thump":
            _add(kick, t, felt_kick(1.1, low=42.0))
    for t, depth in cues.get("swells", []):
        rise = 1.6 if depth <= 1 else 2.2
        _add(swells, t - rise, cymbal_swell(rise, depth, rng))
    # the string bed leans into each section change (+2 to +4 dB over 1.4 s, more into a lift)
    tvec = np.arange(n) / SR
    gain = np.ones(n)
    for sec in cues["sections"][1:]:
        b = sec["start"]
        depth = 1.6 if sec.get("lift") else 1.3
        up = np.clip((tvec - (b - 1.4)) / 1.4, 0, 1) * (tvec < b)
        down = np.clip(1 - (tvec - b) / 1.2, 0, 1) * (tvec >= b)
        gain *= 1 + (depth - 1) * np.maximum(up ** 2, down ** 2)
    warm = butter(2, 1900, "low", fs=SR, output="sos")
    bright = butter(2, 2800, "low", fs=SR, output="sos")
    strings = (sosfilt(warm, strings, axis=1) + sosfilt(bright, lifted, axis=1)) * gain
    bass = sosfilt(butter(2, 220, "low", fs=SR, output="sos"), bass)
    # balance the stems by loudness (the piano carries the motif, the strings sit just under it)
    piano, strings = _norm(piano, -24.0), _norm(strings, -25.5)
    bass, kick, shake = _norm(bass, -31.0), _norm(kick, -37.0), _norm(shake, -41.0)
    bells, swells = _norm(bells, -27.0), _norm(swells, -33.0)
    ir = _reverb_ir()
    send = 0.55 * piano + 0.35 * strings + 0.8 * bells + 0.3 * swells + 0.2 * shake
    wet = np.array([oaconvolve(send[c], ir[c])[:n] for c in range(2)])
    mix = piano + strings + bells + swells + shake + (bass + kick)[None, :] * np.sqrt(0.5) + 0.5 * wet
    # fade in, fade out to silence at `end`
    env = np.ones(n)
    a = int(cues.get("fade_in", 1.5) * SR)
    env[:a] = np.linspace(0, 1, a) ** 2
    e0, e1 = int((end - cues.get("fade_out", 2.5)) * SR), int(end * SR)
    env[e0:e1] *= np.cos(np.linspace(0, np.pi / 2, e1 - e0)) ** 1.5
    env[e1:] = 0
    mix = (mix * env)[:, : int(end * SR)]
    mix *= 10 ** ((cues.get("lufs", -20.0) - lufs(mix)) / 20)
    return mix.astype(np.float32)


if __name__ == "__main__":  # a 40 s test cue: levels, bar grid and a wav to check
    import sys
    import wave
    cues = {"end": 40.0, "resolve": 33.0, "lufs": -20.0, "hits": [(5.0, "chime"), (14.0, "thump"), (25.0, "big")],
            "swells": [(12.0, 1.0), (22.0, 1.8), (33.0, 1.4)], "sections": [
                {"start": 0, "end": 12, "sparse": True}, {"start": 12, "end": 22, "pulse": True},
                {"start": 22, "end": 40, "lift": True, "pulse": True, "prog": ["G", "A", "Bm", "D"]}]}
    for b in plan(cues):
        assert abs(60 / b["beat"] - BPM) < 6 or b.get("final"), b  # the stretched beat stays near 72 BPM
    assert {round(b["t0"], 6) for b in plan(cues)} >= {0.0, 12.0, 22.0, 33.0}  # every section starts on a bar line
    m = render(cues)
    print("shape", m.shape, "lufs", round(lufs(m), 2), "peak", round(20 * np.log10(np.abs(m).max()), 2))
    out = sys.argv[1] if len(sys.argv) > 1 else "music_test.wav"
    with wave.open(out, "wb") as w:
        w.setnchannels(2), w.setsampwidth(2), w.setframerate(SR)
        w.writeframes((np.clip(m.T, -1, 1) * 32767).astype("<i2").tobytes())
