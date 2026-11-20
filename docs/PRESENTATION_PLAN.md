# Presentation, README and push plan

Status: **draft for review** (16 November 2026). Nothing has been changed or pushed yet.

---

## 1. What I found

### Reference decks (Drive folder "AI Battle", 24 files)

- Most decks have 6–8 widescreen (16:9) slides, with **one slide per judging criterion**, in this order:
  1. Innovation and Creativity
  2. Impact and Accessibility
  3. Feasibility and Appropriate Use of AI
  4. Sustainability and Potential to Grow
  5. Responsible AI, Ethics and Safety
- The usual shape: a title slide, an optional problem slide, the five criteria, and a thank-you slide.
- The strongest decks (AinShohay T46, Data Raiders, Algothrift) put a claim headline on every slide ("AI assists. People
  decide") and show screenshots of the working prototype.
- One file name suggests a 15-minute slot ("Slot-9.00-9.15PM").
- "KrishiSense AI" (Team AI Titans) is a direct competitor in agriculture.

### Repository

- Local `main` is at the same commit as GitHub (`17a07bb`).
- Not on GitHub yet (all uncommitted, from 15 November):
  - the role-based login and admin console: `backend/auth.py`, `backend/check_auth.py`, `frontend/src/admin/`,
    `frontend/src/pages/LoginPage.tsx`, `frontend/src/lib/roles.ts`;
  - the Cloud Run demo in `deploy/cloudrun/`;
  - edits to 13 existing files.
- The trained models (`backend/models/`) and `backend/.state/` are git-ignored, so they won't be pushed.

### README is out of date

- It doesn't mention the login, the admin console, the demo password or the hosted demo.
- "41 routes" leaves out the 9 `/auth` routes.
- The repository layout leaves out `auth.py`, `admin/` and `deploy/`.
- "Recent changes" is a long changelog that stops at Phase 10.
- `assets/team_animation.svg` shows a **6th person, Md Rifat (Domain Expert, USA)**, who isn't in the team list of five.

---

## 2. Plan

### Step 1: Push the latest work

1. Before committing, run:
   - `backend/check_auth.py`
   - `tsc --noEmit` in `frontend/`
   - the 100-case regression suite
   - a secret scan of the diff
   - a check that `AGENTS.md` and `CLAUDE.md` are still identical
2. Make three commits:
   - (a) the role-based login and admin console;
   - (b) the Cloud Run demo;
   - (c) the README and docs.
3. Push to `main`, then watch the Docker smoke test on GitHub Actions.

### Step 2: Fix README.md

- Rewrite the top so a judge understands it in 30 seconds: the three problems, a one-line answer to each, the live
  demo link, and the demo logins (password `krishi2026`).
- Add a **Team** section, with the roles already in the code (`frontend/src/story/presets.ts`):

  | Name | Role |
  |---|---|
  | Tanvir Hossin | Team Lead |
  | Md. Omar Faruk | AI/ML Engineer |
  | Md. Abdur Rahman | Full-Stack & Backend Developer |
  | Mohammed Mahmud Parvez | Full-Stack Developer |
  | Md. Morsalin | Full-Stack & Backend Developer |

- Update the route count, the layout tree, and "What is real and what is simulated" (the escrow and the login are
  demo-only).
- Shorten "Recent changes" to the last two phases and point to `docs/internal/MEMORY.md` for the full history.
- Check every figure against the code or a report before it goes in.

### Step 3: Build the deck (9 slides, 16:9, following the five criteria)

| # | Slide | Content (measured figures, or "cited in brief") |
|---|---|---|
| 1 | Title | KrishiNexus OS, the track, the team |
| 2 | Problem | 116% syndicate markup, 77.32% of storage quota held by traders and plant owners, the 2017 haor loss (cited in brief) |
| 3 | One farmer, one question | Rahim's Tk 12 sale blocked by the ΔΠ circuit breaker, answered in spoken Bangla (screenshot) |
| 4 | Innovation and Creativity | Four agents with a hard ΔΠ circuit breaker, a flood check that reads radar through monsoon cloud, a fine-tuned dialect retriever |
| 5 | Impact and Accessibility | Voice in 5 dialects, offline union kiosk, Bangla Whisper, a working phone |
| 6 | Feasibility and Appropriate Use of AI | Architecture, a 1.5B local model with no paid API keys, regression 100/100, blind retrieval top-1 0.591 → 0.955, CI passing |
| 7 | Sustainability and Potential to Grow | Pooled-truck fee, WFP centres, UCB credit, rollout one district at a time |
| 8 | Responsible AI, Ethics and Safety | PII scrubbing, signed certificates, simulated data labelled as simulated, missed targets disclosed, the farmer decides |
| 9 | Thank you | Live demo link, invitation to ask for any feature live |

- Screenshots come from the running app.
- Delivered as a `.pptx`, matching what the other teams uploaded.

### Skills to use

| Step | Skills |
|---|---|
| Push | `git-workflow-and-versioning`, `security-review`, `code-review` (on the unpushed changes) |
| README | `doc-coauthoring` |
| Deck | `pptx`, `impeccable`, `ui-ux-pro-max:slides` |
| Screenshots | `webapp-testing` |

Using literally every installed skill would add noise, so only the ones that apply are used.

---

## 3. Decisions needed

1. **Md Rifat:** remove him from the team image, or keep him as an advisor?
2. **Deck format:** a `.pptx` file (recommended), or a claude.ai slides artifact that also downloads as PowerPoint or
   PDF?
3. **Slot length and language:** 15 minutes in English? Or should the slides use Bangla headings too?
4. **Which event:** the AI Battle round, or the 26 December showcase? It changes whether the deck leads with the five
   criteria.

Step 1 (the push) doesn't depend on these answers and can start as soon as the plan is approved.

---

## 4. Decisions (16 November 2026)

- Step 1 done: pushed `0442065` (login + admin), `c831597` (Cloud Run), `cb78acf` (docs); CI run 43833194354 passed.
- Md Rifat: keep, labelled as an advisor (image and README).
- Event: the AI Battle round, 15-minute slot, English; the deck follows the five criteria.
- Format: `.pptx`.
