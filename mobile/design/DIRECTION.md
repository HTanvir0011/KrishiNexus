# KrishiNexus mobile: design direction v2 (Flutter app)

Status: draft for the redesign branch `design/mobile-fintech-redesign`. Scope: the Flutter app in `mobile/` only.
Direction chosen with the team: **trusted fintech, in the family of the mobile-money apps farmers already use**,
**farmers first**, **Bangla first**. Replaces the Phase 8/9 "Stripe/Linear dashboard" look carried over from the website.

## 1. Why the current app reads as "AI slop"

- Hairline-outlined white cards on a pale canvas everywhere, so every screen has the same weight and no clear first action.
- Web-dashboard density (small pills, 13 px labels, many equal-priority cards) on a 360 dp phone.
- Generic Material 3 emerald with no signature; nothing says "Bangladesh" or "money".
- Money is not the hero: amounts sit in body text instead of being the biggest thing on the screen.

## 2. Research: what we looked at and what we took

| Source | Finding | What we take |
|---|---|---|
| bKash design notes by its product chief ([TBS News, Nov 2025](https://www.tbsnews.net/node/1298136)) | Moved from text-heavy to a visual, icon-led design for readers who struggle with text; "radical simplicity", low cognitive load, one-tap essentials; trust built by showing fees before sending and verifying the recipient | Big icon tiles for the few things people do; show the amount, fee and who gets it before every commit; one primary action per screen |
| bKash redesign case studies ([UX Planet, send money](https://uxplanet.org/improving-the-send-money-experience-of-the-worlds-leading-mfs-app-bkash-a-ux-case-study-28052938cbe6), [concept redesign](https://uxplanet.org/uiux-case-study-mobile-banking-app-bkash-redesign-concept-step-by-step-process-7fb71e38273d)) | Independent, uncommissioned studies; they stress short linear flows and confirmation before money moves | Confirmation sheets and receipt-style results; flows that never branch more than twice |
| GSMA AgriTech UX Design Guidebook ([PDF, Oct 2025](https://www.gsma.com/solutions-and-impact/connectivity-for-good/mobile-for-development/wp-content/uploads/2025/10/AgriTech-UX-Design-Guidebook.pdf)), sections "Mimic farm processes", "Design user-friendly interfaces", "Keep your users coming back" | Limit noise and choices; visual, textual and architectural hierarchy; local language and everyday words; imagery of familiar crops and landscapes; build on WhatsApp/mobile-money patterns (bottom bar, ticks); say what is saved offline vs synced; case study where a Cambodian farm app cut a busy home feed and added voice, marking everything voice-related in one bright colour | Short home with few big actions; one colour reserved for voice; crop imagery in icons; bottom bar and confirmation ticks; visible offline/synced state |
| Medhi Thies and colleagues, text-free and low-literacy UI research ([Microsoft Research](https://www.microsoft.com/en-us/research/?p=161317), [monograph](https://courses.cs.washington.edu/courses/cse490c/18au/readings/medhi-thies-2015.pdf)) | Text-only interfaces were unusable for first-time low-literacy users; semi-abstract graphics, voice feedback, a consistent help affordance, minimal hierarchy, little scrolling and numbers helped | Every action is icon + word; spoken feedback stays; a help button in the same place on every screen; shallow navigation |
| Bangladesh voice advisory work ([KrishokBondhu](https://arxiv.org/html/2510.18355v1), [iFarmer Folon](https://www.startupbangladesh.vc/portfolio_ifarmer_folon/)) | Voice is how Bengali farmers get past literacy limits; local apps ship Bangla, intuitive icons, offline modules | Keep voice as the centre of the farmer home |
| Accessibility floors ([Android touch target guidance](https://support.google.com/accessibility/android/answer/7101858), WCAG 2.2 target size 2.5.8) | 48 dp touch targets are the platform recommendation; WCAG 2.2 AA minimum is 24 px, AAA 44 px | 48 dp minimum everywhere, 56 dp for primary buttons and tiles |

Not verified: bKash's IDEO write-up and the GSMA landing page returned 403 to the fetcher, so nothing here comes from them.
The bKash case studies are third-party opinion, not usability data. We take patterns, not bKash's branding or magenta.

## 3. Design concept: "Krishi Wallet"

The app should feel like a wallet for a farmer's produce and payments: a bold brand header with who you are and the
one number that matters, a grid of big tiles for what you can do, and plain receipts for what happened.

- **Brand colour.** Bangladesh flag green `#006A4E` as the bold, full-bleed colour (headers, primary buttons, selected tab).
  Mustard `#EDB723` is the single accent and means "voice and money to receive". Deliberately not bKash magenta or Nagad orange.
- **Surfaces.** Soft warm-white `#F7F5EE` canvas, white cards with a soft low shadow instead of hairline borders, radius 20.
  Dark theme keeps the night-paddy palette.
- **Header band.** Rounded-bottom flag-green band on each tab's top: greeting by name in Bangla, the role, the live dot,
  and on money screens the amount as the biggest text (taka sign, tabular figures, 32 sp bold).
- **Tiles.** Home actions are 2-column icon tiles (min 112 dp tall): large icon in a tinted circle, Bangla label 16 sp, English small beneath when the language is English-first.
- **Type.** Anek Bangla and Tiro Bangla stay (bundled, offline). Body 16 sp (was 15), labels 14 sp minimum (was 13), amounts 28 to 32 sp, Bangla line height 1.5.
- **Buttons.** One primary per screen: full-width, 56 dp, radius 28, flag green. Secondary is outlined. Destructive is rose and always confirmed.
- **Status.** Always icon + colour + word, never colour alone. Money states: waiting (amber), held in escrow (sky), paid (green), disputed (rose).
- **Trust cues.** Before commit: amount, fee/deduction, who receives it (masked wallet), and a confirm button; after: a big tick, the amount and a receipt.
- **Voice.** Everything voice-related (mic, orb, read-aloud) uses mustard, as in the GSMA Mekong Farm case.
- **Help.** A "?" help affordance in the header of every tab opens the guide.
- **Motion.** Keep the existing quiet system (`Motion.of` collapses under Remove animations); one authored moment stays the grade reveal; add a success tick.
- **Navigation.** Bottom bar stays (familiar from mobile money), icon + label always visible, 64 dp, selected = filled green pill with white icon.

## 4. What changes, in order

1. Tokens and theme (`core/theme.dart`): palette, type scale, shapes, component themes, dark theme.
2. Shared widgets (`widgets/common.dart`): `AppCard`, `Pill`, new `HeaderBand`, `ActionTile`, `AmountText`, `ConfirmTick`, `SectionTitle`, `EmptyState`.
3. Shell (`screens/shell.dart`): new bottom bar.
4. Screens, by farmer priority: Ask (farmer home), Login and Signup, Me, Market, Scan chrome, then Driver, Bank, Guide, Team.

## 5. Constraints (unchanged)

All routes, API calls, role-to-tab mapping, accounts, Bangla and English text and Offline edge mode behaviour stay.
`MediaQuery.disableAnimationsOf` still lands every animation at once. No new dependencies. `flutter analyze` and `flutter test` stay clean.
