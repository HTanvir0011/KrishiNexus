"""Edit the narration for the videos: pauses longer than 0.35 s are shortened (about 0.2 s left: 0.24 s after a
sentence, 0.18 s inside one), the file edges are trimmed to 0.05 s, then the whole segment is sped up by TEMPO with
FFmpeg's pitch-preserving atempo (PyAV filter graph). The ASR word times (work/asr.json) are carried onto the new
timeline, so captions and picture cues follow the edited voice.

Usage: python narration.py <out_dir> <tempo> [keep_sentence keep_comma]   (backend/.venv or video/.venv-tts python)
Output: <out_dir>/<seg>.npy (44.1 kHz mono float32) and <out_dir>/timing.json
"""
from __future__ import annotations

import json
import sys
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from av.audio.frame import AudioFrame

ROOT = Path("C:/ai-congress/KrishiNexus/video")
SR, HOP = 44100, 441  # 10 ms frames
THR_DB = -50.0  # below this the recording is a pause (it is noise-gated to about -86 dBFS between phrases)
MAX_PAUSE, EDGE, XF = 0.35, 0.05, 0.005
# pauses kept longer on purpose (silence is added if the recorded pause is shorter): after "team lead," in S00, so
# Tanvir's intro card holds over 2 s before the next name is spoken
LONGER = {"lead,": 0.95}


def env_db(a: np.ndarray) -> np.ndarray:
    n = len(a) // HOP
    return 20 * np.log10(np.sqrt(np.mean(a[: n * HOP].reshape(n, HOP) ** 2, 1)) + 1e-9)


def quiet_runs(db: np.ndarray) -> list[tuple[int, int]]:
    q = np.concatenate([[False], db < THR_DB, [False]])
    d = np.diff(q.astype(int))
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))  # frame ranges [s, e)


def compress(a: np.ndarray, words: list, keep_sentence: float, keep_comma: float):
    """Cut the middle out of long pauses. Returns the new audio and the cut list [(orig_start, orig_end)] in seconds."""
    db = env_db(a)
    n = len(db)
    cuts = []
    for s, e in quiet_runs(db):
        t0, t1 = s * HOP / SR, e * HOP / SR
        if s == 0:
            cuts.append((0.0, max(0.0, t1 - EDGE)))
        elif e >= n:
            cuts.append((t0 + EDGE, len(a) / SR))
        elif t1 - t0 > MAX_PAUSE:
            before = [w for w in words if w[2] <= t0 + 0.4]  # ASR word ends run early; allow 0.4 s
            ends_sentence = bool(before) and before[-1][0].strip()[-1:] in ".?!"
            keep = keep_sentence if ends_sentence else keep_comma
            if before:
                keep = LONGER.get(before[-1][0].strip().lower(), keep)
            if t1 - t0 > keep:
                cuts.append((t0 + keep / 2, t1 - keep / 2))
            elif keep > t1 - t0:  # a pad: written as a "cut" running backwards, so map_time adds its length
                mid = (t0 + t1) / 2
                cuts.append((mid, mid - (keep - (t1 - t0))))
    out, pos = [], 0
    for c0, c1 in cuts:
        i0, i1 = int(c0 * SR), int(c1 * SR)
        if i1 < i0:  # a pad: silence inserted in the pause
            out.append(a[pos:i0].copy())
            out.append(np.zeros(i0 - i1, np.float32))
            pos = i0
            continue
        if i1 - i0 < 2 * int(XF * SR):
            continue
        piece = a[pos:i0].copy()
        out.append(piece)
        pos = i1
    out.append(a[pos:])
    # 5 ms fades at every splice (both sides are pause, so this only guards against clicks)
    f = int(XF * SR)
    ramp = np.linspace(0, 1, f, dtype=np.float32)
    for k, p in enumerate(out):
        if k > 0 and len(p) > f:
            p[:f] *= ramp
        if k < len(out) - 1 and len(p) > f:
            p[-f:] *= ramp[::-1]
    return np.concatenate(out), cuts


def map_time(t: float, cuts: list) -> float:
    """Original time -> time after the cuts (a time inside a cut maps to the splice)."""
    shift = 0.0
    for c0, c1 in cuts:
        if t >= c1:
            shift += c1 - c0
        elif t > c0:
            return c0 - shift
    return t - shift


def atempo(x: np.ndarray, factor: float, sr: int = SR) -> np.ndarray:
    if abs(factor - 1) < 1e-6:
        return x.copy()
    g = av.filter.Graph()
    src = g.add_abuffer(format="flt", sample_rate=sr, layout="mono", time_base=Fraction(1, sr))
    t = g.add("atempo", f"{factor}")
    sink = g.add("abuffersink")
    src.link_to(t)
    t.link_to(sink)
    g.configure()
    out, pts = [], 0

    def drain():
        while True:
            try:
                out.append(g.pull().to_ndarray()[0])
            except (av.error.BlockingIOError, av.error.EOFError):
                return

    for i in range(0, len(x), 4096):
        chunk = np.ascontiguousarray(x[i:i + 4096], dtype=np.float32)
        fr = AudioFrame.from_ndarray(chunk[None, :], format="flt", layout="mono")
        fr.sample_rate, fr.pts, fr.time_base = sr, pts, Fraction(1, sr)
        pts += len(chunk)
        g.push(fr)
        drain()
    g.push(None)
    drain()
    return np.concatenate(out).astype(np.float32)


def main(out_dir: Path, tempo: float, keep_sentence: float = 0.24, keep_comma: float = 0.18, segs=None):
    asr = json.loads((ROOT / "work/asr.json").read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    timing = {"tempo": tempo, "sr": SR, "segments": {}}
    for seg in segs or sorted(asr):
        a = np.load(ROOT / f"work/narr/{seg}.npy")
        words = asr[seg]["words"]
        b, cuts = compress(a, words, keep_sentence, keep_comma)
        c = atempo(b, tempo)
        np.save(out_dir / f"{seg}.npy", c)
        scale = len(c) / max(1, len(b))  # measured, so the mapping stays exact even if atempo rounds
        new_words = [[w, round(map_time(s, cuts) * scale, 3), round(map_time(e, cuts) * scale, 3)] for w, s, e, _ in words]
        timing["segments"][seg] = {"dur": round(len(c) / SR, 3), "orig": round(len(a) / SR, 3),
                                   "cut": round(sum(c1 - c0 for c0, c1 in cuts), 3), "words": new_words}
        print(f"{seg}: {len(a) / SR:6.2f} s -> {len(b) / SR:6.2f} s (pauses) -> {len(c) / SR:6.2f} s (x{tempo})")
    total = sum(s["dur"] for s in timing["segments"].values())
    timing["total"] = round(total, 3)
    (out_dir / "timing.json").write_text(json.dumps(timing, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"total {total:.2f} s")


if __name__ == "__main__":
    args = sys.argv[1:]
    main(Path(args[0]), float(args[1]), *(float(x) for x in args[2:4]))
