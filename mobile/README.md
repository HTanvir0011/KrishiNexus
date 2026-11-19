# KrishiNexus mobile (Flutter)

The farmer, buyer and driver app for the KrishiNexus node. It talks to the same API as the website
(`https://tanvir.health` by default), so accounts, lots, bids, escrows and deliveries are shared with the web seats.

## What each role gets

| Role | Tabs | What works in the app |
|---|---|---|
| Farmer | Ask, Scan, Market, Me | Ask in Bangla by voice, typing or a recorded dialect question; decision cards (blocked middleman offer, pooled truck with one-tap join, cold storage with credit); the answer read aloud; photo grading with a signed certificate; list a lot (kg or maund), accept a bid into escrow, cancel, report a problem |
| Buyer | Market, Purchases, Verify, Me | Open lots by crop, bid with quick raises, lead/outbid status, won lots with payment and delivery, certificate check |
| Driver | Jobs, On the road, Me | Take a job, pick up, log truck temperature (shelf-life check against drive time), deliver (releases the farmer's payment), report a problem |
| Bank | Disputes, Ledger, Me | Resolve disputes (release, refund, keep holding), every escrow with totals |
| Judge, admin | Ask, Scan, Market, Deliveries, Me | Everything read-only, plus voice and camera |
| Co-op, cold storage | Ask, Scan, Desk, Me | Truck pools or active alerts, and a link to the full web desk |

## Camera and voice

- **Camera** (`lib/screens/scan.dart`): full-screen viewfinder with a framing guide, tap to focus, torch, gallery import,
  and "sample lot" for demos without produce. The photo (1080p JPEG) goes to `POST /edge/grade-crop`; a light sweeps it
  while the node grades, then each piece is outlined one after another, the grade is stamped, and the HMAC-signed
  certificate can be verified on the spot (`POST /edge/verify-certificate`). Tap a piece to read its size and defect.
- **Voice** (`lib/core/voice.dart`, `lib/screens/ask.dart`): the phone's own speech recogniser listens in Bangla
  (`bn-BD`, live words on screen, the orb follows the voice level); the words go to `POST /edge/voice-interact`.
  A spoken question is answered aloud: with the phone's Bangla voice, else the node's online voice (`POST /edge/tts`),
  never in Offline edge mode. If the node needs more (crop, quantity, place) it asks back, and the farmer answers by voice.
- **Consent** is asked once before the farmer's own voice, words or photo are used (same wording as the website).

## Run and build

```powershell
cd mobile
flutter pub get
flutter run                                   # a connected Android phone or emulator
flutter build apk --release                   # build/app/outputs/flutter-apk/app-release.apk
flutter build web --dart-define=API_BASE=http://localhost:8020   # browser test against a local backend
flutter analyze; flutter test
```

`--dart-define=API_BASE=...` (or Me → Server in the app) points it at another node, such as a village kiosk on the LAN.
The release APK is signed with the debug key, so it installs by sideloading; Play Store upload needs a real signing key.
iOS builds need a Mac (camera, microphone, speech and photo prompts are already in `ios/Runner/Info.plist`).

## Design

Same world as the website (`frontend/design/DESIGN_PLAN.md` §11–12): daylight canvas `#F6F8F5`, emerald `#047857`,
amber, rose, sky; Anek Bangla for the interface and Tiro Bangla for words a farmer says or hears; dark theme from the
"night paddy" palette. Material 3 components, 48 dp targets, system Back and predictive back. One authored moment (the
grade reveal: sweep, outlines, stamp); everything else is quiet feedback. "Remove animations" lands everything at once.
