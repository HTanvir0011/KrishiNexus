# Edit notes: KrishiNexus OS demo (v2) and the 30-second problem video

Built on 19 Nov 2026 with the tools in `video/tools/v2/` (rebuild order at the end). Local only: `video/` is excluded from git.

## Files

- `frontend/public/video/krishinexus-demo.mp4`: 16.98 MB
- `frontend/public/video/krishinexus-demo.jpg`: 0.04 MB
- `frontend/public/video/krishinexus-demo.en.vtt`: 0.01 MB
- `frontend/public/video/problem-30s.mp4`: 3.54 MB
- `frontend/public/video/problem-30s.jpg`: 0.07 MB
- `frontend/public/video/problem-30s.en.vtt`: 0.00 MB
- `video/out/krishinexus-demo-1080p.mp4`: 42.59 MB
- `video/out/contact_sheet_demo.jpg`: 0.23 MB
- `video/out/contact_sheet_intro_1s.jpg`: 0.25 MB
- `video/out/contact_sheet_every_6s.jpg`: 0.30 MB
- `video/out/contact_sheet_p30.jpg`: 0.15 MB

Demo (web): 194.9 s, 1280x720 H.264 High yuv420p 30 fps (CRF 24, preset slow), AAC 48000 Hz 2 ch 134 kbps, moov before mdat: True.
Problem video: 30.0 s (900 frames), same format, moov before mdat: True.

## Revision 2 (after the owner's review of the 3:14 cut)

Narration edit and cloned lines kept as reviewed; the picture was re-rendered and the score replaced (see Music and Levels). One small re-time for the intro: a longer pause after "team lead," (0.95 s of silence instead of the cut-down pause) and a 0.40 s hold of the team grid before the problem section, so the lead's and the advisor's cards are each fully on screen for over 2 s. Everything after the intro moves 1.12 s later; the film is 194.91 s (was 193.80 s).

- Team intro rebuilt (`intro2.py`): the title, then one slot per member that starts on their spoken name (found in spoken order in the S00 word times; the lead's slot opens 0.65 s before his name, the others 0.35 s), each with a 624x780 portrait (72 % of the frame height) revealed by a rising rounded mask over a sliding amber block, a slight settle from 108 % zoom, the name and role (from team.json) rising through a mask, an amber underline drawing, and a slide-out exit; then all six in a grid popping in one by one. The cause of the broken cut: the cue for the fourth "And" matched the "and" in "AI and machine learning", so the cues were out of order and the advisor appeared at 7.5 s.
- Section titles: each heading is revealed through a mask with an amber tick; every section change is an emerald wipe with an amber leading edge (0.48 s, cover then reveal), also into the end card.
- Kinetic numbers: callout cards count up (116 %, 77.32 %, 65 %, Tk 12,000) with an exponential ease-out.
- Diagrams that build: S01 the potato price chain node by node (farmer Tk 31.42, Faria +3.78, Bepari +8.52, Aratdar +6.60, Paiker +5.50, Retailer +10.21, Dhaka shopper Tk 66.03); S03 the four agents lighting as each is named, then the middleman's Tk 4,800 struck through against the pooled truck's Tk 19,980 with the circuit-breaker note; S04 a grade stamp landing on the certificate; S05 the nine LangGraph nodes lighting in sequence; S06 a pooled truck filling and a truck rerouting from the cold store to the market; S07 the escrow flow buyer to bank to farmer with the money held, then released on delivery, and the truck driving Shibganj to Bogura (26.2 km, 34 °C, 22 h shelf life); S08 the credit gauge sweeping with a push-in on the score; S09 a phone number redacting to its token and the 24 h retention ring; the app section's live-location dot pulsing along a route; S10 break-even bars growing to 16 trucks a month and the Dec 2026 field test to Jan 2027 pilot timeline.
- Highlight boxes draw on around the figure being spoken about (the site's markup numbers, each role card in S02, the graded tubers), with callout cards for the key point of each beat.
- Kickers removed: no small all-caps label above any heading (the intro's "TEAM HEAT WAVE" and "ADVISOR", the app section's "KRISHINEXUS ON ANDROID", and the label above the problem video's heading). The problem video was re-rendered with its new matching cue.
- The end card and the score's final resolve are anchored on "This is KrishiNexus OS" after "January" (the earlier match could catch "this December").

## Structure of the demo

| Time | Section | Voice |
|---|---|---|
| 0:00.00–0:23.42 | Team intro (title, then each member as named) | narrator S00 |
| 0:23.57–0:41.49 | The problem | narrator S01 |
| 0:41.64–0:54.86 | One OS, every role | narrator S02 |
| 0:55.01–1:13.54 | The farmer asks (consent, decision, circuit breaker) | narrator S03 |
| 1:13.69–1:24.75 | Photo grading | narrator S04 |
| 1:24.90–1:39.53 | Agents, tools, offline | narrator S05 |
| 1:39.68–1:50.49 | Co-op and cold storage | narrator S06 |
| 1:50.64–2:09.42 | Direct market and delivery | narrator S07 |
| 2:09.57–2:20.32 | Credit for the farmer | narrator S08 |
| 2:20.47–2:35.79 | Honest AI, safe data | narrator S09 |
| 2:35.94–2:58.80 | The Android app (cloned narration) | cloned (owner, consented) |
| 2:58.95–3:14.91 | The road ahead, then the end card | narrator S10 |

Total 194.91 s. The picture of each section lands on its first word (0.3 s dissolve ending at the word); inside a section every recorded action is time-warped onto the word that names it (piecewise linear between named marks recorded with the clicks).

## What changed against the draft (`video/KrishiNexus_demo_draft.webm`)

- Sound: the owner's narration (11 files) with pauses over 0.35 s cut to about 0.2 s (0.22 s after a sentence, 0.17 s inside one) and a pitch-preserving 1.08x speed-up (FFmpeg atempo through PyAV); an original score; a 3:1 voice compressor and limiter. The draft was silent.
- Look: the site's daylight canvas #F6F8F5, emerald #047857 and amber, Anek Latin (the app's font files), a light browser frame, emerald/amber/rose callout cards with counting numbers and light camera zooms on the figures. The draft used a navy Heat Wave theme with yellow cards and a progress bar.
- Team intro rebuilt with the six new portraits (`frontend/public/team/*.webp`) and the names and roles from `frontend/src/data/team.json`, lead first and advisor last, each card cut on the spoken name; no group photo and no page numbers (the draft's intro ran 18 s on the old photo crops).
- Footage re-recorded today from https://tanvir.health (the site has changed): S01 now uses the whitepaper's sourced figures (116 %, 77.32 %, 65 % of Sunamganj's boro), S03 adds the landing page's circuit-breaker card, S02 shows every quick-login seat, S07's driver flow was re-shot.
- New 23 s mobile-app section before S10: the Flutter web build in a drawn phone (412x915 at 2x), with the Ask tab (Bangla home, recorded Rangpuri question, decision cards), Scan (sample lot outlined, grade stamp, certificate), a buyer's bids and a driver's route with Share live location; "Get the Android app at tanvir.health" on screen.
- Captions moved from burned-in text to WebVTT tracks (every spoken line, aligned to the voice).
- Format: MP4 H.264/AAC 1280x720 for the web plus a 1080p master; the draft was VP8 WebM without sound.

## Levels (demo)

- Voice: -16.0 LUFS integrated (target -16).
- Music under the voice: -28.74 LUFS while speaking, 12.74 dB below the voice (need >= 12); undocked bed -20.0 LUFS.
- Mix: -15.95 LUFS integrated, true peak -4.12 dBTP before AAC.
- As encoded (AAC, decoded back): -16.0 LUFS, true peak -4.37 dBTP (limit -1), AAC vs mix offset 0.0 ms.
- Ducking: -9.0 dB from the voice envelope, 80 ms attack with 80 ms look-ahead, 0.35 s hold through the gaps between sentences (so it never pumps), 0.5 s release, corners smoothed over 50 ms. At each of the 11 section changes the hold is dropped and the release is 0.15 s, so the score comes up within 0-3 dB of its -20 LUFS bed in the silence under the wipe; it also stands at full level in the 1.6 s before the app section's voice, the 3.6 s download card and the end card's tail. Music fades in over 1 s and out over 1.4 s.

Problem video: voice -16.0 LUFS, music 12.14 dB under it, encoded mix -17.05 LUFS, true peak -4.29 dBTP.

## Music

Composed in numpy (`music.py`, rewritten in revision 2), nothing sampled or downloaded:
- a soft felt-piano motif (two alternating one-bar figures on the chord tones; additive partials with string-stiffness stretch, two strings per note under a cent apart, a quiet hammer, fast-then-slow decay, the pedal held through each chord; dotted quarters only in the intro);
- a warm string bed (four detuned, slowly drifting saw voices per note through a 1.9 kHz low-pass, 2.8 kHz in the lifts), leaning +2 to +4 dB into each section change;
- a soft sine bass on the roots; a very light pulse from S02 on (felt kick on beats 1 and 3, a quiet shaker on the off-beats);
- accents: celesta-like chimes pitched from the sounding chord on the picture's hit points (19 in the demo: the team grid complete, each count-up landing (116 %, 77.32 %, 65 %, Tk 19,980, Tk 12,000, 13 tools, 5 models, 16 trucks, 1 truck), the price chain and agent pipelines completing, the credit gauge, the escrow release, the download card), a soft felt thump under the grade stamp, a two-note fall as each truck arrives, and a suspended-cymbal swell into every section change and the end card (larger into the app section);
- a synthetic convolution room as reverb.

Sync: every section starts on a downbeat as its wipe turns over; inside a section the beat is stretched around 72 BPM (70-74 BPM in practice) so a whole number of beats fits exactly, so every cut lands on a bar line. D major throughout: S00 I-vi-IV-V, the problem opens on B minor (vi-IV-I-V), the middle sections alternate I-V-vi-IV and I-vi-IV-V, the app section lifts on IV-V-vi-I with brighter strings and the motif doubled an octave up, and IV-V resolves to Dadd9 on "This is KrishiNexus OS" under the end card. The 30 s cue uses the same instruments: B minor (vi-IV-I-V), chimes as each number lands (a thump under BELOW COST), a cymbal swell and IV-V-I resolving to D as the closing card turns over.

## The cloned lines

Chatterbox (`chatterbox-tts` 0.1.7 from PyPI, CPU PyTorch 2.6.0, weights from Hugging Face ResembleAI/chatterbox) in `video/.venv-tts`. Reference: 16.6 s of the owner's S09 narration (pauses shortened, original speed). Takes per sentence: 6; each was heard back by the local faster-whisper model and scored on missing/extra words, voice-encoder similarity to the narrator, speaking rate, pitch spread and stray noise at the end. Picks:
- line 1: take 0_3 (similarity 0.9062, word error 0.0, 3.23 words/s voiced, pitch spread 3.54 st)
- line 2: take 1_5 (similarity 0.9451, word error 0.0, 3.44 words/s voiced, pitch spread 3.24 st)
- line 3: take 2_2 (similarity 0.9526, word error 0.0, 3.15 words/s voiced, pitch spread 2.72 st)
- line 4: take 3_1 (similarity 0.9562, word error 0.0, 3.25 words/s voiced, pitch spread 3.56 st)
- the narrator: 3.44 words/s voiced, median f0 130 Hz, spread 3.66 st
- matching: rate 3.31 -> 3.64 words/s (atempo 1.100); pitch 128 vs 130 Hz (shift 0.00 st); EQ onto the narrator's long-term spectrum {'100 Hz': 0.0, '250 Hz': 0.7, '500 Hz': 0.2, '1000 Hz': -0.2, '2000 Hz': -0.5, '4000 Hz': 0.1, '8000 Hz': 1.0}; air above 12 kHz to -26.7 dB re 1-4 kHz; phrase tails 85 ms vs the narrator's 115 ms (room none); pauses gated like the narration; level and compression in mix.py's shared voice chain; voice-encoder similarity to the narrator 0.9694 (the narrator against himself 0.9901)

## Captions

Demo: 66 cues, worst start 0.01 s and worst end 0.29 s from the voice's own onsets and offsets. Problem video: 5 cues, worst 0.0 s / 0.27 s. The narrator's actual wording is captioned (it differs a little from VIDEO_PLAN.md), with names as written on the site.

## Team intro check (measured on the 1080p master)

Each frame's portrait card compared with the six photos (downscaled, grey; a match needs the photo fully revealed). `video/out/contact_sheet_intro_1s.jpg` has a frame every second through the intro.

| Member | Role | Fully on screen | From | To |
|---|---|---|---|---|
| Tanvir Hossin | Team lead · Product and architecture | 2.2 s | 3.4 | 5.57 |
| Md. Omar Faruk | AI and ML engineer | 2.8 s | 6.13 | 8.9 |
| Md. Abdur Rahman | Full-stack and backend developer | 2.27 s | 9.5 | 11.73 |
| Mohammed Mahmud Parvez | Full-stack developer | 2.37 s | 12.33 | 14.67 |
| Md. Morsalin | Full-stack and backend developer | 3.4 s | 15.23 | 18.6 |
| Md Rifat | Advisor · Domain and network expert | 2.13 s | 19.2 | 21.3 |

In spoken order: True; every member at least 2 s: True. The six-portrait grid follows.

## A/V sync (first word of each section vs the moment its picture settles)

| Section | Boundary | First word | Picture settled | Word − picture |
|---|---|---|---|---|
| S01 | 23.57 | 23.61 | 23.47 | 0.14 |
| S02 | 41.64 | 41.68 | 41.6 | 0.08 |
| S03 | 55.01 | 55.04 | 54.93 | 0.11 |
| S04 | 73.69 | 73.73 | 73.63 | 0.1 |
| S05 | 84.9 | 84.94 | 84.83 | 0.11 |
| S06 | 99.68 | 99.71 | 99.63 | 0.08 |
| S07 | 110.64 | 110.67 | 110.57 | 0.1 |
| S08 | 129.57 | 129.61 | 129.5 | 0.11 |
| S09 | 140.47 | 140.52 | 140.4 | 0.12 |
| MOB | 155.94 | 157.58 | 156.1 | 1.48 |
| S10 | 178.95 | 178.98 | 178.9 | 0.08 |

## Playback check (headless Chromium)

playwright chromium 153.0.8010.12, canPlayType probably:
- krishinexus-demo: readyState 4, duration 194.9 s, 1280x720, played to 1.46 s, seek near the end ok (readyState 4), 66 caption cues parsed, ok=True
- problem-30s: readyState 4, duration 30 s, 1280x720, played to 1.46 s, seek near the end ok (readyState 4), 5 caption cues parsed, ok=True

## Notes and limits

- The mobile section is 22.9 s, not 25: the 50-word script read at the narrator's edited pace takes 17.7 s, so the phone opens on the Bangla home screen for 1.6 s before the voice and the download card holds 3.6 s after it, keeping the whole film at 194.9 s (inside 185-195 s).
- Model weights: the Hugging Face client stalled on this connection, so the same ResembleAI/chatterbox files were fetched with resumable curl range requests and checked against Hugging Face's SHA-256; T3 came as the half-size `t3_cfg.pt` (same repo) and was stored as float32 `t3_cfg.safetensors` for `from_local`.
- Recording on the live site changed demo state, as the draft's flow did: a raised bid on LOT-SEED01 (Bogura Agro Traders), the Accept form opened on Rahim's lot (not submitted), DRIVER-BOG-01 took, loaded, reported 34 °C and delivered the green chili job (payment released), one MCP tool run, one sample-lot certificate (web and app), a flood drill on HIMAGAR-BOG-05 cleared again afterwards, and in the app the driver's Share live location was switched on for a few seconds. A reset from /admin restores the seeds.
- The app was filmed from mobile/build/web with its API calls answered by https://tanvir.health through Playwright routing (the build points at localhost:8020); nothing was rebuilt and the local backend and emulator were not touched.
- `.git/info/exclude` has `video/`, which also matches `frontend/public/video/`: the six deliverables are not seen by git until that line is anchored (`/video/`) or the files are added with `git add -f`.
- Captions carry the narrator's actual words, which differ slightly from VIDEO_PLAN.md's script.

## Rebuild

```
cd video/tools/v2
python -I rec_site.py           # website shots (system python, Playwright)
python -I rec_app.py            # app shots (serve mobile/build/web on 127.0.0.1:8790 first)
# decode.py and transcribe.py (video/work) made work/narr/*.npy and work/asr.json with backend/.venv
../../.venv-tts/Scripts/python.exe narration.py ../../work/voice 1.08 0.22 0.17
../../.venv-tts/Scripts/python.exe narration.py ../../work/voice30 1.0 0.30 0.22
../../.venv-tts/Scripts/python.exe clone.py ref|gen 5|pick|match   (asr_clone.py takes|mob in backend/.venv)
../../.venv-tts/Scripts/python.exe mix.py demo; ... mix.py p30
../../.venv-tts/Scripts/python.exe build.py; ... p30.py
../../.venv-tts/Scripts/python.exe qa_media.py demo; ... qa_media.py p30; python -I qa_play.py
../../.venv-tts/Scripts/python.exe notes.py
```
