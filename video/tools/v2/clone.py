"""The mobile-app lines in the narrator's own cloned voice (the narrator is the owner, who consented), with Chatterbox
(ResembleAI/chatterbox, CPU) in video/.venv-tts.

  python clone.py verify       joins the ranged download of s3gen and checks every model file's SHA-256
  python clone.py ref          builds the reference: 16.5 s of narration (S09, pauses shortened, original speed)
  python clone.py gen N        N takes per sentence -> work/clone/takes/<k>_<n>.wav (+ takes.json with the settings)
  python clone.py pick         scores every take (words heard back by faster-whisper, voice similarity to the
                               narrator, speaking rate, pitch range, stray noise) and keeps the best per sentence
  python clone.py match        joins the picks, then matches the narration: pauses, tempo, tone (EQ to the
                               narrator's long-term spectrum), air above 12 kHz, gate, loudness -> work/clone/mob.npy

The model files come from Hugging Face (ResembleAI/chatterbox) via fetch_chatterbox.sh into video/models/chatterbox.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path("C:/ai-congress/KrishiNexus/video")
OUT = ROOT / "work/clone"
MODEL = ROOT / "models/chatterbox"
SR = 44100

# The script (50 words, the brief's wording; the app has the driver's "Share live location" switch and live market
# updates), one take per sentence: (caption text, the spelling the TTS reads: names as the narrator says them)
LINES = [
    ("KrishiNexus also fits in a farmer's pocket.",
     "Krishi Nexus also fits in a farmer's pocket."),
    ("Our Android app speaks Bangla: Rahim asks out loud and hears the answer back.",
     "Our Android app speaks Bangla. Raheem asks out loud, and hears the answer back."),
    ("He photographs his harvest and gets a signed grade in seconds.",
     "He photographs his harvest, and gets a signed grade in seconds."),
    ("Buyers bid from their phones, drivers share their live location, and everyone follows the sale in real time.",
     "Buyers bid from their phones, drivers share their live location, and everyone follows the sale in real time."),
]


def load_wav(p: Path):
    import soundfile as sf
    a, sr = sf.read(str(p), dtype="float32", always_2d=False)
    if a.ndim > 1:
        a = a.mean(1)
    return a, sr


def save_wav(p: Path, a: np.ndarray, sr: int):
    import soundfile as sf
    p.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(p), np.asarray(a, dtype=np.float32), sr, subtype="FLOAT")


def resample(a: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    from math import gcd
    from scipy.signal import resample_poly
    g = gcd(sr_in, sr_out)
    return resample_poly(a, sr_out // g, sr_in // g).astype(np.float32)


# SHA-256 of the Hugging Face files (ResembleAI/chatterbox, revision 5bb1f6ee), checked after the resumable download
SHA256 = {"ve.safetensors": "f0921cab452fa278bc25cd23ffd59d36f816d7dc5181dd1bef9751a7fb61f63c",
          "conds.pt": "6552d70568833628ba019c6b03459e77fe71ca197d5c560cef9411bee9d87f4e",
          "s3gen.safetensors": "2b78103c654207393955e4900aac14a12de8ef25f4b09424f1ef91941f161d4e",
          "t3_cfg.pt": "0b2dd5439fe7e94f379561419847a45bf2c79d0e8ea751c6bbe947ce337789cc"}


SIZES = {"s3gen.safetensors": 1056484620, "t3_cfg.pt": 1064892246}


def verify() -> bool:
    """Join the ranged parts of the big files (fetch_range.sh: <file>.r0, .r1, ...), then check every SHA-256."""
    import hashlib
    parts_all = []
    for name, size in SIZES.items():
        parts = sorted(MODEL.glob(f"{name}.r[0-9]"))
        if not parts:
            continue
        if sum(p.stat().st_size for p in parts) != size:
            print(name, "parts incomplete")
            return False
        with open(MODEL / name, "wb") as out:
            for p in parts:
                out.write(p.read_bytes())
        parts_all += parts
    parts = parts_all
    ok = True
    for name, want in SHA256.items():
        h = hashlib.sha256()
        with open(MODEL / name, "rb") as f:
            for blk in iter(lambda: f.read(1 << 22), b""):
                h.update(blk)
        good = h.hexdigest() == want
        ok &= good
        print(name, "ok" if good else "SHA-256 MISMATCH")
    if ok:
        for p in parts:
            p.unlink()
    return ok


# -- reference -----------------------------------------------------------------------------------------------------

def make_ref():
    sys.path.insert(0, str(Path(__file__).parent))
    from narration import compress
    asr = json.loads((ROOT / "work/asr.json").read_text(encoding="utf-8"))
    a = np.load(ROOT / "work/narr/S09.npy")
    b, _ = compress(a, asr["S09"]["words"], 0.24, 0.18)
    save_wav(OUT / "ref.wav", b, SR)
    print("reference", round(len(b) / SR, 2), "s")


# -- generation ----------------------------------------------------------------------------------------------------

def load_model():
    import torch
    from chatterbox.tts import ChatterboxTTS
    torch.set_num_threads(14)
    t3 = MODEL / "t3_cfg.safetensors"
    if not t3.exists():  # the half-size checkpoint was fetched instead: store it as float32 safetensors once
        from safetensors.torch import save_file
        sd = torch.load(MODEL / "t3_cfg.pt", map_location="cpu", weights_only=True)
        if isinstance(sd, dict) and "model" in sd:
            sd = sd["model"][0] if isinstance(sd["model"], list) else sd["model"]
        save_file({k: v.float().contiguous() for k, v in sd.items()}, str(t3))
    return ChatterboxTTS.from_local(MODEL, "cpu")


def generate(n: int):
    import time
    import torch
    m = load_model()
    m.prepare_conditionals(str(OUT / "ref.wav"), exaggeration=0.5)
    settings = [  # (exaggeration, cfg_weight, temperature): calm read, a little variety between takes
        (0.45, 0.5, 0.75), (0.5, 0.45, 0.8), (0.4, 0.55, 0.7), (0.5, 0.5, 0.8), (0.55, 0.4, 0.8),
        (0.65, 0.4, 0.8), (0.7, 0.35, 0.8),  # livelier takes: the narrator's pitch moves more than the first takes
    ]
    meta = json.loads((OUT / "takes.json").read_text()) if (OUT / "takes.json").exists() else {}
    for k, (_, text) in enumerate(LINES):
        for j in range(n):
            name = f"{k}_{j}"
            if name in meta:
                continue
            ex, cfg, temp = settings[j % len(settings)]
            torch.manual_seed(1000 * k + j)
            t0 = time.time()
            wav = m.generate(text, exaggeration=ex, cfg_weight=cfg, temperature=temp)
            a = wav.squeeze(0).numpy()
            save_wav(OUT / "takes" / f"{name}.wav", a, m.sr)
            meta[name] = {"line": k, "exaggeration": ex, "cfg_weight": cfg, "temperature": temp,
                          "seconds": round(len(a) / m.sr, 2), "compute_s": round(time.time() - t0, 1)}
            print(name, meta[name], flush=True)
            (OUT / "takes.json").write_text(json.dumps(meta, indent=1))


# -- scoring ---------------------------------------------------------------------------------------------------------

def f0_stats(a: np.ndarray, sr: int):
    import librosa
    y = resample(a, sr, 16000)
    f0, vf, _ = librosa.pyin(y, fmin=70, fmax=300, sr=16000, frame_length=1024)
    f0 = f0[vf & np.isfinite(f0)]
    if len(f0) < 10:
        return 0.0, 0.0
    st = 12 * np.log2(f0 / 100)
    return float(np.median(f0)), float(np.std(st))


def norm_words(text: str) -> list[str]:
    """Words for comparing what was meant with what was heard back (names as the recogniser spells them)."""
    import re
    t = text.lower().replace("krishi nexus", "krishinexus").replace("-", " ")
    alias = {"raheem": "rahim", "rahem": "rahim", "rahim's": "rahim", "bengali": "bangla",
             "here's": "hears", "heres": "hears"}  # same sound
    return [alias.get(w, w) for w in re.findall(r"[a-z']+", t)]


def voiced_rate(a: np.ndarray, sr: int, words: int) -> float:
    hop = sr // 100
    n = len(a) // hop
    db = 20 * np.log10(np.sqrt(np.mean(a[: n * hop].reshape(n, hop) ** 2, 1)) + 1e-9)
    voiced = (db > db.max() - 35).sum() / 100
    return words / max(voiced, 0.1)


def pick():
    import re
    import torch
    from chatterbox.models.voice_encoder import VoiceEncoder
    from safetensors.torch import load_file
    ve = VoiceEncoder()
    ve.load_state_dict(load_file(MODEL / "ve.safetensors"))
    ve.eval()

    def embed(a, sr):
        y = resample(a, sr, 16000)
        with torch.inference_mode():
            e = ve.embeds_from_wavs([y], sample_rate=16000)
        e = np.asarray(e).mean(0)
        return e / np.linalg.norm(e)

    # the narrator: every edited segment at original speed
    narr = [np.load(ROOT / f"work/narr/S{i:02d}.npy") for i in range(1, 11)]
    ref_e = embed(np.concatenate(narr), SR)
    ref_f0, ref_spread = f0_stats(np.concatenate(narr[:4]), SR)
    asr_words = json.loads((ROOT / "work/asr.json").read_text(encoding="utf-8"))
    n_words = sum(len(asr_words[f"S{i:02d}"]["words"]) for i in range(1, 11))
    ref_rate = voiced_rate(np.concatenate(narr), SR, n_words)
    print(f"narrator: f0 {ref_f0:.0f} Hz, spread {ref_spread:.2f} st, rate {ref_rate:.2f} words/s voiced")

    heard = json.loads((OUT / "heard.json").read_text(encoding="utf-8"))  # from asr_takes (faster-whisper)
    meta = json.loads((OUT / "takes.json").read_text())
    rows = []
    for name, m in sorted(meta.items()):
        a, sr = load_wav(OUT / "takes" / f"{name}.wav")
        target = norm_words(LINES[m["line"]][0])
        got = norm_words(heard.get(name, ""))
        import difflib
        sm = difflib.SequenceMatcher(a=target, b=got)
        wer = 1 - sum(b.size for b in sm.get_matching_blocks()) / max(len(target), 1)
        extra = max(0, len(got) - len(target)) / max(len(target), 1)
        sim = float(embed(a, sr) @ ref_e)
        f0, spread = f0_stats(a, sr)
        rate = voiced_rate(a, sr, len(target))
        # stray noise after the last word (a common TTS artefact): energy in the last 0.4 s vs the speech
        hop = sr // 100
        n = len(a) // hop
        db = 20 * np.log10(np.sqrt(np.mean(a[: n * hop].reshape(n, hop) ** 2, 1)) + 1e-9)
        tail = float(np.percentile(db[-40:], 90) - np.percentile(db, 95))
        # the longest silence inside the take (a hesitation the narrator wouldn't make)
        quiet = db < np.percentile(db, 95) - 35
        runs, run = [], 0
        for q in quiet[np.argmax(~quiet):len(quiet) - np.argmax(~quiet[::-1])]:
            run = run + 1 if q else 0
            runs.append(run)
        gap = max(runs or [0]) / 100
        score = (sim * 10 - 12 * wer - 6 * extra - 3 * abs(np.log(rate / ref_rate))
                 - 0.6 * abs(spread - ref_spread) - 0.03 * abs(f0 - ref_f0) - (0.5 if tail > -25 else 0)
                 - 2 * max(0.0, gap - 0.45))
        rows.append({"take": name, "line": m["line"], "wer": round(wer, 3), "sim": round(sim, 4),
                     "f0": round(f0), "spread": round(spread, 2), "rate": round(rate, 2), "tail_db": round(tail, 1),
                     "max_gap_s": round(gap, 2),
                     "score": round(score, 3), "heard": heard.get(name, "")})
    best = {}
    for r in rows:
        if r["wer"] > 0.1:
            continue
        if r["line"] not in best or r["score"] > best[r["line"]]["score"]:
            best[r["line"]] = r
    for r in sorted(rows, key=lambda r: (r["line"], -r["score"])):
        flag = "*" if best.get(r["line"], {}).get("take") == r["take"] else " "
        print(flag, r)
    (OUT / "scores.json").write_text(json.dumps({"narrator": {"f0": ref_f0, "spread": ref_spread, "rate": ref_rate},
                                                 "takes": rows, "best": best}, indent=1), encoding="utf-8")
    missing = [k for k in range(len(LINES)) if k not in best]
    if missing:
        print("no clean take for lines", missing)


# -- matching to the narration -------------------------------------------------------------------------------------

def pitch_shift(x: np.ndarray, semitones: float) -> np.ndarray:
    """Pitch without tempo change: asetrate (pitch and speed) + aresample + atempo (speed back), FFmpeg via PyAV."""
    import av
    from fractions import Fraction
    from av.audio.frame import AudioFrame
    pr = 2 ** (semitones / 12)
    g = av.filter.Graph()
    src = g.add_abuffer(format="flt", sample_rate=SR, layout="mono", time_base=Fraction(1, SR))
    chain = [src, g.add("asetrate", f"{SR * pr:.3f}"), g.add("aresample", str(SR)), g.add("atempo", f"{1 / pr:.6f}"),
             g.add("abuffersink")]
    for u, v in zip(chain, chain[1:]):
        u.link_to(v)
    g.configure()
    out = []

    def drain():
        while True:
            try:
                out.append(g.pull().to_ndarray()[0])
            except (av.error.BlockingIOError, av.error.EOFError):
                return
    for i in range(0, len(x), 4096):
        fr = AudioFrame.from_ndarray(np.ascontiguousarray(x[None, i:i + 4096], np.float32), format="flt", layout="mono")
        fr.sample_rate, fr.pts, fr.time_base = SR, i, Fraction(1, SR)
        g.push(fr)
        drain()
    g.push(None)
    drain()
    return np.concatenate(out).astype(np.float32)


def tail_ms(a: np.ndarray) -> float:
    """Room feel: median time for a phrase ending to fall from -25 dBFS to -45 dBFS (10 ms envelope), normalised
    to the same speech level first."""
    from narration import env_db
    x = a / (np.percentile(np.abs(a), 99.5) + 1e-9) * 0.3
    db = env_db(x)
    tails = []
    for i in range(30, len(db) - 10):
        if db[i] < -45 and db[i - 1] >= -45 and (db[i:i + 10] < -45).all():
            j = i - 1
            while j > i - 40 and db[j] < -25:
                j -= 1
            if db[j] >= -25:
                tails.append((i - j) * 10)
    return float(np.median(tails)) if tails else 0.0


def add_room(x: np.ndarray, rt60: float, wet: float) -> np.ndarray:
    """A small synthetic room (decaying filtered noise), mixed in at `wet`."""
    from scipy.signal import butter, fftconvolve, sosfilt
    rng = np.random.default_rng(5)
    n = int(rt60 * 1.2 * SR)
    t = np.arange(n) / SR
    ir = sosfilt(butter(2, 5000, "low", fs=SR, output="sos"), rng.standard_normal(n)) * np.exp(-6.91 * t / rt60)
    ir[: int(0.003 * SR)] = 0
    ir /= np.sqrt((ir ** 2).sum())
    return (x + wet * fftconvolve(x, ir)[: len(x)]).astype(np.float32)


def band_ltas(a: np.ndarray, sr: int):
    from scipy.signal import welch
    f, p = welch(a, sr, nperseg=4096)
    return f, p


def match():
    from scipy.signal import firwin2, fftconvolve, butter, sosfilt
    sys.path.insert(0, str(Path(__file__).parent))
    from narration import compress, atempo, env_db
    sc = json.loads((OUT / "scores.json").read_text(encoding="utf-8"))
    best = {int(k): v for k, v in sc["best"].items()}
    pieces = []
    gaps = [0.40] * (len(LINES) - 1)  # between sentences: a breath, so each app screen has its moment
    for k in range(len(LINES)):
        a, sr = load_wav(OUT / "takes" / f"{best[k]['take']}.wav")
        a = resample(a, sr, SR)
        # trim the take to its speech (keep 0.05 s), as narration.py does with the narrator's files
        db = env_db(a)
        idx = np.flatnonzero(db > -50)
        s0, s1 = max(0, idx[0] * 441 - int(0.05 * SR)), min(len(a), (idx[-1] + 1) * 441 + int(0.05 * SR))
        a = a[s0:s1]
        b, _ = compress(a, [], 0.22, 0.17)  # in-line pauses: the same rule as the narration
        pieces.append(b)
        if k < len(LINES) - 1:
            pieces.append(np.zeros(int(gaps[k] * SR), np.float32))
    x = np.concatenate(pieces)
    # tempo: the narrator's edited rate; the clone is matched by measuring both
    narr = np.concatenate([np.load(ROOT / f"work/voice/S{i:02d}.npy") for i in range(1, 11)])
    asr = json.loads((ROOT / "work/asr.json").read_text(encoding="utf-8"))
    n_words = sum(len(asr[f"S{i:02d}"]["words"]) for i in range(1, 11))
    rate_n = voiced_rate(narr, SR, n_words)
    words_c = sum(len(l[0].split()) for l in LINES)
    rate_c = voiced_rate(x, SR, words_c)
    f = float(np.clip(rate_n / rate_c, 0.92, 1.12))
    x = atempo(x, f)
    print(f"tempo: narrator {rate_n:.2f} w/s, clone {rate_c:.2f} w/s -> atempo {f:.3f}")
    # pitch: if the clone's median pitch is off the narrator's by more than 0.6 semitone, move it (resample + atempo)
    f0n, _ = f0_stats(np.concatenate([np.load(ROOT / f"work/narr/S{i:02d}.npy") for i in (1, 4, 9)]), SR)
    f0c, _ = f0_stats(x, SR)
    shift = float(12 * np.log2(f0n / f0c)) if f0n and f0c else 0.0
    if abs(shift) > 0.6:  # at most 1.5 semitones: the resampling shift moves the formants with the pitch
        shift = float(np.clip(shift, -1.5, 1.5))
        x = pitch_shift(x, shift)
    else:
        shift = 0.0
    print(f"pitch: narrator {f0n:.0f} Hz, clone {f0c:.0f} Hz -> shift {shift:.2f} st")
    # tone: EQ the clone's long-term spectrum onto the narrator's (1/3-octave smoothed, +-8 dB, linear phase)
    fN, pN = band_ltas(narr, SR)
    fC, pC = band_ltas(x, SR)
    centers = 1000 * 2 ** (np.arange(-17, 14) / 3)  # 20 Hz .. 20 kHz
    gains = []
    for c in centers:
        sel = (fN >= c / 2 ** (1 / 6)) & (fN < c * 2 ** (1 / 6))
        if not sel.any():
            gains.append(0.0)
            continue
        g = 10 * np.log10(pN[sel].mean() + 1e-20) - 10 * np.log10(pC[sel].mean() + 1e-20)
        gains.append(g)
    gains = np.array(gains)
    gains -= np.median(gains[(centers > 300) & (centers < 4000)])  # level is set later; match the shape only
    usable = (centers >= 70) & (centers <= 11500)
    gains = np.where(usable, np.clip(gains, -8, 8), 0.0)
    gains = np.convolve(gains, [0.25, 0.5, 0.25], mode="same")
    freqs = np.concatenate([[0], centers[centers < SR / 2], [SR / 2]])
    resp = 10 ** (np.concatenate([[gains[0]], gains[centers < SR / 2], [0]]) / 20)
    fir = firwin2(2047, freqs / (SR / 2), resp)
    x = fftconvolve(x, fir, mode="same").astype(np.float32)
    print("EQ (dB) at 100/250/500/1k/2k/4k/8k Hz:",
          [round(float(np.interp(v, centers, gains)), 1) for v in (100, 250, 500, 1000, 2000, 4000, 8000)])
    # air: the clone stops at 12 kHz (24 kHz model); the narrator's MP3 carries some 12-16 kHz.
    sel_n = (fN >= 12000) & (fN < 16000)
    sel_mid = (fN >= 1000) & (fN < 4000)
    air_n = 10 * np.log10(pN[sel_n].mean() / pN[sel_mid].mean())
    hp = sosfilt(butter(4, 5500, "high", fs=SR, output="sos"), x)
    exc = sosfilt(butter(4, 12000, "high", fs=SR, output="sos"), np.abs(hp))  # rectified highs: harmonics above 12 k
    fX, pX = band_ltas(x, SR)
    fE, pE = band_ltas(exc, SR)
    mid_x = pX[(fX >= 1000) & (fX < 4000)].mean()
    air_e = pE[(fE >= 12000) & (fE < 16000)].mean()
    g_air = np.sqrt(10 ** (air_n / 10) * mid_x / max(air_e, 1e-20))
    x = x + (g_air * exc).astype(np.float32)
    print(f"air: narrator 12-16 kHz at {air_n:.1f} dB re 1-4 kHz; exciter gain {g_air:.3f}")
    # room: if the narrator's phrase endings ring out longer than the clone's, add a small room to match
    t_n, t_c = tail_ms(narr), tail_ms(x)
    room = (0.0, 0.0)
    if t_n > t_c + 40:  # a smaller gap is articulation, not room (a test room at 30 ms cost voice similarity)
        best = None
        for rt in (0.25, 0.35, 0.5):
            for wet in (0.04, 0.08, 0.12, 0.18, 0.25):
                d = abs(tail_ms(add_room(x, rt, wet)) - t_n)
                if best is None or d < best[0]:
                    best = (d, rt, wet)
        room = best[1:]
        x = add_room(x, *room)
    print(f"room: narrator tails {t_n:.0f} ms, clone {t_c:.0f} ms -> room rt60 {room[0]} s wet {room[1]}")
    # gate: the narrator's pauses are digital silence (about -86 dBFS); do the same between phrases
    db = env_db(x)
    gate = (db > -52).astype(float)
    gate = np.convolve(gate, np.ones(9) / 9, mode="same")  # 90 ms smoothing so word tails stay
    g = np.repeat(np.clip(gate * 1.5, 0, 1), 441)
    g = np.pad(g, (0, len(x) - len(g)), constant_values=g[-1] if len(g) else 1)
    x = (x * np.maximum(g, 10 ** (-40 / 20))).astype(np.float32)
    np.save(OUT / "mob.npy", x)
    save_wav(OUT / "mob.wav", x, SR)
    # how close the finished lines sit to the narrator, next to how close the narrator is to himself
    import torch
    from chatterbox.models.voice_encoder import VoiceEncoder
    from safetensors.torch import load_file
    ve = VoiceEncoder()
    ve.load_state_dict(load_file(MODEL / "ve.safetensors"))
    ve.eval()

    def emb(a):  # speech only: pauses would dilute the embedding differently for each side
        hop = SR // 100
        n = len(a) // hop
        fr = a[: n * hop].reshape(n, hop)
        keep = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9) > -50
        with torch.inference_mode():
            e = np.asarray(ve.embeds_from_wavs([resample(fr[keep].ravel(), SR, 16000)], sample_rate=16000)).mean(0)
        return e / np.linalg.norm(e)
    first = np.concatenate([np.load(ROOT / f"work/voice/S{i:02d}.npy") for i in (1, 2, 3, 4, 5)])
    second = np.concatenate([np.load(ROOT / f"work/voice/S{i:02d}.npy") for i in (6, 7, 8, 9, 10)])
    e1, e2, ec = emb(first), emb(second), emb(x)
    sim = {"clone_vs_narrator": round(float(ec @ ((e1 + e2) / np.linalg.norm(e1 + e2))), 4),
           "narrator_S01-05_vs_S06-10": round(float(e1 @ e2), 4)}
    print("voice-encoder similarity:", sim)
    eq = {f"{v} Hz": round(float(np.interp(v, centers, gains)), 1) for v in (100, 250, 500, 1000, 2000, 4000, 8000)}
    summary = (f"rate {rate_c:.2f} -> {rate_n:.2f} words/s (atempo {f:.3f}); pitch {f0c:.0f} vs {f0n:.0f} Hz "
               f"(shift {shift:.2f} st); EQ onto the narrator's long-term spectrum {eq}; air above 12 kHz to "
               f"{air_n:.1f} dB re 1-4 kHz; phrase tails {t_c:.0f} ms vs the narrator's {t_n:.0f} ms (room "
               f"{'none' if not room[0] else f'rt60 {room[0]} s, wet {room[1]}'}); pauses gated like the narration; "
               f"level and compression in mix.py's shared voice chain")
    summary += (f"; voice-encoder similarity to the narrator {sim['clone_vs_narrator']} (the narrator against "
                f"himself {sim['narrator_S01-05_vs_S06-10']})")
    (OUT / "match.json").write_text(json.dumps({"tempo": f, "pitch_shift_st": shift, "eq_db": eq, "similarity": sim,
                                                "air_db": float(air_n), "dur": len(x) / SR, "summary": summary},
                                               indent=1), encoding="utf-8")
    print("mobile narration", round(len(x) / SR, 2), "s")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    cmd = sys.argv[1]
    if cmd == "verify":
        sys.exit(0 if verify() else 1)
    if cmd == "ref":
        make_ref()
    elif cmd == "gen":
        generate(int(sys.argv[2]) if len(sys.argv) > 2 else 4)
    elif cmd == "pick":
        pick()
    elif cmd == "match":
        match()
