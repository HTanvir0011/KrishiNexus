# KrishiNexus: immersive website, design plan v1 (for review)

Status: **approved 2026-10-24 and built** (see section 10 for what changed during the build). A visual style tile with the palette, type and a hero
mock is at `frontend/design/style-tile.html` (open `http://localhost:5173/design/style-tile.html` with the dev
server running).

References studied:
- curtisdesignr.me: a live HUD with coordinates and clock, a hairline grid, a condensed display face, scroll-pinned statements.
- portalsystems.space: a cinematic hero, then one persistent world (the globe) that the whole scroll story happens over.
- vay.io: calm product storytelling, with live status cards floating over the scene and a short, real step sequence.
- AgrixAI shot: frosted glass panels over a misty field, arc gauges, deep green.

What we take from them is the **structure**: a persistent world, a HUD that reports real state, and live cards over
the scene. What we don't take is their look. Our concept is different: a farmer's own question, answered by four agents.

---

## 1. Decisions for you

| # | Question | Recommendation |
|---|---|---|
| 1 | Where does the story live? | Story at `/`; the live OS at `/os` (judge split-screen by default, plus `/os/field`, `/os/coop` and `/os/market`); whitepaper stays at `/docs`. "Live OS" in the header keeps the demo one click away. |
| 2 | Landscape | **Stylised delta**: a procedural field mosaic, with real place coordinates and road distances from `bd_geo`. A literal Bangladesh outline would need a public-domain shapefile (Natural Earth) downloaded and simplified, so I'd only do that if you want it. |
| 3 | Language | Every farmer quote and the spoken answers in Bangla, each with an English line beneath; interface chrome in English. A full English/বাংলা toggle is possible but doubles the copy. |
| 4 | Imagery | **Procedural only**: no stock or generated photos. It works offline at the kiosk, needs no licences, and every pixel is driven by the same data as the agents. |

---

## 2. Concept: "Sell now, or keep them in cold storage?"

The site follows **one real question** through the system. It's the Rangpuri voice preset the backend already ships:

> বাহে, মুই মিঠাপুকুরের রহিম মিয়া … হামার ঘরত দশ মণ লাল পাকরি আলু আছে। ফড়িয়া কয় বারো টাকা কেজি দিবে।
> **এলা বেচমু না হিমাগারত থুমু?**
>
> Rahim Mia of Mithapukur, Rangpur: 10 mon (400 kg) of red potatoes, the Faria offers Tk 12 a kilo.
> "Should I sell now, or keep them in cold storage?"

The page is a **night flight over the delta that ends at dawn**. Perishables travel at night, so the story starts
before sunrise at Rahim's plot. It follows the potatoes down the road to Dhaka, drops into the cold stores, flies to
the haor where Abdul faces a flood, and ends at dawn with the answer spoken back in Bangla. From there you enter the live OS.

The memorable thing (the one place we spend boldness): **one persistent landscape whose camera moves with your
scroll, with the farmer's own words set large over it.** Everything else stays quiet: text columns, honest numbers, few controls.

---

## 3. Tokens

### Colour (6 core + 2 supporting)

| Name | Hex | Role | Contrast on base |
|---|---|---|---|
| Night paddy | `#0E211A` | Base background: pre-dawn paddy, clearly green, not black | — |
| Flag green | `#006A4E` | Brand, healthy state, the in-band zone on gauges, active nav fill (husk text on it is 5.5:1) | fills only (2.5:1 as text) |
| Mustard | `#EDB723` | The one accent: primary actions, focus ring, Rahim's plot, "money you keep". Mustard blooms across Bangladesh in December, the week of the 26 Dec showcase. | 9.1:1 |
| Husk | `#EFEBDD` | Primary text: dried rice-husk white | 14.1:1 |
| Sun red | `#F2545B` text / `#F42A41` fill | Alerts only: syndicate markup, blocked sale, RED flood | 4.9:1 |
| Monsoon | `#6FA8B5` | Water, flood and radar data; second data series | 6.4:1 |
| *Delta* (supporting) | `#17352A` | Raised surfaces, the glass tint | — |
| *Silt* (supporting) | `#9DB0A3` | Secondary text, labels | 7.3:1 |

Scroll-linked atmosphere: the sky gradient behind the landscape moves from night paddy (`#0E211A`) to a dawn mix
(`#1B3A2E` with a low mustard horizon glow) as the story progresses. It's the only ambient colour change.

### Type: two families, each with a job

- **Tiro Bangla** (Tiro Typeworks: John Hudson and Fiona Ross; serif, Bangla and Latin) is **the human voice**.
  It's used only for what a farmer says and what the system says back aloud. Hero 88–120 px, line height 1.25;
  never below 18 px.
- **Anek Bangla** (Ek Type; variable width 75–125, weight 100–800; Bangla and Latin) is **the system**: headings,
  interface, body text and numbers. **Width encodes role**:
  - `wdth 75`, weight 600: numbers and gauges, tall and narrow;
  - `wdth 100`, weight 400–500: body and interface;
  - `wdth 118`, weight 650: chapter headlines.
- Scale (px): 13 · 15 · **17 body** (line height 1.6, Bangla 1.7) · 21 · 26 · 34 · 48 · 72 · 112.
  Line length ≤ 68 characters.
- Rules: sentence case everywhere; no all-caps labels; no monospace (data labels are Anek condensed); no arrow
  glyphs appended to buttons.
- Both fonts are self-hosted (`@fontsource-variable/anek-bangla`, `@fontsource/tiro-bangla`), so the kiosk works
  offline. The style tile loads them from Google Fonts only as a preview.

### Shape and depth

- Radius by hierarchy: OS page panels 24 px, cards inside them 14 px, chips and pills 999 px.
  The story chapters themselves have no boxes.
- Glass is used only in the OS:
  - fill: delta at 55 % opacity;
  - backdrop blur: 18 px;
  - border: 1 px top highlight (husk at 8 %);
  - no drop shadows.
- Focus: 2 px mustard outline, 3 px offset, on every interactive element.

---

## 4. Layout

Left-aligned throughout. The story text sits in a 5/12 column on the left (max 34 rem). The landscape fills the
viewport behind, with each chapter's camera target offset into the right 7/12, so text never covers the action.

### Hero (desktop)

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ KrishiNexus   Story  Live OS  Whitepaper          Backend live  25.57°N 89.28°E 04:52 │
│                                                                                      │
│ Rahim Mia farms in Mithapukur, Rangpur.        ░░▒▒▓▓ field mosaic, pre-dawn ▓▒░     │
│                                                ▒▓   ◯ 5 km union ring        ▓▒      │
│ এলা বেচমু না                                    ▓    ▣ Rahim's plot (mustard)  ▓      │
│ হিমাগারত থুমু?            ← Tiro Bangla 112px   ▒▓   · neighbours' plots     ▓▒      │
│ ∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿     ← the line sits on its own waveform                       │
│ [400 kg red potatoes] [Faria offers Tk 12] [Phone number hidden]  ← tags appear as   │
│                                                                    he speaks         │
│ "Should I sell now, or keep them in cold storage?"  Rangpuri                         │
│                                                                                      │
│ ( Play his question )   ( Ask in another dialect ▾ )   Type a question               │
│                                                                    ১ ২ ৩ ৪ ৫ ৬       │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

- **HUD** (Curtis-style, but functional): the coordinates are the camera's current place and change per chapter,
  the clock is BDT, and backend status is live.
- **Chapter rail** (right edge): Bangla numerals ১–৬, because the story is a real sequence. Each shows its place
  name on hover or focus and acts as a skip link.

### Chapters (each a tall scroll section, text left, the landscape acts right)

| | Chapter | Camera | What the reader does |
|---|---|---|---|
| ১ | **Who holds the cold**: "77 of every 100 chambers are booked before a farmer arrives." | Drops onto Rangpur's 4 BCSA blocks; each block's 100 chambers fill: traders, owners, farmers | District picker (live quota); *Simulate a power cut* drives the chamber gauge out of the 48–50 °F band |
| ২ | **The road to Dhaka**: "The Faria offers Tk 12. In Karwan Bazar the same potato sells for Tk 78." | Follows the real road Mithapukur → Bogura → Jamuna bridge → Karwan Bazar; each tier rises as a price post on the road | Scroll moves the truck; a toggle swaps *Syndicate route* and *Pooled truck*; focusing a post shows that tier's margin and the Bepari cost lines (the Aratdar takes 62.35 % of them) |
| ৩ | **Rahim's answer**: sell, store or pool | Three light trails from his plot: Faria gate, cold store, pooled truck; the winning one brightens | Shows the ΔΠ values; plays the Bangla answer aloud (Tiro Bangla on screen, English beneath) |
| ৪ | **Abdul's question**: "অখন কাটমু নি?" ("Should I cut it now?"), Sylheti, Tahirpur | Flies north-east to the Sunamganj haor under a cloud layer | **Drag the radar divider** to see through the clouds: Sentinel-1 water spreading; live breach risk and the 72-hour harvest window |
| ৫ | **Four agents, one answer** | Pulls up to the whole delta; agent pipeline overlay | *Run the agents* triggers a live orchestration; the WebSocket trace lights each step (numbered, because it is a sequence) |
| ৬ | **Open the OS**: dawn | Settles at sunrise over Rahim's union | Buttons: *Open the live OS*, *Open judge mode*, *Read the whitepaper*; team roster below |

### Live OS (`/os`): AgrixAI-style glass over the same landscape, frozen at dawn and blurred

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ KrishiNexus   Story  Live OS  Whitepaper                       Backend live  04:52   │
│ ( Field )( Co-op & storage )( Market & credit )( Judge mode )     Simulate ▾         │
│ ┌ Rahim's lot ──────────────┐ ┌ Chamber CH-03 ─────────────┐ ┌ Truck pool ─────────┐ │
│ │ Grade A, 96.2 %           │ │   ◜ 48–50 °F band ◝         │ │   ◯ 4,600/5,000 kg  │ │
│ │ Pool beats the Faria by   │ │   49.1 °F   RH 93 %         │ │   8 neighbours       │ │
│ │ Tk 51/kg                  │ │   ( Simulate power cut )    │ │   ( Join the pool )  │ │
│ └───────────────────────────┘ └─────────────────────────────┘ └──────────────────────┘ │
│ ┌ Agent trace, live ─────────────────────────────────┐ ┌ Credit 782 of 850 ─────────┐ │
│ │ streamed events                                     │ │ dial · Tk 15,000 at 6 %   │ │
│ └─────────────────────────────────────────────────────┘ └────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

- **Existing features are kept and re-skinned, not rewritten**: farmer app, command center with the 3D cold-store
  twin, pool radar, bank and B2B portal, the `/docs` sections. Same store, same API client, same offline fallbacks.
- **Gauges:**
  - chamber temperature: an arc with the 48–50 °F band in flag green and a mustard needle;
  - relative humidity;
  - credit: a 300–850 dial;
  - pool fill: a ring to 5,000 kg;
  - flood: a 72-hour risk bar.
  - Every number is set in Anek condensed.

### Mobile (≤ 640 px)

```
┌───────────────────────┐
│ KrishiNexus        ☰  │
│ ░▒▓ landscape band ▓▒░ │  sticky, 40 vh
├───────────────────────┤
│ এলা বেচমু না           │  Tiro Bangla 44px
│ হিমাগারত থুমু?         │
│ ∿∿∿∿∿∿∿∿∿∿∿∿∿∿         │
│ tags wrap             │
│ ( Play his question ) │  full-width, 48 px tall
└───────────────────────┘
```

The OS collapses to one column, with the segmented nav scrolling horizontally.

---

## 5. Interaction and motion

**One orchestrated moment** is the hero, on load, once:
1. The landscape fades up from dark.
2. Rahim's question writes itself along the waveform, word by word.
3. The extracted-fact tags appear (400 kg, Tk 12, phone hidden). This is the real PII scrub and entity extraction
   from `/edge/voice-interact`.

That takes about 2.5 s. *Play his question* repeats it with Bangla speech (browser TTS).

Everything else is either **scroll-linked**, so the reader drives it (the camera moves only while you scroll), or
**a response to an action**:
- the route toggle;
- dragging the radar divider;
- *Run the agents*, which lights each step as its trace event arrives;
- *Simulate power cut*, which pushes the gauge out of the band.

Deliberately absent: fade-up on every section, hover-lift on cards, auto-playing counters, scroll-jacking (native
scroll with sticky stages).

**Reduced motion:** the camera cuts between chapter stills with a ≤ 200 ms crossfade, nothing drifts, and the hero
shows its final state immediately.

Honest labels: speech-to-text needs the on-device Whisper model, which isn't installed. So the hero offers the five
recorded dialect questions or typing, and says so in one line. The waveform is drawn from the sentence's syllables
and is labelled as an illustration.

---

## 6. Live data per chapter (all with the existing offline fallbacks)

| Chapter | Endpoint |
|---|---|
| Hero, ৩ | `POST /edge/voice-interact` (preset `rangpur_potato_distress`): transcript, entities, PII, Bangla answer, full agent state |
| ১ | `query_cold_storage_quota`, `get_chamber_telemetry`, `POST /mcp/simulate-anomaly` |
| ২ | `detect_syndicate_markup_anomaly` (tiers, Bepari cost lines), `find_optimal_selling_hub` |
| ৪ | `calculate_haor_flash_flood_risk`, `POST /automation/n8n/hourly-sar-flood-check`, voice preset `sunamganj_haor_flood` |
| ৫ | `POST /agents/orchestrate` + `WS /ws/agent-trace` |
| OS | unchanged from today |

Copy numbers are **templated from these responses**, not typed in, so the page and the agents never disagree.
Seasonal prices change by date, and the copy says "today's DAM-modelled prices".

---

## 7. Accessibility and performance floor

- The canvas is `aria-hidden`; every fact the landscape shows is also in HTML (place labels are HTML overlays, not
  canvas text).
- `lang="bn"` on Bangla text.
- All text pairs ≥ 4.5:1 (table above).
- Touch targets ≥ 44 px.
- *Play his question* is a real button with a visible "Speaking…" state.
- Chapter rail = skip links.
- WebGL fallback: a static SVG mosaic. If WebGL is missing or the device is low-power, the landscape renders once
  and stops.
- Render loop pauses when the tab is hidden; device pixel ratio capped at 1.5.
- Route-level code-splitting (story, OS, docs) also fixes the current 934 kB single bundle.
- Fonts and landscape need no network; the story works with the backend offline, using the existing cached-demo
  fallbacks and a visible "cached demo" HUD state.

---

## 8. Review against the brief: what I changed from my first instincts

1. **Palette.** The first instinct was the AgrixAI and Curtis look: near-black with acid lime, which is the most
   common generated look right now. It's now a genuinely green night paddy with **mustard** as the single accent,
   which is seasonal and national: mustard is in bloom for the 26 Dec showcase. Flag green is the brand colour, and
   red is reserved for alerts.
2. **Hero.** The first instinct was a drone-style photo with a big-number stats row. Now the hero is **the farmer's
   own dialect question**, the real input to the product, set on its own waveform with the system's understanding
   shown as tags.
3. **Type.** The first instinct was Inter with monospace data labels and all-caps eyebrows. Now it's a two-family
   system where the family itself carries meaning: serif for the human voice, variable sans for the system, with
   width as a role signal.
4. **Structure.** The first instinct was identical rounded cards and a fade-up on every section. Now one persistent
   world carries the story, chapters are text over it, cards appear only in the OS, and radius follows hierarchy.
5. **Numbering** is used only where order is real: the story's chapters (Bangla numerals) and the agent pipeline.
6. **Imagery.** Stock photography is replaced with a procedural landscape that runs offline and is driven by the
   same data.

---

## 9. Build plan after approval

1. **Foundation:**
   - tokens in `index.css` `@theme`;
   - self-hosted fonts;
   - primitives (`Button`, `GlassPanel`, `ArcGauge`, `Ring`, `Chip`, `Hud`);
   - routing for `/`, `/os[/field|/coop|/market]` and `/docs`, with `React.lazy` code-splitting.
2. **Landscape engine** (`src/story/landscape/`, pure Three.js, no new 3D libraries):
   - field-mosaic shader, rivers and roads;
   - places projected from real `bd_geo` coordinates;
   - storage blocks (instanced), haor water and cloud layer with a radar reveal mask, truck light on the route curve;
   - camera keyframes per chapter, a scroll controller, and the reduced-motion and no-WebGL fallbacks.
3. **Story chapters:** hero, ১–৬, wired to the live endpoints above.
4. **OS re-skin:** field, co-op and storage, market and credit, judge split, docs.
5. **QA:**
   - `tsc` and build;
   - browser checks at 1440 px and 390 px;
   - keyboard-only pass, reduced motion, backend-offline;
   - bundle-size check;
   - `MEMORY.md` and `AGENTS.md` updates.

New dependencies: only the two font packages. No GSAP or smooth-scroll library; scroll progress is a small
`requestAnimationFrame` hook.

---

## 10. What changed during the build (2026-10-24)

- **Chapter order:** "Who holds the cold" now comes before "The road to Dhaka". His cold stores are next to his plot, so the
  camera goes plot, cold stores, road south, then zooms out, instead of flying back north from Dhaka. It also matches his
  question: store first, then sell.
- **Rahim's answer** compares the three choices as proportional bars (taka for his 400 kg) rather than three light trails;
  the bars are easier to read, and the map keeps his plot and the lit road.
- **Offline honesty:** the story has its own dated snapshot of Rahim's and Abdul's runs and the Rangpur quota. For any
  other district offline, the chapter says a sample cold store is shown.
- **Rendering fixes found in testing:**
  - fog distance is now computed per pixel from the world position (interpolating it across the two-triangle ground plane
    fogged everything);
  - the fog colour is passed to the custom shaders in sRGB.
- **Machine-specific:** port 8000 on this PC is taken by `claude-science.exe serve`, so the dev proxy target comes from
  `KNX_BACKEND_URL`. The launch config `krishinexus-frontend-8002` serves the site on 5175 against the backend on 8002.
- **Found in the screenshot review (headless Chrome, 1440 px and 390 px):**
  - The cold-storage still is framed from the district's stores (bounding-box centre, distance from their spread), so
    no store sits under the text column in any of the four districts.
  - Cold-store towers fade out before the road chapter, where they read as price posts.
  - Rahim's answer pulls back far enough to show the whole road, his plot to Karwan Bazar.
  - Map labels flip to the left near the right edge and the chapter rail. Labels that overlap are lifted on desktop;
    on a phone the later one is hidden. The pooled-truck label rides with the truck.
  - The floating header has a fading shade so chapter text no longer runs into the links. On a phone it uses two rows
    and scrolls away, so the landscape band keeps the top of the screen.
  - The live OS cold-storage twin now uses the story's quota colours (traders slate, plant owners sky, farmers mustard).
  - Typed English questions with plural crop names ("potatoes") were asked for the crop; the lexicon now accepts
    English plurals for crop names.
