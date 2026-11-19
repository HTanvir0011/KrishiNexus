"""Hears the cloned lines back with the local faster-whisper model (backend/.venv, language="en"):
  takes -> work/clone/heard.json  {take: text}           (clone.py pick rejects takes with missing or extra words)
  mob   -> work/clone/timing.json {dur, words: [[w, s, e]]} (caption and picture timing for the mobile section)
Run with: PYTHONDONTWRITEBYTECODE=1 backend/.venv/Scripts/python.exe asr_clone.py takes|mob
"""
import json
import sys
from pathlib import Path

import av
import numpy as np
from faster_whisper import WhisperModel

MODEL = "C:/ai-congress/KrishiNexus/backend/models/whisper/krishi-whisper-bn-v1-ct2-int8"
CLONE = Path("C:/ai-congress/KrishiNexus/video/work/clone")


def to16k(a: np.ndarray, sr: int) -> np.ndarray:
    n = int(len(a) * 16000 / sr)
    return np.interp(np.arange(n) * sr / 16000, np.arange(len(a)), a).astype(np.float32)


def read(path: Path):
    with av.open(str(path)) as c:
        s = c.streams.audio[0]
        a = np.concatenate([f.to_ndarray() for f in c.decode(s)], axis=1).astype(np.float32)
        return a.mean(0), s.rate


m = WhisperModel(MODEL, device="cpu", compute_type="int8", cpu_threads=8)
if sys.argv[1] == "takes":
    out = {}
    for p in sorted((CLONE / "takes").glob("*.wav")):
        a, sr = read(p)
        segs, _ = m.transcribe(to16k(a, sr), language="en", beam_size=5, condition_on_previous_text=False)
        out[p.stem] = " ".join(s.text.strip() for s in segs)
        print(p.stem, "|", out[p.stem], flush=True)
    (CLONE / "heard.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
else:
    a = np.load(CLONE / "mob.npy")
    segs, _ = m.transcribe(to16k(a, 44100), language="en", beam_size=5, word_timestamps=True,
                           condition_on_previous_text=False)
    words = [[w.word, round(w.start, 3), round(w.end, 3)] for s in segs for w in (s.words or [])]
    (CLONE / "timing.json").write_text(json.dumps({"dur": round(len(a) / 44100, 3), "words": words}, indent=1),
                                       encoding="utf-8")
    print(" ".join(w[0] for w in words))
