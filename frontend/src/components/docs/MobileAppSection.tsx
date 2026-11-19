import { ArrowRight, Camera, Mic, ShieldCheck } from "lucide-react";

import site from "../../data/site.json";
import { Link } from "../../lib/router";
import { AppDownload } from "../AppDownload";

/** What each role gets in the Flutter app (mobile/README.md); the tabs follow the backend's role checks. */
const ROLES: [string, string, string][] = [
  ["Farmer", "Ask, Scan, Market, Me", "Ask in Bangla by voice or typing; decision cards; the answer read aloud; photo grading with a signed certificate; list a lot, accept a bid into escrow, report a problem"],
  ["Buyer", "Market, Purchases, Verify, Me", "Open lots by crop, bid with quick raises, lead and outbid status, won lots with payment and delivery, certificate check"],
  ["Driver", "Jobs, On the road, Me", "Take a job, pick up, log the load temperature (shelf-life check), deliver to release the farmer's payment"],
  ["Bank", "Disputes, Ledger, Me", "Resolve disputes (release, refund, keep holding) and see every escrow"],
  ["Co-op, cold storage", "Ask, Scan, Desk, Me", "Voice and camera, truck pools or alerts, and a link to the full web desk"],
  ["Judge, admin", "Ask, Scan, Market, Deliveries, Me", "Everything read-only, plus voice and camera"],
];

const FEATURES = [
  { icon: Mic, title: "Voice", text: "The phone's own recogniser listens in Bangla (bn-BD) and shows the words live; POST /edge/voice-interact answers, read aloud by the phone's Bangla voice or the node's online voice (POST /edge/tts), never in Offline edge mode. If a crop, quantity or place is missing, it asks back by voice." },
  { icon: Camera, title: "Camera", text: "A full-screen viewfinder with a framing guide, tap to focus, torch and gallery import. The 1080p JPEG goes to POST /edge/grade-crop; each piece is outlined, the grade is stamped, and the HMAC-signed certificate can be checked on the spot (POST /edge/verify-certificate)." },
  { icon: ShieldCheck, title: "Consent and data", text: "Consent is asked once, in the website's words, before the farmer's own voice, words or photo are used. The app keeps the session token on the phone; identity numbers come back masked, as on the web." },
];

export function MobileAppSection() {
  return (
    <div className="space-y-5">
      <div className="surface p-4 sm:p-5">
        <div className="min-w-0">
          <p className="m-0 text-[15px] leading-relaxed text-slate-700">
            The KrishiNexus Android app (Flutter, Material 3) is the phone companion for farmers, buyers and drivers. It calls the same
            API as this website ({site.origin.replace("https://", "")} by default), so accounts, lots, bids, escrows and deliveries are
            shared with the web seats. It follows the same design system: daylight canvas, emerald, Anek Bangla for the interface and
            Tiro Bangla for words a farmer says or hears.
          </p>
          <AppDownload className="mt-4" />
          <Link to="/guide#app" className="inline-flex min-h-11 items-center gap-1.5 text-[14px] font-semibold text-emerald-700 no-underline hover:text-emerald-800">
            Install steps in the user guide <ArrowRight className="size-4" aria-hidden />
          </Link>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {FEATURES.map((f) => (
          <div key={f.title} className="surface p-4">
            <h3 className="m-0 flex items-center gap-2 text-[15px] font-semibold text-slate-900"><f.icon className="size-4 text-emerald-700" aria-hidden /> {f.title}</h3>
            <p className="m-0 mt-2 text-[13.5px] leading-relaxed text-slate-700">{f.text}</p>
          </div>
        ))}
      </div>

      <div className="surface min-w-0 p-4 sm:p-5">
        <h3 className="m-0 text-[15px] font-semibold text-slate-900">Tabs by role</h3>
        <div className="scroll-thin mt-3 -mx-1 overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-left text-[13px]">
            <thead>
              <tr className="border-b border-slate-200 text-[12px] text-slate-500">
                {["Role", "Tabs", "What works in the app"].map((h) => <th key={h} scope="col" className="px-2 py-2 font-medium">{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {ROLES.map(([role, tabs, what]) => (
                <tr key={role} className="border-b border-slate-100 align-top">
                  <th scope="row" className="px-2 py-2 font-semibold text-slate-900">{role}</th>
                  <td className="px-2 py-2 text-slate-700">{tabs}</td>
                  <td className="px-2 py-2 text-slate-700">{what}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <ul className="m-0 grid list-disc gap-1.5 pl-5 text-[13.5px] leading-relaxed text-slate-700 marker:text-emerald-700">
        <li>Android 7.0 or newer (minSdk 24), about {site.apk_size_mb} MB. The release APK is signed with the debug key, so it installs by sideloading; a Play Store upload needs a real signing key.</li>
        <li>KrishiNexus-armv7.apk is the build for older 32-bit phones.</li>
        <li>The team screen reads <code className="font-mono text-[12.5px]">/team/team.json</code>, the same file as the website's team section, with a copy bundled in the app.</li>
        <li>Me → Server (or <code className="font-mono text-[12.5px]">--dart-define=API_BASE=…</code>) points the app at another node, such as a village kiosk on the LAN; cleartext is allowed for that case.</li>
        <li>Source and build steps: <code className="font-mono text-[12.5px]">mobile/README.md</code> in the repository.</li>
      </ul>
    </div>
  );
}
