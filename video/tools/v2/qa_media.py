"""QA for the delivered files: container facts (duration, size, codecs, moov before mdat), the encoded sound's levels
(integrated LUFS, true peak, music under voice), caption parsing and timing against the voice, A/V sync at every
section start, and a contact sheet of frames at every section boundary.

Usage: python qa_media.py demo|p30   (video/.venv-tts python) -> video/out/qa_<name>.json, contact_sheet_<name>.jpg
"""
from __future__ import annotations

import json
import re
import struct
import sys
import wave
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from loud import SR, _blocks, lufs, true_peak_db  # noqa: E402
from look import font  # noqa: E402

ROOT = Path("C:/ai-congress/KrishiNexus")
WEB = ROOT / "frontend/public/video"
OUT = ROOT / "video/out"
WORK = ROOT / "video/work"


def top_boxes(path: Path) -> list[str]:
    boxes, pos, size = [], 0, path.stat().st_size
    with open(path, "rb") as f:
        while pos < size:
            f.seek(pos)
            hdr = f.read(16)
            n, kind = struct.unpack(">I4s", hdr[:8])
            if n == 1:
                n = struct.unpack(">Q", hdr[8:16])[0]
            boxes.append(kind.decode("latin1"))
            pos += n if n else size
    return boxes


def probe(path: Path) -> dict:
    c = av.open(str(path))
    info = {"file": str(path), "size_bytes": path.stat().st_size, "size_mb": round(path.stat().st_size / 1e6, 2),
            "container_duration_s": round(c.duration / 1e6, 3), "top_level_boxes": top_boxes(path)}
    info["faststart"] = info["top_level_boxes"].index("moov") < info["top_level_boxes"].index("mdat")
    for s in c.streams:
        cc = s.codec_context
        if s.type == "video":
            info["video"] = {"codec": cc.name, "profile": cc.profile, "width": cc.width, "height": cc.height,
                             "pix_fmt": cc.pix_fmt, "fps": float(s.average_rate), "frames": s.frames,
                             "duration_s": round(float(s.duration * s.time_base), 3), "bit_rate": cc.bit_rate}
        elif s.type == "audio":
            info["audio"] = {"codec": cc.name, "sample_rate": cc.sample_rate, "channels": cc.channels,
                             "bit_rate": cc.bit_rate, "duration_s": round(float(s.duration * s.time_base), 3)}
    c.close()
    return info


def decode_audio(path: Path) -> np.ndarray:
    c = av.open(str(path))
    s = c.streams.audio[0]
    res = av.AudioResampler(format="fltp", layout="stereo", rate=48000)
    chunks = []
    for fr in c.decode(s):
        for r in res.resample(fr):
            chunks.append(r.to_ndarray())
    c.close()
    return np.concatenate(chunks, axis=1)


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, w.getnchannels()).T
    return x.astype(np.float32) / 32768


def parse_vtt(path: Path) -> list[tuple[float, float, str]]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("WEBVTT"), "missing WEBVTT header"

    def secs(t):
        h, m, s = t.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    cues = []
    for block in text.strip().split("\n\n")[1:]:
        lines = block.strip().splitlines()
        tl = next(l for l in lines if "-->" in l)
        m = re.match(r"(\d\d:\d\d:\d\d\.\d{3}) --> (\d\d:\d\d:\d\d\.\d{3})", tl)
        assert m, f"bad timing line: {tl}"
        body = "\n".join(lines[lines.index(tl) + 1:]).strip()
        assert body, "empty cue"
        cues.append((secs(m.group(1)), secs(m.group(2)), body))
    for (s0, e0, _), (s1, e1, _) in zip(cues, cues[1:]):
        assert s0 < e0 <= s1 < e1, f"cue order/overlap at {s0}"
    return cues


def voice_env(voice: np.ndarray):
    v = voice.mean(0) if voice.ndim > 1 else voice
    hop = SR // 100
    n = len(v) // hop
    return 20 * np.log10(np.sqrt(np.mean(v[: n * hop].reshape(n, hop) ** 2, 1)) + 1e-9)


def cue_timing(cues, voice) -> list[dict]:
    """Each cue edge against the voice. An edge in a pause is checked against the onset (start) or offset (end) of the
    speech beside it (40 ms of quiet, as captions.py finds them): error = distance to the nearest one. An edge
    inside running speech (a cue boundary between two words with no gap) can't be seen in the envelope; it is
    reported as mid-speech and sits on the recognised word boundary."""
    from captions import onsets_offsets
    v = voice.mean(0) if voice.ndim > 1 else voice
    on, off, db = onsets_offsets(v, SR, min_quiet=2)  # word boundaries too: 20 ms dips between words count
    on, off = np.array(on), np.array(off)

    def active(t):
        i = int(t * 100)
        return bool((db[max(0, i - 8):i + 8] > -48).all())
    rows = []
    for s, e, text in cues:
        r = {"start": round(s, 2), "end": round(e, 2), "text": text[:40]}
        for edge, t, ref in (("start", s, on), ("end", e, off)):
            if active(t):
                r[edge + "_err"], r[edge + "_kind"] = 0.0, "mid-speech"
            else:
                r[edge + "_err"] = round(float(np.min(np.abs(ref - t))), 2) if len(ref) else 9.0
                r[edge + "_kind"] = "pause"
        rows.append(r)
    return rows


def frames_at(path: Path, times: list[float]) -> list[Image.Image]:
    c = av.open(str(path))
    s = c.streams.video[0]
    out, want = [], sorted(times)
    i = 0
    for fr in c.decode(s):
        t = float(fr.pts * fr.time_base)
        while i < len(want) and t >= want[i] - 1e-3:
            out.append(fr.to_image())
            i += 1
        if i >= len(want):
            break
    c.close()
    return out


def transition_end(path: Path, b: float) -> float:
    """When the dissolve into a new section is done: the first frame after b-0.5 that is closer to the new picture
    (b+0.15) than 10 % of the old-to-new distance (old = b-0.5)."""
    c = av.open(str(path))
    s = c.streams.video[0]
    c.seek(int(max(0, b - 1.5) / s.time_base), stream=s)
    fr_ = []
    for fr in c.decode(s):
        t = float(fr.pts * fr.time_base)
        if t < b - 0.5 - 1e-3:
            continue
        if t > b + 0.2:
            break
        fr_.append((t, np.asarray(fr.to_image().resize((320, 180)), np.float32)))
    c.close()
    old = fr_[0][1]
    new = min(fr_, key=lambda x: abs(x[0] - (b + 0.15)))[1]
    span = float(np.abs(old - new).mean())
    for t, a in fr_:
        if float(np.abs(a - new).mean()) <= 0.10 * span:
            return t
    return fr_[-1][0]


def time_sheet(src: Path, times: list[float], path: Path, cols: int, tw: int = 384, th: int = 216) -> str:
    """A frame at each of `times`, labelled m:ss.ss, `cols` per row."""
    imgs = frames_at(src, times)
    rows = (len(imgs) + cols - 1) // cols
    sheet = Image.new("RGB", (tw * cols, (th + 26) * rows), "white")
    d = ImageDraw.Draw(sheet)
    for i, (t, im) in enumerate(zip(times, imgs)):
        x, y = tw * (i % cols), (th + 26) * (i // cols)
        sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, y + 26))
        m, sec = divmod(t, 60)
        d.text((x + 6, y + 3), f"{int(m)}:{sec:05.2f}", font=font(18, 600), fill=(17, 24, 39))
    sheet.save(path, quality=84)
    return str(path)


def intro_check(src: Path, end: float) -> dict:
    """Which team portrait fills the intro's portrait card in each frame, measured on the video itself: the card's
    pixels (downscaled, grey) against each member's photo. Gives each member's on-screen seconds and first/last time."""
    import intro2
    box = (intro2.PX, intro2.PY, intro2.PX + intro2.PW, intro2.PY + intro2.PH)
    small = (39, 48)

    def sig(im):
        return np.asarray(im.convert("L").resize(small, Image.BILINEAR), np.float32)
    refs = [sig(intro2.portrait(m["slug"]).resize((intro2.PW, intro2.PH), Image.LANCZOS)) for m in intro2.TEAM]
    c = av.open(str(src))
    st = c.streams.video[0]
    fps = float(st.average_rate)
    hits = {i: [] for i in range(len(refs))}
    for fr in c.decode(st):
        t = float(fr.pts * fr.time_base)
        if t > end:
            break
        im = fr.to_image()
        sc = im.width / 1920
        g = sig(im.crop(tuple(int(v * sc) for v in box)))
        err = [float(np.abs(g - r).mean()) for r in refs]
        k = int(np.argmin(err))
        if err[k] < 8.0:  # the photo is fully revealed in the card (partial reveals and wipes fail this)
            hits[k].append(t)
    c.close()
    out = []
    for i, m in enumerate(intro2.TEAM):
        ts = hits[i]
        out.append({"member": m["name"]["en"], "role": m["role"]["en"], "seconds_fully_on_screen": round(len(ts) / fps, 2),
                    "first_s": round(ts[0], 2) if ts else None, "last_s": round(ts[-1], 2) if ts else None})
    firsts = [r["first_s"] for r in out]
    return {"members": out, "in_spoken_order": None not in firsts and firsts == sorted(firsts),
            "all_at_least_2s": all(r["seconds_fully_on_screen"] >= 2.0 for r in out)}


def main(name: str):
    if name == "demo":
        web, master = WEB / "krishinexus-demo.mp4", OUT / "krishinexus-demo-1080p.mp4"
        vtt = WEB / "krishinexus-demo.en.vtt"
        import timeline
        secs = timeline.load()["sections"]
        bounds = [(s["key"], s["start"]) for s in secs]
        voice_at = {s["key"]: s["voice_at"] for s in secs}
        s10 = secs[-1]
        bounds.append(("END CARD", s10["start"] + timeline.word_time(s10, "This", timeline.word_time(s10, "January")) - 0.3 + 0.45))
    else:
        web, master = WEB / "problem-30s.mp4", None
        vtt = WEB / "problem-30s.en.vtt"
        import p30
        w = p30.w  # each beat as its number lands
        bounds = [("open", 0.6), ("below cost", w("below") + 0.8), ("five tiers", w("tiers") + 0.5),
                  ("116%", w("116") + 0.9), ("77%", w("77") + 1.0), ("flash flood", w("wipe") + 0.6),
                  ("closing", p30.closing_at() + 2.4), ("end", 29.9)]
    report = {"web": probe(web)}
    if master and master.exists():
        report["master_1080p"] = probe(master)
    # sound as encoded
    enc = decode_audio(web)
    voice = read_wav(WORK / f"mix/{name}_voice.wav")
    music = read_wav(WORK / f"mix/{name}_music.wav")
    mixw = read_wav(WORK / f"mix/{name}_mix.wav")
    n = min(enc.shape[1], mixw.shape[1])
    # offset between the decoded AAC and the mix (AAC priming must be trimmed by the edit list)
    s0, s1, pad = int(10 * SR), int(13 * SR), 2400
    corr = np.correlate(enc[0, s0 - pad:s1 + pad], mixw[0, s0:s1], mode="valid")  # lags -pad..+pad
    lag = int(np.argmax(corr)) - pad
    vb = _blocks(voice[:, :n])
    speech = -0.691 + 10 * np.log10(vb + 1e-20) > -40
    report["levels_encoded"] = {
        "mix_lufs_integrated": round(lufs(enc[:, :n]), 2),
        "mix_true_peak_dbtp": round(true_peak_db(enc), 2),
        "voice_lufs_integrated": round(lufs(voice), 2),
        "voice_lufs_during_speech": round(lufs(voice, speech), 2),
        "music_lufs_during_speech": round(lufs(music, speech), 2),
        "aac_vs_mix_offset_ms": round(lag / SR * 1000, 2),
    }
    report["levels_encoded"]["music_below_voice_db"] = round(report["levels_encoded"]["voice_lufs_during_speech"] -
                                                             report["levels_encoded"]["music_lufs_during_speech"], 2)
    # captions
    cues = parse_vtt(vtt)
    db = voice_env(voice)
    timing = cue_timing(cues, voice)
    report["captions"] = {"file": str(vtt), "cues": len(cues), "max_start_err_s": max(r["start_err"] for r in timing),
                          "max_end_err_s": max(r["end_err"] for r in timing), "last_end_s": cues[-1][1],
                          "edges_at_pauses": sum((r["start_kind"] == "pause") + (r["end_kind"] == "pause")
                                                 for r in timing),
                          "edges_mid_speech": sum((r["start_kind"] != "pause") + (r["end_kind"] != "pause")
                                                  for r in timing),
                          "worst": sorted(timing, key=lambda r: -max(r["start_err"], r["end_err"]))[:4]}
    # A/V sync: each section's first word against the moment its picture settles
    if name == "demo":
        sync = []
        for key, b in bounds[1:-1]:
            k0 = int(voice_at[key] * 100) - 20  # the first rise after 0.1 s of quiet, near where its voice starts
            onset = None
            for i in range(k0, k0 + 80):
                if db[i] > -48 and (db[i - 10:i] <= -48).all():
                    onset = i / 100
                    break
            te = transition_end(web, b)
            sync.append({"section": key, "boundary_s": round(b, 2), "first_word_s": onset,
                         "picture_settled_s": round(te, 2),
                         "word_minus_picture_s": round(onset - te, 2) if onset is not None else None})
        report["av_sync"] = sync
    # contact sheet
    src = master if master and master.exists() else web
    imgs = frames_at(src, [t for _, t in bounds])
    cols = 4
    tw, th = 480, 270
    sheet = Image.new("RGB", (tw * cols, (th + 30) * ((len(imgs) + cols - 1) // cols)), "white")
    d = ImageDraw.Draw(sheet)
    for i, ((label, t), im) in enumerate(zip(bounds, imgs)):
        x, y = tw * (i % cols), (th + 30) * (i // cols)
        sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, y + 30))
        m, sec = divmod(t, 60)
        d.text((x + 6, y + 4), f"{label}  {int(m)}:{sec:05.2f}", font=font(20, 600), fill=(17, 24, 39))
    sheet_path = OUT / f"contact_sheet_{name}.jpg"
    sheet.save(sheet_path, quality=86)
    report["contact_sheet"] = str(sheet_path)
    if name == "demo":  # the intro, a frame every second; the whole film, a frame every 6 s; the portraits measured
        s01 = secs[1]["start"]
        report["contact_sheet_intro_1s"] = time_sheet(src, [i + 0.5 for i in range(int(s01))],
                                                      OUT / "contact_sheet_intro_1s.jpg", cols=6)
        total = secs[-1]["end"]
        report["contact_sheet_every_6s"] = time_sheet(src, [6.0 * i + 3.0 for i in range(int((total - 3.0) // 6) + 1)],
                                                      OUT / "contact_sheet_every_6s.jpg", cols=6, tw=320, th=180)
        report["intro"] = intro_check(src, s01)
    (OUT / f"qa_{name}.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "demo")
