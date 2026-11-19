"""Mixes the sound for the videos at 48 kHz: the edited narration (and the cloned mobile lines) as a centred voice at
-16 LUFS integrated, the procedural score (music.py) cued to the sections and the picture's hit points, at -20 LUFS
where nobody speaks and ducked under the voice to about -28 LUFS (sidechain from the voice envelope: 80 ms attack
with 80 ms look-ahead, 0.35 s hold through the gaps between sentences, 0.5 s release, corners smoothed over 50 ms so
it never pumps), then a true-peak limiter at -1.5 dBTP (headroom for the AAC encode, which must stay under -1 dBTP).

Voice chain per segment: 70 Hz high-pass, a 3:1 soft-knee compressor on the loudest fifth of the syllables (the phone
recordings sit near -30 LUFS with peaks 14 dB above their speech), level to -16 LUFS, a -3 dBTP peak limiter.

Usage: python mix.py demo | p30      (video/.venv-tts python: numpy, scipy)
Output: work/mix/<name>_mix.wav, _voice.wav, _music.wav and <name>_levels.json
"""
from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, resample_poly, sosfilt

sys.path.insert(0, str(Path(__file__).parent))
import timeline  # noqa: E402
from loud import SR, limit, lufs, true_peak_db, _blocks  # noqa: E402
from music import render  # noqa: E402

WORK = Path("C:/ai-congress/KrishiNexus/video/work")
VOICE_LUFS = -16.0
MUSIC_LUFS = -20.0       # the bed's level where nobody speaks (intro, gaps, transitions, end card)
DUCK_DB, ATTACK, HOLD, RELEASE, LOOKAHEAD = 9.0, 0.08, 0.35, 0.50, 0.08


def to48(a: np.ndarray) -> np.ndarray:
    return resample_poly(a, 160, 147).astype(np.float32)  # 44.1 kHz -> 48 kHz


def compress_voice(x: np.ndarray, ratio=3.0, knee=6.0, attack=0.003, release=0.12, pct=80) -> np.ndarray:
    fr = SR // 1000  # 1 ms frames
    n = len(x) // fr
    e = np.mean(x[: n * fr].reshape(n, fr) ** 2, 1)
    lvl = 10 * np.log10(np.convolve(e, np.ones(5) / 5, mode="same") + 1e-12)  # 5 ms RMS
    voiced = lvl > lvl.max() - 40
    thr = np.percentile(lvl[voiced], pct)
    over = lvl - thr
    gr = np.where(over <= -knee / 2, 0.0, np.where(over >= knee / 2, over * (1 - 1 / ratio),
                                                    (1 - 1 / ratio) * (over + knee / 2) ** 2 / (2 * knee)))
    a_c, r_c = np.exp(-1 / (attack * 1000)), np.exp(-1 / (release * 1000))
    sm, cur = np.zeros(n), 0.0
    for i in range(n):
        c = a_c if gr[i] > cur else r_c
        cur = c * cur + (1 - c) * gr[i]
        sm[i] = cur
    g = np.interp(np.arange(len(x)) / fr, np.arange(n) + 0.5, 10 ** (-sm / 20))
    return (x * g).astype(np.float32)


HP = butter(2, 70, "high", fs=SR, output="sos")


def voice_chain(a44: np.ndarray) -> np.ndarray:
    a = sosfilt(HP, to48(a44)).astype(np.float32)
    a = compress_voice(a)
    a *= 10 ** ((VOICE_LUFS - lufs(a)) / 20)
    return limit(a, -3.0)[0]


def write_wav(path: Path, x: np.ndarray):
    x = np.atleast_2d(x)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(x.shape[0])
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x.T, -1, 1) * 32767).round().astype("<i2").tobytes())


def duck_gain(voice: np.ndarray, opens: list[float] = ()) -> np.ndarray:
    """Music gain (linear) from the voice: down DUCK_DB while speaking, with look-ahead, hold and release. Around each
    time in `opens` (the section changes) there is no hold and a quick release, so the score swells up in the short
    silence under the wipe and ducks again as the next section's first word comes."""
    hop = SR // 100
    n = len(voice) // hop + 1
    v = np.pad(voice, (0, n * hop - len(voice)))
    db = 20 * np.log10(np.sqrt(np.mean(v.reshape(n, hop) ** 2, 1)) + 1e-9)
    active = db > -45.0
    la = int(LOOKAHEAD * 100)
    active = np.concatenate([active[la:], np.zeros(la, bool)]) | active  # start ducking before the voice
    # hold: stay down through short gaps
    hold = int(HOLD * 100)
    near = np.zeros(n, bool)
    for b in opens:
        near[max(0, int((b - 0.7) * 100)):int((b + 0.1) * 100)] = True
    held = active.copy()
    last = -10 ** 9
    for i in range(n):
        if active[i]:
            last = i
        elif i - last <= hold and not near[i]:
            held[i] = True
    target = np.where(held, -DUCK_DB, 0.0)
    g = np.zeros(n)
    down, up = DUCK_DB / (ATTACK * 100), DUCK_DB / (RELEASE * 100)  # dB per 10 ms frame
    cur = 0.0
    for i in range(n):
        if target[i] < cur:
            cur = max(target[i], cur - down)
        else:
            cur = min(target[i], cur + (DUCK_DB / 15 if near[i] else up))  # 0.15 s release at a section change
        g[i] = cur
    g = np.convolve(np.pad(g, 2, mode="edge"), np.ones(5) / 5, mode="valid")  # round the corners (50 ms)
    gl = 10 ** (g / 20)
    return np.interp(np.arange(len(voice)) / hop, np.arange(n), gl).astype(np.float32)


def place(total: float, items: list[tuple[float, np.ndarray]]) -> np.ndarray:
    out = np.zeros(int(round(total * SR)) + SR, np.float32)
    for t, a in items:
        i = int(round(t * SR))
        out[i:i + len(a)] += a[: len(out) - i]
    return out[: int(round(total * SR))]


PROGS = {"S00": ["D", "Bm", "G", "A"], "S01": ["Bm", "G", "D", "A"],  # the problem opens on the minor chord
         "MOB": ["G", "A", "Bm", "D"], "S10": ["D", "Bm", "G", "A"]}   # IV-V-vi-I lifts into the app


def voice_items(name: str):
    """[(start time, 48 kHz voice segment normalised to -16 LUFS)], total length, and the music cue sheet."""
    if name == "demo":
        tl = timeline.load()
        items, cues = [], []
        for sec in tl["sections"]:
            src = WORK / ("clone/mob.npy" if sec["key"] == "MOB" else f"voice/{sec['key']}.npy")
            if not src.exists():  # the cloned lines are not made yet: a silent stand-in keeps the timing
                print("missing", src, "- silence instead")
                items.append((sec["voice_at"], np.zeros(int(sec["voice_dur"] * SR), np.float32)))
            else:
                items.append((sec["voice_at"], voice_chain(np.load(src))))
            # each section's downbeat lands as its wipe turns over (0.12 s before its first word)
            k = sec["key"]
            cue = {"start": 0.0 if k == "S00" else sec["start"] - 0.12, "end": None, "pulse": k not in ("S00", "S01"),
                   "prog": PROGS[k] if k in PROGS else ["D", "Bm", "G", "A"] if int(k[1:]) % 2 else ["D", "A", "Bm", "G"]}
            if k == "S00":
                cue["sparse"] = True
            if k in ("MOB", "S10"):
                cue["lift"] = True
            cues.append(cue)
        for a, b in zip(cues, cues[1:]):
            a["end"] = b["start"]
        cues[-1]["end"] = tl["total"]
        s10 = tl["sections"][-1]
        resolve = s10["start"] + timeline.word_time(s10, "This", timeline.word_time(s10, "January"))
        import build
        hits = build.music_hits(build.Film())
        keys = [s["key"] for s in tl["sections"]]
        swells = [(c["start"], 1.8 if k == "MOB" else 1.0) for k, c in zip(keys[1:], cues[1:])] + [(resolve, 1.4)]
        return items, tl["total"], {"end": tl["total"], "resolve": resolve, "sections": cues, "hits": hits,
                                    "swells": swells, "fade_in": 1.0, "fade_out": 1.4,
                                    "opens": [c["start"] + 0.12 for c in cues[1:]]}, tl
    if name == "p30":
        import p30
        return p30.voice_items(voice_chain)
    raise SystemExit(f"unknown mix {name}")


def main(name: str):
    out = WORK / "mix"
    out.mkdir(parents=True, exist_ok=True)
    items, total, cue, tl = voice_items(name)
    voice = place(total, items)
    voice *= 10 ** ((VOICE_LUFS - lufs(voice)) / 20)  # the stem as a whole at -16.0 LUFS
    cue["lufs"] = MUSIC_LUFS
    music = render(cue)
    music = np.pad(music, ((0, 0), (0, max(0, len(voice) - music.shape[1]))))[:, : len(voice)]
    levels_ducking = {"duck_db": DUCK_DB, "attack_s": ATTACK, "hold_s": HOLD, "release_s": RELEASE,
                      "lookahead_s": LOOKAHEAD, "hits": len(cue.get("hits", [])), "swells": len(cue.get("swells", [])),
                      "opens_at_section_changes": len(cue.get("opens", []))}
    g = duck_gain(voice, cue.get("opens", []))
    ducked = music * g[None, :]
    vb = _blocks(voice)
    speech = -0.691 + 10 * np.log10(vb + 1e-20) > -40  # 400 ms blocks with the voice present
    voice = np.vstack([voice, voice]) * np.float32(np.sqrt(0.5))  # centred: the stereo pair measures -16 LUFS too
    mix = limit(voice + ducked, -1.5)
    levels = {
        "duration_s": round(voice.shape[1] / SR, 3),
        "voice_lufs_integrated": round(lufs(voice), 2),
        "music_lufs_undocked": round(lufs(music), 2),
        "voice_lufs_during_speech": round(lufs(voice, speech), 2),
        "music_lufs_during_speech": round(lufs(ducked, speech), 2),
        "mix_lufs_integrated": round(lufs(mix), 2),
        "mix_true_peak_dbtp": round(true_peak_db(mix), 2),
        "voice_true_peak_dbtp_before_limiter": round(true_peak_db(voice), 2),
    }
    levels["music_below_voice_during_speech_db"] = round(levels["voice_lufs_during_speech"] -
                                                         levels["music_lufs_during_speech"], 2)
    levels["ducking"] = levels_ducking
    write_wav(out / f"{name}_mix.wav", mix)
    write_wav(out / f"{name}_voice.wav", voice)
    write_wav(out / f"{name}_music.wav", ducked)
    (out / f"{name}_levels.json").write_text(json.dumps(levels, indent=1), encoding="utf-8")
    print(json.dumps(levels, indent=1))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "demo")
