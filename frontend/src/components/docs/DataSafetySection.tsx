import { CheckCircle2, CircleAlert } from "lucide-react";

/** What the node keeps about a farmer, where, for how long and who sees it. Each row is what the code does today. */
const DATA: { item: string; handling: string; kept: string; where: string }[] = [
  { item: "Spoken or typed question", handling: "Names, phone, NID, wallet and bank numbers are replaced by tokens before any agent sees the text (guardrails/pii_scrubber.py)", kept: "For that request only; returned to the farmer who asked", where: "Memory" },
  { item: "The hidden originals", handling: "Kept in the PII vault so a local settlement service could restore them", kept: "Erased within 24 hours (VAULT_TTL_SECONDS)", where: "Memory, never disk" },
  { item: "Voice recording", handling: "Offline: transcribed on the kiosk by krishi-whisper-bn-v1, then discarded. Online: the browser's own speech service (Chrome sends audio to Google). The farmer can type instead", kept: "Not saved", where: "Kiosk memory / browser" },
  { item: "Crop photo", handling: "Graded in memory; the signed certificate keeps the grade metrics, not the image", kept: "Photo not saved; certificate until restart", where: "Memory" },
  { item: "Wallet number (escrow)", handling: "Masked before storing (017•••••344); the escrow is simulated and no money moves", kept: "Until reset", where: ".state/escrows.json" },
  { item: "Truck-pool lot", handling: "Farmer id, weight and grade", kept: "Until the pools are reset", where: ".state/truck_pools.json" },
  { item: "Account", handling: "Name, role, district and a salted PBKDF2 password hash; passwords never leave the server", kept: "Until an admin deletes it", where: ".state/users.json" },
  { item: "Sign-up identity (national ID, phone, payout wallet)", handling: "Format-checked, then kept only as HMAC-SHA256 digests under the server's signing key (to refuse duplicate accounts and to pay out only to the registered wallet) and masked forms (NID …1234, 017••••5678). The raw numbers are never stored or shown again, not even to an admin; the sign-up form keeps nothing on the device", kept: "Until an admin deletes the account", where: ".state/users.json" },
  { item: "Truck location", handling: "Only while the driver switches sharing on and a job is taken or on the road. The browser sends about 100 m (three decimals) at most every 15 s; the node keeps the last precise fix in memory and shows a point rounded to 0.01° (about 1 km) with whole-km distance. The node sends it only to the farmer, buyer and driver of that sale and to the judge, admin and bank desks; every other account gets no position. The precise fix is dropped at delivery", kept: "The last rounded point per delivery, until the market is reset", where: ".state/marketplace.json (rounded); memory (precise)" },
  { item: "Live market events", handling: "Lot id, crop and status only, with no names, wallets or locations; public, so an open page sees that something changed and reloads what its account may read", kept: "The last 200 events", where: "Memory" },
  { item: "Feedback", handling: "Useful / not useful and an optional comment, PII-scrubbed before it is stored", kept: "Latest 5,000", where: ".state/feedback.json" },
  { item: "Agent trace", handling: "Masked previews only (017******44), never the raw text", kept: "Latest 2,000 events", where: "Memory; live viewers and the admin" },
  { item: "Weather lookup", handling: "Only the district's coordinates go to Open-Meteo", kept: "Not kept", where: "—" },
  { item: "Language models", handling: "No cloud LLM is called at runtime; the fine-tuned model runs on the kiosk through Ollama", kept: "—", where: "Kiosk" },
  { item: "Spoken answer (Bangla playback)", handling: "Read by the device's own Bangla voice when it has one. Otherwise the answer text, with personal details scrubbed, is read by an online speech service (Google Translate's Bangla voice, or Microsoft's bn-BD neural voices through the open-source edge-tts library if Google fails) and the audio played back. Never in Offline edge mode; KNX_ONLINE_TTS=off switches it off", kept: "Audio of the last 48 answers in node memory; nothing on disk", where: "Node memory / Google or Microsoft speech service" },
];

const SAFEGUARDS = [
  "The farmer decides: the app recommends and explains; it never sells, stores or borrows on its own.",
  "A hard ΔΠ circuit breaker blocks a sale below the production-cost floor when storing pays more, whatever any model says.",
  "Consent is asked in Bangla before the farmer's own voice or photo is used, and recorded only on their device.",
  "Every certificate and escrow receipt is HMAC-signed, so a tampered grade reads as tampered.",
  "Modelled and simulated data carry their label in the interface (modelled telemetry, climatology fallback, simulated escrow, OFFLINE-PREVIEW).",
  "Measured scores sit beside their targets, missed targets included, and the blind test sets are frozen: nothing is tuned against them.",
];

const LIMITS = [
  "This is a demo: quick login needs no password and every API route except the admin API is open.",
  "Market prices, chamber telemetry and radar inputs are modelled, not live feeds; no real money moves.",
  "Whisper missed its character-error target, the potato defect stage missed its mask target, and the dialect retriever missed one precision target (switched on by the owner); the app quotes these scores.",
  "No study with farmers has been run yet; the field-test kit in the repository (docs/FIELD_TEST_KIT.md) is the plan for one.",
  "On the free hosted demo the disk is wiped whenever the service restarts or sleeps, so accounts, pools, escrows and feedback start fresh.",
];

export function DataSafetySection() {
  return (
    <div className="space-y-5">
      <div className="surface min-w-0 p-4 sm:p-5">
        <h3 className="text-[15px] font-semibold text-slate-900">What the node keeps about a farmer</h3>
        <div className="scroll-thin mt-3 -mx-1 overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-left text-[13px]">
            <thead>
              <tr className="border-b border-slate-200 text-[12px] text-slate-500">
                {["Data", "How it is handled", "How long", "Where"].map((h) => <th key={h} scope="col" className="px-2 py-2 font-medium">{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {DATA.map((row) => (
                <tr key={row.item} className="border-b border-slate-100 align-top">
                  <th scope="row" className="px-2 py-2 font-semibold text-slate-900">{row.item}</th>
                  <td className="px-2 py-2 text-slate-700">{row.handling}</td>
                  <td className="px-2 py-2 text-slate-700">{row.kept}</td>
                  <td className="px-2 py-2 font-mono text-[12px] text-slate-600">{row.where}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="surface p-4 sm:p-5">
          <h3 className="text-[15px] font-semibold text-slate-900">Safeguards built in</h3>
          <ul className="m-0 mt-3 grid list-none gap-2.5 p-0">
            {SAFEGUARDS.map((text) => (
              <li key={text} className="flex gap-2 text-[13.5px] leading-relaxed text-slate-700">
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-700" aria-hidden /> {text}
              </li>
            ))}
          </ul>
        </div>
        <div className="surface p-4 sm:p-5">
          <h3 className="text-[15px] font-semibold text-slate-900">Known limits, stated plainly</h3>
          <ul className="m-0 mt-3 grid list-none gap-2.5 p-0">
            {LIMITS.map((text) => (
              <li key={text} className="flex gap-2 text-[13.5px] leading-relaxed text-slate-700">
                <CircleAlert className="mt-0.5 size-4 shrink-0 text-amber-600" aria-hidden /> {text}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
