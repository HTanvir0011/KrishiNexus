"""Writes video/out/EDIT_NOTES.md from the build's own records (timeline, mix levels, QA reports, clone scores)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import timeline  # noqa: E402

ROOT = Path("C:/ai-congress/KrishiNexus")
OUT, WORK, WEB = ROOT / "video/out", ROOT / "video/work", ROOT / "frontend/public/video"
TITLES = {"S00": "Team intro (title, then each member as named)", "S01": "The problem", "S02": "One OS, every role",
          "S03": "The farmer asks (consent, decision, circuit breaker)", "S04": "Photo grading",
          "S05": "Agents, tools, offline", "S06": "Co-op and cold storage", "S07": "Direct market and delivery",
          "S08": "Credit for the farmer", "S09": "Honest AI, safe data",
          "MOB": "The Android app (cloned narration)", "S10": "The road ahead, then the end card"}


def mmss(t):
    m, s = divmod(t, 60)
    return f"{int(m)}:{s:05.2f}"


def load(p):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def main():
    tl = timeline.load()
    v = load(WORK / "voice/timing.json")
    qd, qp, play = load(OUT / "qa_demo.json"), load(OUT / "qa_p30.json"), load(OUT / "qa_play.json")
    lv, lp = load(WORK / "mix/demo_levels.json"), load(WORK / "mix/p30_levels.json")
    sc, ct = load(WORK / "clone/scores.json"), load(WORK / "clone/match.json")
    L = ["# Edit notes: KrishiNexus OS demo (v2) and the 30-second problem video", "",
         "Built on 19 Nov 2026 with the tools in `video/tools/v2/` (rebuild order at the end). Local only: `video/` is "
         "excluded from git.", "", "## Files", ""]
    for p in [WEB / "krishinexus-demo.mp4", WEB / "krishinexus-demo.jpg", WEB / "krishinexus-demo.en.vtt",
              WEB / "problem-30s.mp4", WEB / "problem-30s.jpg", WEB / "problem-30s.en.vtt",
              OUT / "krishinexus-demo-1080p.mp4", OUT / "contact_sheet_demo.jpg", OUT / "contact_sheet_intro_1s.jpg",
              OUT / "contact_sheet_every_6s.jpg", OUT / "contact_sheet_p30.jpg"]:
        if p.exists():
            L.append(f"- `{p.relative_to(ROOT).as_posix()}`: {p.stat().st_size / 1e6:.2f} MB")
    w = qd.get("web", {})
    if w:
        L += ["", f"Demo (web): {w['container_duration_s']} s, {w['video']['width']}x{w['video']['height']} "
                  f"H.264 {w['video']['profile']} {w['video']['pix_fmt']} {w['video']['fps']:.0f} fps (CRF 24, preset slow), "
                  f"AAC {w['audio']['sample_rate']} Hz {w['audio']['channels']} ch {w['audio']['bit_rate'] // 1000} kbps, "
                  f"moov before mdat: {w['faststart']}."]
    w = qp.get("web", {})
    if w:
        L += [f"Problem video: {w['container_duration_s']} s ({w['video']['frames']} frames), same format, "
              f"moov before mdat: {w['faststart']}."]
    L += ["", "## Revision 2 (after the owner's review of the 3:14 cut)", "",
          "Narration edit and cloned lines kept as reviewed; the picture was re-rendered and the score replaced "
          "(see Music and Levels). One small re-time for the intro: a longer pause after \"team lead,\" (0.95 s of silence "
          "instead of the cut-down pause) and a 0.40 s hold of the team grid before the problem section, so the lead's "
          "and the advisor's cards are each fully on screen for over 2 s. Everything after the intro moves 1.12 s "
          f"later; the film is {tl['total']:.2f} s (was 193.80 s).", "",
          "- Team intro rebuilt (`intro2.py`): the title, then one slot per member that starts on their spoken name "
          "(found in spoken order in the S00 word times; the lead's slot opens 0.65 s before his name, the others "
          "0.35 s), each with a 624x780 portrait (72 % of the frame height) revealed by a rising rounded mask over a "
          "sliding amber block, a slight settle from 108 % zoom, the name and role (from team.json) rising through a "
          "mask, an amber underline drawing, and a slide-out exit; then all six in a grid popping in one by one. The "
          "cause of the broken cut: the cue for the fourth \"And\" matched the \"and\" in \"AI and machine "
          "learning\", so the cues were out of order and the advisor appeared at 7.5 s.",
          "- Section titles: each heading is revealed through a mask with an amber tick; every section change is an "
          "emerald wipe with an amber leading edge (0.48 s, cover then reveal), also into the end card.",
          "- Kinetic numbers: callout cards count up (116 %, 77.32 %, 65 %, Tk 12,000) with an exponential ease-out.",
          "- Diagrams that build: S01 the potato price chain node by node (farmer Tk 31.42, Faria +3.78, Bepari "
          "+8.52, Aratdar +6.60, Paiker +5.50, Retailer +10.21, Dhaka shopper Tk 66.03); S03 the four agents "
          "lighting as each is named, then the middleman's Tk 4,800 struck through against the pooled truck's "
          "Tk 19,980 with the circuit-breaker note; S04 a grade stamp landing on the certificate; S05 the nine "
          "LangGraph nodes lighting in sequence; S06 a pooled truck filling and a truck rerouting from the cold store "
          "to the market; S07 the escrow flow buyer to bank to farmer with the money held, then released on "
          "delivery, and the truck driving Shibganj to Bogura (26.2 km, 34 °C, 22 h shelf life); S08 the credit "
          "gauge sweeping with a push-in on the score; S09 a phone number redacting to its token and the 24 h "
          "retention ring; the app section's live-location dot pulsing along a route; S10 break-even bars growing "
          "to 16 trucks a month and the Dec 2026 field test to Jan 2027 pilot timeline.",
          "- Highlight boxes draw on around the figure being spoken about (the site's markup numbers, each role "
          "card in S02, the graded tubers), with callout cards for the key point of each beat.",
          "- Kickers removed: no small all-caps label above any heading (the intro's \"TEAM HEAT WAVE\" and "
          "\"ADVISOR\", the app section's \"KRISHINEXUS ON ANDROID\", and the label above the problem video's "
          "heading). The problem video was re-rendered with its new matching cue.",
          "- The end card and the score's final resolve are anchored on \"This is KrishiNexus OS\" after "
          "\"January\" (the earlier match could catch \"this December\")."]
    L += ["", "## Structure of the demo", "", "| Time | Section | Voice |", "|---|---|---|"]
    for s in tl["sections"]:
        L.append(f"| {mmss(0 if s['key'] == 'S00' else s['start'])}–{mmss(s['end'])} | {TITLES[s['key']]} | "
                 f"{'cloned (owner, consented)' if s['key'] == 'MOB' else 'narrator ' + s['key']} |")
    L += ["", f"Total {tl['total']:.2f} s. The picture of each section lands on its first word (0.3 s dissolve "
              "ending at the word); inside a section every recorded action is time-warped onto the word that names "
              "it (piecewise linear between named marks recorded with the clicks)."]
    L += ["", "## What changed against the draft (`video/KrishiNexus_demo_draft.webm`)", "",
          "- Sound: the owner's narration (11 files) with pauses over 0.35 s cut to about 0.2 s (0.22 s after a "
          f"sentence, 0.17 s inside one) and a pitch-preserving {v.get('tempo', 1.08):.2f}x speed-up (FFmpeg atempo "
          "through PyAV); an original score; a 3:1 voice compressor and limiter. The draft was silent.",
          "- Look: the site's daylight canvas #F6F8F5, emerald #047857 and amber, Anek Latin (the app's font files), "
          "a light browser frame, emerald/amber/rose callout cards with counting numbers and light camera zooms on "
          "the figures. The draft used a navy Heat Wave theme with yellow cards and a progress bar.",
          "- Team intro rebuilt with the six new portraits (`frontend/public/team/*.webp`) and the names and roles "
          "from `frontend/src/data/team.json`, lead first and advisor last, each card cut on the spoken name; no "
          "group photo and no page numbers (the draft's intro ran 18 s on the old photo crops).",
          "- Footage re-recorded today from https://tanvir.health (the site has changed): S01 now uses the "
          "whitepaper's sourced figures (116 %, 77.32 %, 65 % of Sunamganj's boro), S03 adds the landing page's "
          "circuit-breaker card, S02 shows every quick-login seat, S07's driver flow was re-shot.",
          "- New 23 s mobile-app section before S10: the Flutter web build in a drawn phone (412x915 at 2x), with "
          "the Ask tab (Bangla home, recorded Rangpuri question, decision cards), Scan (sample lot outlined, grade "
          "stamp, certificate), a buyer's bids and a driver's route with Share live location; "
          "\"Get the Android app at tanvir.health\" on screen.",
          "- Captions moved from burned-in text to WebVTT tracks (every spoken line, aligned to the voice).",
          "- Format: MP4 H.264/AAC 1280x720 for the web plus a 1080p master; the draft was VP8 WebM without sound."]
    if lv:
        L += ["", "## Levels (demo)", "",
              f"- Voice: {lv['voice_lufs_integrated']} LUFS integrated (target -16).",
              f"- Music under the voice: {lv['music_lufs_during_speech']} LUFS while speaking, "
              f"{lv['music_below_voice_during_speech_db']} dB below the voice (need >= 12); undocked bed "
              f"{lv['music_lufs_undocked']} LUFS.",
              f"- Mix: {lv['mix_lufs_integrated']} LUFS integrated, true peak {lv['mix_true_peak_dbtp']} dBTP before "
              "AAC."]
        e = qd.get("levels_encoded", {})
        if e:
            L.append(f"- As encoded (AAC, decoded back): {e['mix_lufs_integrated']} LUFS, true peak "
                     f"{e['mix_true_peak_dbtp']} dBTP (limit -1), AAC vs mix offset {e['aac_vs_mix_offset_ms']} ms.")
        d = lv.get("ducking", {})
        L.append(f"- Ducking: -{d.get('duck_db')} dB from the voice envelope, {int(d.get('attack_s', 0) * 1000)} ms "
                 f"attack with {int(d.get('lookahead_s', 0) * 1000)} ms look-ahead, {d.get('hold_s')} s hold through "
                 f"the gaps between sentences (so it never pumps), {d.get('release_s')} s release, corners smoothed "
                 f"over 50 ms. At each of the {d.get('opens_at_section_changes')} section changes the hold is dropped "
                 "and the release is 0.15 s, so the score comes up within 0-3 dB of its -20 LUFS bed in the silence "
                 "under the wipe; it also stands at full level in the 1.6 s before the app section's voice, the 3.6 s "
                 "download card and the end card's tail. Music fades in over 1 s and out over 1.4 s.")
    if lp:
        e = qp.get("levels_encoded", {})
        L += ["", "Problem video: voice {0} LUFS, music {1} dB under it, encoded mix {2} LUFS, true peak {3} dBTP.".format(
            lp["voice_lufs_integrated"], lp["music_below_voice_during_speech_db"],
            e.get("mix_lufs_integrated"), e.get("mix_true_peak_dbtp"))]
    L += ["", "## Music", "",
          "Composed in numpy (`music.py`, rewritten in revision 2), nothing sampled or downloaded:",
          "- a soft felt-piano motif (two alternating one-bar figures on the chord tones; additive partials with "
          "string-stiffness stretch, two strings per note under a cent apart, a quiet hammer, fast-then-slow decay, "
          "the pedal held through each chord; dotted quarters only in the intro);",
          "- a warm string bed (four detuned, slowly drifting saw voices per note through a 1.9 kHz low-pass, "
          "2.8 kHz in the lifts), leaning +2 to +4 dB into each section change;",
          "- a soft sine bass on the roots; a very light pulse from S02 on (felt kick on beats 1 and 3, a quiet "
          "shaker on the off-beats);",
          "- accents: celesta-like chimes pitched from the sounding chord on the picture's hit points "
          f"({(lv.get('ducking') or {}).get('hits', '?')} in the demo: the team grid complete, each count-up landing "
          "(116 %, 77.32 %, 65 %, Tk 19,980, Tk 12,000, 13 tools, 5 models, 16 trucks, 1 truck), the price chain "
          "and agent pipelines completing, the credit gauge, the escrow release, the download card), a soft felt "
          "thump under the grade stamp, a two-note fall as each truck arrives, and a suspended-cymbal swell into "
          "every section change and the end card (larger into the app section);",
          "- a synthetic convolution room as reverb.",
          "",
          "Sync: every section starts on a downbeat as its wipe turns over; inside a section the beat is stretched "
          "around 72 BPM (70-74 BPM in practice) so a whole number of beats fits exactly, so every cut lands on a bar "
          "line. D major throughout: S00 I-vi-IV-V, the problem opens on B minor (vi-IV-I-V), the middle sections "
          "alternate I-V-vi-IV and I-vi-IV-V, the app section lifts on IV-V-vi-I with brighter strings and the "
          "motif doubled an octave up, and IV-V resolves to Dadd9 on \"This is KrishiNexus OS\" under the end card. "
          "The 30 s cue uses the same instruments: B minor (vi-IV-I-V), chimes as each number lands (a thump under "
          "BELOW COST), a cymbal swell and IV-V-I resolving to D as the closing card turns over."]
    if sc:
        L += ["", "## The cloned lines", ""]
        L.append(f"Chatterbox (`chatterbox-tts` 0.1.7 from PyPI, CPU PyTorch 2.6.0, weights from Hugging Face "
                 f"ResembleAI/chatterbox) in `video/.venv-tts`. Reference: 16.6 s of the owner's S09 narration "
                 f"(pauses shortened, original speed). Takes per sentence: "
                 f"{len(sc.get('takes', [])) // max(1, len(sc.get('best', {})))}; each was heard back by the local "
                 "faster-whisper model and scored on missing/extra words, voice-encoder similarity to the narrator, "
                 "speaking rate, pitch spread and stray noise at the end. Picks:")
        for k, b in sorted(sc.get("best", {}).items(), key=lambda kv: int(kv[0])):
            L.append(f"- line {int(k) + 1}: take {b['take']} (similarity {b['sim']}, word error {b['wer']}, "
                     f"{b['rate']} words/s voiced, pitch spread {b['spread']} st)")
        n = sc.get("narrator", {})
        if n:
            L.append(f"- the narrator: {n['rate']:.2f} words/s voiced, median f0 {n['f0']:.0f} Hz, spread "
                     f"{n['spread']:.2f} st")
        if ct:
            L.append(f"- matching: {ct.get('summary', '')}")
    c = qd.get("captions", {})
    if c:
        L += ["", "## Captions", "",
              f"Demo: {c['cues']} cues, worst start {c['max_start_err_s']} s and worst end {c['max_end_err_s']} s "
              "from the voice's own onsets and offsets. Problem video: "
              f"{qp.get('captions', {}).get('cues')} cues, worst {qp.get('captions', {}).get('max_start_err_s')} s / "
              f"{qp.get('captions', {}).get('max_end_err_s')} s. The narrator's actual wording is captioned (it "
              "differs a little from VIDEO_PLAN.md), with names as written on the site."]
    it = qd.get("intro", {})
    if it:
        L += ["", "## Team intro check (measured on the 1080p master)", "",
              "Each frame's portrait card compared with the six photos (downscaled, grey; a match needs the photo "
              "fully revealed). `video/out/contact_sheet_intro_1s.jpg` has a frame every second through the intro.", "",
              "| Member | Role | Fully on screen | From | To |", "|---|---|---|---|---|"]
        for r in it["members"]:
            L.append(f"| {r['member']} | {r['role']} | {r['seconds_fully_on_screen']} s | {r['first_s']} | "
                     f"{r['last_s']} |")
        L += ["", f"In spoken order: {it['in_spoken_order']}; every member at least 2 s: {it['all_at_least_2s']}. "
                  "The six-portrait grid follows."]
    s = qd.get("av_sync", [])
    if s:
        L += ["", "## A/V sync (first word of each section vs the moment its picture settles)", "",
              "| Section | Boundary | First word | Picture settled | Word − picture |", "|---|---|---|---|---|"]
        for r in s:
            L.append(f"| {r['section']} | {r['boundary_s']} | {r['first_word_s']} | {r['picture_settled_s']} | "
                     f"{r['word_minus_picture_s']} |")
    if play:
        L += ["", "## Playback check (headless Chromium)", ""]
        b = play.get("browser", {})
        L.append(f"{b.get('channel')} {b.get('version')}, canPlayType {b.get('canPlayType')}:")
        for name in ("krishinexus-demo", "problem-30s"):
            r = play.get(name)
            if r:
                L.append(f"- {name}: readyState {r['readyState']}, duration {r['duration']} s, "
                         f"{r['videoWidth']}x{r['videoHeight']}, played to {r['playedTo']:.2f} s, seek near the end "
                         f"ok (readyState {r['seekedReadyState']}), {r['cues']} caption cues parsed, ok={r['ok']}")
    L += ["", "## Notes and limits", "",
          "- The mobile section is 22.9 s, not 25: the 50-word script read at the narrator's edited pace takes 17.7 s, "
          "so the phone opens on the Bangla home screen for 1.6 s before the voice and the download card holds 3.6 s "
          f"after it, keeping the whole film at {tl['total']:.1f} s (inside 185-195 s).",
          "- Model weights: the Hugging Face client stalled on this connection, so the same ResembleAI/chatterbox files "
          "were fetched with resumable curl range requests and checked against Hugging Face's SHA-256; T3 came as the "
          "half-size `t3_cfg.pt` (same repo) and was stored as float32 `t3_cfg.safetensors` for `from_local`.",
          "- Recording on the live site changed demo state, as the draft's flow did: a raised bid on LOT-SEED01 "
          "(Bogura Agro Traders), the Accept form opened on Rahim's lot (not submitted), DRIVER-BOG-01 took, loaded, "
          "reported 34 °C and delivered the green chili job (payment released), one MCP tool run, one sample-lot "
          "certificate (web and app), a flood drill on HIMAGAR-BOG-05 cleared again afterwards, and in the app the "
          "driver's Share live location was switched on for a few seconds. A reset from /admin restores the seeds.",
          "- The app was filmed from mobile/build/web with its API calls answered by https://tanvir.health through "
          "Playwright routing (the build points at localhost:8020); nothing was rebuilt and the local backend and "
          "emulator were not touched.",
          "- `.git/info/exclude` has `video/`, which also matches `frontend/public/video/`: the six deliverables are "
          "not seen by git until that line is anchored (`/video/`) or the files are added with `git add -f`.",
          "- Captions carry the narrator's actual words, which differ slightly from VIDEO_PLAN.md's script."]
    L += ["", "## Rebuild", "",
          "```", "cd video/tools/v2",
          "python -I rec_site.py           # website shots (system python, Playwright)",
          "python -I rec_app.py            # app shots (serve mobile/build/web on 127.0.0.1:8790 first)",
          "# decode.py and transcribe.py (video/work) made work/narr/*.npy and work/asr.json with backend/.venv",
          "../../.venv-tts/Scripts/python.exe narration.py ../../work/voice 1.08 0.22 0.17",
          "../../.venv-tts/Scripts/python.exe narration.py ../../work/voice30 1.0 0.30 0.22",
          "../../.venv-tts/Scripts/python.exe clone.py ref|gen 5|pick|match   (asr_clone.py takes|mob in backend/.venv)",
          "../../.venv-tts/Scripts/python.exe mix.py demo; ... mix.py p30",
          "../../.venv-tts/Scripts/python.exe build.py; ... p30.py",
          "../../.venv-tts/Scripts/python.exe qa_media.py demo; ... qa_media.py p30; python -I qa_play.py",
          "../../.venv-tts/Scripts/python.exe notes.py", "```"]
    (OUT / "EDIT_NOTES.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(OUT / "EDIT_NOTES.md")


if __name__ == "__main__":
    main()
