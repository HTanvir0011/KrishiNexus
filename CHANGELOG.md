# Changelog

Newest first. The live build state and handover log is in [`MEMORY.md`](MEMORY.md). Trained-model results are in [`README.md`](README.md#trained-models) and [`TRAINING_PLAN.md`](TRAINING_PLAN.md).

## Mobile app in Flutter (19 November 2026)

- `mobile/` is an Android (and iOS-ready) app on the same node and accounts: farmers ask in Bangla by voice and hear the
  answer, photograph the harvest for a signed grade, and sell lots; buyers bid and verify certificates; drivers run
  deliveries with temperature logs; the bank resolves disputes. See `mobile/README.md`.

## Bangla playback in every browser (19 November 2026)

- শুনুন / Listen in Bangla now plays everywhere. The device's own Bangla voice is used where there is one (Microsoft
  Edge, Chrome on Android); elsewhere the node reads the answer through an online voice (`POST /edge/tts`): Google
  Translate's Bangla voice, or Microsoft's bn-BD neural voices if Google fails. Personal details are scrubbed first,
  Offline edge mode never calls it, and `KNX_ONLINE_TTS=off` switches it off. Docs → Data safety lists it.

## Owner review fixes: grading, voice, bids, bank desk, cold-store incidents, co-op desk (19 November 2026)

- Photo grading: without a ruler in the photo, sizes are judged against the lot itself (the default), so an even lot
  grades A instead of always C; slivers and specks are no longer counted as produce.
- Voice: a photo certificate for another crop no longer blocks the question; Bangla playback waits for the browser's
  voices and uses Bangla ones where they exist (Microsoft Edge, Chrome on Android), and says so where none do.
- Direct market: bids ranked with Highest and You marks, earlier bids folded away, lead/outbid status, quick raises.
- Truck driver: summary strip, a route bar with the truck's position, a shelf-life bar; deliveries start from the
  farmer's upazila (a same-district sale was 0 km).
- New bank desk (`/os/bank`): escrow custody, transaction history, and a dispute queue that releases, refunds or holds;
  farmers, buyers and drivers can report a problem on any sale.
- Himagar: incident control with whole-plant or single-chamber drills (grid lost with the generator starting, or a total
  blackout), an alarm, a power board and a self-checking playbook; every chamber now refreshes during an incident.
- Co-op: its own desk (how pooling works, truck pools, members' lots, dispatch), instead of the judge's command centre.

## Motion, graphics and interface polish (19 November 2026)

- Overview: a new "Five hands, or one truck" card under the live decision. It draws the five-tier markup road from the
  live syndicate tool, and when you run the agents a truck drives Rahim's routed lot to the buyer and his real net
  price lands at the end. The run now names the agent at work, and the payout bars grow in.
- Workspace: a sliding pill on the navbar and seat tabs, a crossfade between seats, a route stepper on every lot and
  delivery, a flash for newly arrived bids and a released payment, and themed selection, caret and scrollbars.
- Login: the overview's dotted ground and faint farm-to-buyer routes behind the form; role-coloured icons.
- Fix: judges can open the truck driver seat (it showed a "Request failed" alert every 8 seconds).
- Every animation respects reduced motion; nothing loops.

## Direct marketplace, truck driver seat and a voice fix (17 November 2026)

- `/os/trade`: farmers list a lot and buyers bid in the open; the farmer accepts one bid, the payment is held in a
  (simulated) escrow, and a delivery job opens. A bid under the production cost needs the farmer's confirmation.
- `/os/driver`: a truck driver takes the job, reports the load's temperature on the road (shelf-life check), and
  confirms delivery, which releases the escrow to the farmer.
- Voice: Whisper now skips non-speech (a silent clip took about 2 minutes, now under a second); the farmer app has a
  typed-question box, and falls back to the browser's speech service where the server has no speech model.

## Himagar OS, cold-storage seat (17 November 2026)

- `/os/himagar` gives a cold-storage manager one facility at a time: who holds the space (traders, plant owners,
  farmers), every chamber's temperature, humidity and rot risk beside the 3D twin, a pooled slot booking that returns an
  HMAC-signed warehouse receipt, and a shelf-life check at the chamber's live reading.
- New role `storage` with the demo account `HIMAGAR-BOG-05`; judges and admins see the seat too.

## Consent, data retention, feedback and the pilot plan (17 November 2026)

- The farmer app asks for consent, in Bangla and English, before the farmer's own voice or photo is used.
- Hidden names and phone numbers now leave the PII vault after 24 hours; nothing personal is written to disk.
- Every decision ends with "Was this advice useful?"; comments are PII-scrubbed, and admins read them at `/admin/feedback`.
- The whitepaper adds per-truck unit economics, a district break-even point and a dated pilot plan (`/docs#economics`),
  and a data, consent and safety section (`/docs#data`).
- `FIELD_TEST_KIT.md` is the plan for the first study with farmers. No study has been run yet.
- `render.yaml` deploys the hosted demo on Render's free plan, with gzipped responses and an optional keep-awake
  workflow (`DEMO_URL`). Deploying it is a dashboard step for the repository owner.

## Demo login and admin console (15 November 2026)

- `/login`: a sign-in form (account ID and password) with one-click quick-login cards, grouped by role.
- `/admin`: an admin console with a sidebar for accounts (add, edit, disable, delete, restore the seeds), escrows and
  overview counts. The last active admin can't be removed.
- Passwords are stored as salted PBKDF2 hashes and never returned by the API. Session tokens are HMAC-signed and last
  12 hours. `backend/check_auth.py` checks forged, tampered and expired tokens.
- `deploy/cloudrun/` packages the frontend and API in one container for a hosted demo, with per-visitor limits on
  writes that every visitor would see.

## Buyer bids, 1-tap escrow, truck reroute and data services (Phase 10, 10 November 2026)

- **Buyer bids** (market seat, `/os/market`).
  - Every buyer for the lot is listed, best net payout first: supermarket DCs, wholesale arats, the 66 WFP centres
    and four new agro-processors. The processors (potato flakes and chips, chili paste, a rice mill) buy grades that
    retail refuses.
  - Net payout is after pooled freight, fees and transit loss. Bids under the crop's production cost are flagged.
  - Bids are modelled from DAM hub prices, not live offers from named buyers.
- **1-tap escrow.**
  - One tap locks the best bid. The amount is held for the farmer's bKash or Nagad wallet and released when the
    delivery is weighed at the buyer's door.
  - The node recomputes the bid itself, a second tap returns the same escrow, and the receipt is HMAC-signed with the
    wallet number masked.
  - **The escrow is simulated:** no money moves and no wallet API is called. A live escrow needs a merchant agreement
    and API credentials.
- **Truck reroute on transit heat** (co-op seat, `/os/coop`).
  - The co-op enters the truck's temperature. If the produce would spoil before arrival (ETA over 75% of its
    remaining shelf life), the truck is sent to the best buyer it still reaches in time, and the escrow is locked
    again there.
  - At 38 °C a potato truck keeps its route; a green-chili truck moves from a 7.2 h buyer to a 2.0 h one.
- **Data services in Compose** (`docker compose --profile data up --build`).
  - PostgreSQL + pgvector receives the 19 knowledge chunks with the vectors the app indexes.
  - Neo4j receives the supply-chain graph.
  - n8n runs the two cron jobs in queue mode on Redis.
  - The app itself still answers from its in-process stores. This profile has not yet run on a Docker host.
- **Training update.**
  - Prompts v6 fixed storage citation (0.911 on the exported model) but store-or-sell verdicts fell to 0.895, so that
    model was not shipped.
  - Prompts v7, where the circuit breaker states whether today's price is below the floor, fixed those verdicts
    (1.000 in every check). But storage citation fell to 0.85–0.89 on 14 unseen sentences, so that model was not
    shipped either.
  - The deployed model is unchanged. All results are in `TRAINING_PLAN.md` §6.
