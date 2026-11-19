"""Caption text for every spoken line (the narrator's actual words, names spelled as on the site) and the alignment of
each cue to the edited voice: cue start = first word, cue end = last word, from the ASR word times carried through
narration.py, then snapped to the voice's own onsets and offsets (10 ms energy envelope), so cues sit within 0.3 s.
"""
from __future__ import annotations

import difflib
import re

import numpy as np

CUES = {
    "S00": ["KrishiNexus OS, built by Team Heat Wave.", "Tanvir Hossin, team lead.",
            "Md. Omar Faruk, AI and machine learning engineer.", "Md. Abdur Rahman, full-stack and backend.",
            "Mohammed Mahmud Parvez, full-stack developer.", "Md. Morsalin, full-stack and backend.",
            "And our advisor, Md Rifat,", "domain and network expert, joining us online."],
    "S01": ["In Bangladesh, a potato farmer often sells below cost.",
            "Between the field and the buyer, five tiers of middlemen",
            "can mark the price up by as much as 116%.", "Traders hold 77% of the cold-storage space,",
            "and a single flash flood can wipe out an entire season."],
    "S02": ["KrishiNexus OS is one AI operating system", "for everyone in that chain:",
            "the farmer, the co-op, the cold store,", "the buyer, the truck driver and the bank.",
            "Each one signs in to their own workspace."],
    "S03": ["Rahim is a potato farmer in Rangpur.", "He simply asks in his own dialect.",
            "After he gives consent, four AI agents grade his crop,",
            "compare today's market with cold storage and a shared truck,", "and check the flood risk.",
            "A circuit breaker stops him from selling below his cost,", "and it shows its working."],
    "S04": ["He can also photograph his potatoes.", "A trained vision model finds every tuber and its defects,",
            "then signs a quality certificate.", "Buyers and banks can verify that certificate for themselves."],
    "S05": ["Behind every answer, you can watch the agents work.",
            "They retrieve Bangladeshi farm data,", "call live tools through three MCP servers,",
            "and every step is traced.", "It even runs offline,", "on a fine-tuned Bangla model at a village kiosk."],
    "S06": ["Co-ops pool small harvests into full five-ton trucks.",
            "The cold store sees live chamber sensors in a 3D twin.",
            "And when a flood or heat alert arrives, the trucks are rerouted."],
    "S07": ["Rahim can also sell directly.", "He lists his lot, traders bid in the open,",
            "and he accepts the best bid.", "The payment is held in escrow.",
            "A driver takes the job", "and reports the load temperature along the road.",
            "Our shelf-life model checks that the potatoes will arrive safe,",
            "and on delivery the payment is released to Rahim."],
    "S08": ["Banks see a credit score from 300 to 850.",
            "It is backed by satellite flood checks and signed certificates.",
            "So a farmer without collateral can still get credit."],
    "S09": ["We trained five models, and we publish every score,", "including the ones that missed their targets.",
            "The app asks for consent. It removes names and phone numbers.", "It keeps data for 24 hours only,",
            "and it always leaves the final decision to the farmer."],
    "S10": ["One pooled truck covers its costs.", "A district breaks even at 16 trucks a month.",
            "We start a field test this December", "and a potato pilot in January.",
            "This is KrishiNexus OS, by Team Heat Wave.", "Try it now at tanvir.health."],
}
# one spelling for both sides (caption text and what the recogniser heard), so the two line up word for word
CANON = {"raheem": ["rahim"], "drangpur": ["rangpur"], "farouk": ["faruk"], "abdul": ["abdur"],
         "mahmoud": ["mahmud"], "drifath": ["rifat"], "mohammad": ["md"], "mohammed": ["md"], "muhammad": ["md"],
         "heatwave": ["heat", "wave"], "krishinexus": ["krishi", "nexus"], "3mcp": ["three", "mcp"], "3": ["three"],
         "5": ["five"], "science": ["signs"], "agent's": ["agents"], "it's": ["its"], "pool": ["pooled"],
         "coal": ["cold"], "op's": ["op"], "ops": ["op"], "backend": ["back", "end"], "bangladeshi": ["bangla", "deshi"],
         "escrow": ["escrow"]}


def canon_words(text: str) -> list[str]:
    out = []
    for w in re.split(r"[\s\-./]+", text.lower()):
        w = re.sub(r"[^a-z0-9']", "", w).strip("'")
        if w:
            out += CANON.get(w, [w])
    return out


def norm_tokens(text: str) -> list[str]:
    return canon_words(text)


def asr_tokens(words) -> list[tuple[str, float, float]]:
    toks = []
    for w, s, e in words:
        for k in canon_words(w):
            toks.append((k, s, e))
    return toks


def onsets_offsets(a: np.ndarray, sr: int, quiet_db: float = -48.0, min_quiet: int = 4):
    """Voice onsets (speech starting after at least 40 ms below -48 dBFS: a pause or the gap between two words) and
    offsets (speech followed by 40 ms of quiet), from the 10 ms RMS envelope. Outside the audio counts as quiet."""
    hop = sr // 100
    n = len(a) // hop
    db = 20 * np.log10(np.sqrt(np.mean(a[: n * hop].reshape(n, hop) ** 2, 1)) + 1e-9) if n else np.zeros(0)
    q = np.concatenate([np.ones(min_quiet, bool), db < quiet_db, np.ones(min_quiet, bool)])
    on, off = [], []
    for i in range(min_quiet, len(q) - min_quiet):
        if not q[i] and q[i - min_quiet:i].all():
            on.append((i - min_quiet) / 100)
        if q[i] and not q[i - 1] and q[i:i + min_quiet].all():
            off.append((i - min_quiet) / 100)
    return on, off, db


def align(seg_words, audio: np.ndarray, sr: int, cue_texts: list[str]) -> list[tuple[float, float, str]]:
    """Cue (start, end, text) in the segment's edited time."""
    asr = asr_tokens(seg_words)
    a_keys = [t[0] for t in asr]
    cue_tok = [norm_tokens(c) for c in cue_texts]
    flat, owner = [], []
    for ci, toks in enumerate(cue_tok):
        flat += toks
        owner += [ci] * len(toks)
    sm = difflib.SequenceMatcher(a=flat, b=a_keys, autojunk=False)
    match = {}
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            match[blk.a + k] = blk.b + k
    on, off, db = onsets_offsets(audio, sr)
    pauses = []  # (speech stops, speech starts again) at least 0.12 s apart
    for o in off:
        nxt = [x for x in on if x > o]
        if nxt and nxt[0] - o >= 0.12:
            pauses.append((o, nxt[0]))
    dur = len(audio) / sr
    cues = []
    for ci, text in enumerate(cue_texts):
        idx = [i for i, o in enumerate(owner) if o == ci]
        m = [match[i] for i in idx if i in match]
        if m:
            s, e = asr[min(m)][1], asr[max(m)][2]
            e0 = asr[min(m)][2]
        else:  # nothing recognised: fall back to the neighbours
            s = cues[-1][1] if cues else 0.0
            e = s + 0.35 * len(cue_tok[ci])
            e0 = s
        # snap the start to the voice. A recognised start that falls in silence moves to the next onset; a real
        # pause (0.12 s or more) ending inside the first word means the recogniser swallowed it, so the cue starts
        # where the pause ends; otherwise the onset nearest the recognised start (-0.35..+0.45 s).
        def quiet(t):
            i = int(t * 100)
            return i < len(db) and bool((db[max(0, i - 2):i + 3] < -48).all())
        if quiet(s):
            nxt = [o for o in on if s <= o <= s + 0.8]
            if nxt:
                s = nxt[0]
        else:
            inside = [b for a_, b in pauses if s - 0.05 <= b <= e0 - 0.08]
            if inside:
                s = inside[-1]
            else:
                cand = [o for o in on if s - 0.35 <= o <= s + 0.45]
                if cand:
                    s = min(cand, key=lambda o: abs(o - s))
        # the end: a recognised end in silence moves back to where the speech stopped, otherwise to the next stop
        if quiet(e):
            prv = [o for o in off if e - 0.8 <= o <= e]
            if prv:
                e = prv[-1]
        else:
            cand = [o for o in off if e - 0.1 <= o <= e + 0.7]
            if cand:
                e = cand[0]
        cues.append([max(0.0, s), min(dur, max(e, s + 0.4)), text])
    for i in range(1, len(cues)):  # no overlaps; close gaps under 0.3 s so the text doesn't flicker
        if cues[i][0] < cues[i - 1][1]:
            cues[i - 1][1] = cues[i][0]
        elif cues[i][0] - cues[i - 1][1] < 0.3:
            cues[i - 1][1] = cues[i][0]
    return [tuple(c) for c in cues]


def vtt(cues: list[tuple[float, float, str]]) -> str:
    def ts(t):
        h, r = divmod(max(0.0, t), 3600)
        m, s = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"
    lines = ["WEBVTT", ""]
    for i, (s, e, text) in enumerate(cues, 1):
        lines += [str(i), f"{ts(s)} --> {ts(e)}", text, ""]
    return "\n".join(lines)
