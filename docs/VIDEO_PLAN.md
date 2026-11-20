# KrishiNexus OS: 180-second demo video plan

Status (18 Nov 2026): **silent captioned draft built**, `video/KrishiNexus_demo_draft.webm` (176 s, 1080p, WebM),
recorded from tanvir.health with `video/tools/rec.py` and assembled with `video/tools/assemble.py`. Waiting for the voice
(S00–S10); the final MP4 with the voice needs a full ffmpeg (Playwright's bundled one has no H.264 or audio).
Local file, not pushed (like `docs/PRESENTATION_PLAN.md`); `video/` is excluded in `.git/info/exclude`.

Draft notes: S07 shows the Accept form opening but not submitted (no wallet number typed on the live site), then cuts
to Rahim's seeded lot with "Payment held"; the driver steps run for real on Abdul's chili job. The recording changed
the live market (a Tk 18.75 bid on LOT-SEED01; LOT-SEED03 delivered); a redeploy or restart restores the seeds.
Language: English narration, Bangla shown on screen where the farmer speaks. Picture: 1920×1080, 30 fps, MP4.
Everything is filmed on the live site, https://tanvir.health.

## 1. The script (11 segments with the team intro, 427 words, about 3:00 with the intro and end card)

Read at a calm pace (about 145 words a minute). Each segment is its own audio file (section 3).

| # | Time | Narration (what you say) | On screen (what I film) |
|---|---|---|---|
| S00 | 0:00–0:18 | "KrishiNexus OS, built by Team Heat Wave. Tanvir Hossin, team lead. Md. Omar Faruk, AI and ML engineer. Md. Abdur Rahman, full-stack and backend. Mohammed Mahmud Parvez, full-stack developer. Md. Morsalin, full-stack and backend. And our advisor, Md Rifat, domain and network expert, joining online." | Animated intro (`video/tools/intro.py`): the title rises over a drifting "HEAT WAVE" watermark; then each member one by one (photo wiped up over a yellow block, name, underline and role animate in), lead first, advisor last; then the six-member group photo with a slow zoom. No page numbers. Photos: `video/assets/team_5.webp`, `team_6.webp`. |
| S01 | 0:18–0:34 | "In Bangladesh, a potato farmer often sells below cost, while five tiers of middlemen mark produce up by as much as one hundred and sixteen percent. Traders hold seventy-seven percent of cold-storage space, and one flash flood can wipe out a season." | Landing page `/`: the headline, then scroll to the problem table (116%, 77.32%, 2017 haor flood). |
| S02 | 0:14–0:26 | "KrishiNexus OS is one AI operating system for everyone in that chain: the farmer, the co-op, the cold store, the buyer, the truck driver and the bank. Each logs in to their own workspace." | `/login`: the centred form, then the quick-login cards for each role. |
| S03 | 0:26–0:48 | "Rahim, a potato farmer in Rangpur, just asks in his own dialect. After his consent, four AI agents grade his crop, compare today's market with cold storage and a shared truck, and check flood risk. A circuit breaker stops him selling below his cost, and shows the working." | Quick login `FARM-RAN-001` → `/os/field`: consent card → a Rangpuri sample question → the decision card with the ΔΠ circuit breaker and the numbers. |
| S04 | 0:48–1:00 | "He can photograph his potatoes. A trained vision model finds every tuber and its defects, and signs a quality certificate that buyers and banks can verify." | "Grade a photo" with the sample potato image → grade letter, defect list, signed certificate ID. |
| S05 | 1:00–1:14 | "Behind every answer, you can watch the agents work: retrieval from Bangladeshi farm data, live tool calls through three MCP servers, and every step traced. It even runs offline, on a fine-tuned Bangla model at a village kiosk." | Agent trace visualizer streaming steps; `/docs` MCP inspector with one live tool call; the offline-mode switch. |
| S06 | 1:14–1:30 | "Co-ops pool small harvests into full five-ton trucks. The cold store sees live chamber sensors in a 3D twin, and when a flood or heat alert hits, the trucks are rerouted." | `/os/coop`: truck-pool map; `/os/himagar`: 3D cold-storage twin; inject an anomaly → alert and reroute. |
| S07 | 1:30–1:58 | "Rahim can also sell directly. He lists his lot, traders bid in the open, and he accepts the best bid. The payment is held in escrow. A driver takes the job, reports the load temperature on the road, our shelf-life model checks it will arrive safe, and on delivery the payment is released to Rahim." | `/os/trade` as Rahim: a lot with bids → accept → "payment held"; `BUY-BOG-02` raising a bid; `/os/driver` as `DRIVER-BOG-01`: take job → loaded → 34 °C report (safe) → delivered → "payment released". |
| S08 | 1:58–2:14 | "Banks see a credit score from three hundred to eight fifty, backed by satellite flood checks and signed certificates, so a farmer without collateral can still get credit." | `/os/market` as `BANK-UCB-01`: credit gauge, flood shield, certificate verification. |
| S09 | 2:14–2:36 | "We trained five models and publish every score, including the ones that missed their targets. The app asks for consent, removes names and phone numbers, keeps data for twenty-four hours only, and always leaves the final decision to the farmer." | `/docs`: the trained-models scores and evaluation table; the data-safety table; a phone number shown as `<BD_PHONE_REDACTED>` in admin feedback. |
| S10 | 2:36–3:00 | "One pooled truck covers its costs, and a district breaks even at sixteen trucks a month. We start a field test this December and a potato pilot in January. KrishiNexus OS, by Team Heat Wave. Try it now at tanvir dot health." | `/docs#economics`: the unit-economics card and pilot timeline; end card: logo, team names, **tanvir.health**. |

Numbers in the script, and where they come from:
- 116%, 77.32% and the 2017 haor flood: README problem table, cited from the project brief.
- The five trained models and their scores: README → Trained models.
- 300–850 credit score: README.
- Break-even at 16 trucks a month, and the pilot dates: `/docs#economics`, which labels them as pilot assumptions.

## 2. Shot checklist (before filming)

1. Wake the site: open https://tanvir.health a minute early (the free plan sleeps).
2. Reset the demo state as admin, so the seeded lots and bids show. This needs the admin password from Render →
   Environment → `KNX_ADMIN_PASSWORD`. Then use `/admin`: Reset accounts, Reset marketplace, Reset truck pools.
3. Browser at 1920×1080, zoom 100%, English UI, no other tabs or notifications showing.
4. A dry run of every shot. If one fails on the day, use the local copy (http://localhost:5173) for that shot.

## 3. What I need from you: the voice

- **One audio file per segment:** `S00` … `S10`, as `.m4a`, `.mp3` or `.wav` (a phone recorder is fine).
- **Room and pacing:**
  - A quiet room, the phone 20–30 cm from your mouth, the same place for all ten.
  - Leave about 1 second of silence at the start and end of each file.
  - Don't rush to hit the exact times: I fit the picture to your voice. The full read should come to 2:50–3:05.
  - If a line trips you up, re-read the whole segment; don't splice mid-sentence.
- Put the files in `C:\ai-congress\KrishiNexus\video\voice\` and tell me.

## 4. How I'll build the video (later, once the voice is in)

1. **Check the tools:** ffmpeg and Playwright (Chromium) on this PC. Install them only with your OK.
2. **Film:** a Playwright script drives tanvir.health for each segment's shots at 1920×1080 and records one clip per
   segment. The clicks are scripted, so a retake is identical. Logins use quick login; I don't type the admin password
   anywhere.
3. **Fit to your voice:** measure each `S0x` file's length, then trim or slow each clip to match. Still frames hold
   where a page is reading.
4. **Polish:**
   - burned-in English captions, generated from the script and timed to your audio;
   - a title card (0:00) and an end card with the team and tanvir.health;
   - light zooms on the key numbers (ΔΠ, the escrow amount, the shelf-life hours);
   - no music, unless you ask.
5. **Output:**
   - `video/KrishiNexus_demo_180s.mp4`: H.264, 1080p, under 100 MB;
   - `video/KrishiNexus_demo_180s.srt`: captions;
   - a 10-frame contact sheet, so you can check it before uploading.
6. Nothing is uploaded or pushed unless you say so.
