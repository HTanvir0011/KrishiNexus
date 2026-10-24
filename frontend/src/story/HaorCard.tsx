import { useEffect, useState } from "react";

import { api, ApiError, mcpCall } from "../api/client";
import { Badge, Segmented, SourceChip, Spinner } from "../components/ui";
import { cn } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { pushAlert } from "../state/store";
import { abdulFrom, ABDUL_SNAPSHOT, SNAPSHOT_DATE } from "./data";

/** The parts of `calculate_haor_flash_flood_risk` output this card renders. */
interface HaorRisk {
  upazila: string;
  sar_water_backscatter_db: number;
  sar_water_fraction: number;
  upstream_rainfall_72h_mm: number;
  embankment_breach_probability_pct: number;
  alert_level: string;
  boro_at_risk_tons: number;
  flood_wave_lead_time_hours: number;
  recommended_harvest_within_hours: number;
  voice_alert_bn: string;
}

type Mode = "today" | "surge";

const SURGE_DB = -19.5;
const HISTORY = [
  { district: "Sunamganj", loss: 65 },
  { district: "Kishoreganj", loss: 44 },
  { district: "Netrokona", loss: 21 },
];
const ALERT_TONE: Record<string, "emerald" | "amber" | "red"> = { GREEN: "emerald", YELLOW: "amber", ORANGE: "amber", RED: "red" };

const COPY = {
  en: {
    title: "Sentinel-1 haor flood shield",
    sub: "Abdul's Boro rice in Tahirpur, Sunamganj, seen through monsoon cloud",
    today: "Today", surge: "April 2017 surge",
    breach: "chance the embankment breaks in 72 hours",
    harvest: "Harvest within", atRisk: "Boro at risk", rain: "Upstream rain, 72 h", backscatter: "Backscatter",
    history: "Boro lost in the 2017 flash flood (cited in brief)",
    note: "The radar is a simulated Sentinel-1 pass; this build has no live Copernicus feed. The surge adds 320 mm of upstream rain and a -19.5 dB scene on the backend; going back to today clears every simulation.",
    water: "Black is open water",
    hills: "Meghalaya hills",
  },
  bn: {
    title: "সেন্টিনেল-১ হাওর বন্যা সুরক্ষা",
    sub: "মেঘের ভেতর দিয়ে তাহিরপুর, সুনামগঞ্জে আব্দুলের বোরো ধান",
    today: "আজ", surge: "২০১৭ সালের ঢল",
    breach: "আগামী ৭২ ঘণ্টায় বাঁধ ভাঙার সম্ভাবনা",
    harvest: "ধান কাটুন", atRisk: "ঝুঁকিতে বোরো", rain: "উজানে বৃষ্টি, ৭২ ঘণ্টা", backscatter: "ব্যাকস্ক্যাটার",
    history: "২০১৭ সালের আকস্মিক বন্যায় বোরো ক্ষতি (ব্রিফ থেকে উদ্ধৃত)",
    note: "রাডারটি সিমুলেটেড সেন্টিনেল-১ পাস; এই বিল্ডে লাইভ কোপার্নিকাস ফিড নেই। ঢল সিমুলেশন ব্যাকএন্ডে ৩২০ মিমি বৃষ্টি যোগ করে; আজকের অবস্থায় ফিরলে সব সিমুলেশন মুছে যায়।",
    water: "কালো অংশ খোলা পানি",
    hills: "মেঘালয় পাহাড়",
  },
};

const tool = (sar: number) => mcpCall<HaorRisk>("calculate_haor_flash_flood_risk", { upazila: "Tahirpur", sar_water_backscatter_db: sar });

export function HaorCard({ className }: { className?: string }) {
  const c = useCopy(COPY);
  const [mode, setMode] = useState<Mode>("today");
  const [today, setToday] = useState<HaorRisk | null>(null);
  const [surge, setSurge] = useState<HaorRisk | null>(null);
  const [status, setStatus] = useState<"loading" | "live" | "cached">("loading");
  const [ms, setMs] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  // Today's scene is the one Abdul's own agents used: the climate agent's simulated pass for this hour.
  useEffect(() => {
    let active = true;
    api.voiceInteract({ preset_id: "sunamganj_haor_flood" })
      .then(async (r) => {
        const facts = r.live ? abdulFrom(r.data) : null;
        if (!facts || facts.sarDb === null) throw new Error("offline");
        const started = performance.now();
        const risk = await tool(facts.sarDb);
        if (!active) return;
        setToday(risk);
        setStatus("live");
        setMs(performance.now() - started);
      })
      .catch(() => active && setStatus("cached"));
    return () => {
      active = false;
    };
  }, []);

  const choose = async (next: Mode) => {
    if (next === mode || busy) return;
    setBusy(true);
    try {
      let started = performance.now();
      if (next === "surge") {
        await api.simulateFlashFlood("Tahirpur");
        started = performance.now();
        setSurge(await tool(SURGE_DB));
      } else {
        await api.clearAnomalies();
        started = performance.now();
        if (today) setToday(await tool(today.sar_water_backscatter_db));
      }
      setMs(performance.now() - started);
      setMode(next);
    } catch (error) {
      pushAlert("danger", "The flood simulation needs the live backend", error instanceof ApiError ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const shown = mode === "surge" ? surge : today;
  const cached = status === "cached";
  const breach = shown?.embankment_breach_probability_pct ?? (cached ? ABDUL_SNAPSHOT.breachPct : null);
  const level = shown?.alert_level ?? (cached ? ABDUL_SNAPSHOT.alertLevel : null) ?? "GREEN";
  const flood = mode === "surge" ? 1 : 0;

  return (
    <article className={cn("surface grid min-w-0 gap-5 p-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]", className)}>
      <SarMap flood={flood} water={c.water} hills={c.hills} sar={shown?.sar_water_backscatter_db ?? (cached ? ABDUL_SNAPSHOT.sarDb : null)} />

      <div className="flex min-w-0 flex-col">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="m-0 text-[17px] font-semibold tracking-[-0.01em] text-slate-900">{c.title}</h3>
            <p className="m-0 text-[13px] text-slate-500">{c.sub}</p>
          </div>
          <Segmented label="Scenario" value={mode} onChange={(v) => void choose(v)}
            options={[{ value: "today", label: c.today }, { value: "surge", label: <>{busy && mode === "today" ? <Spinner /> : null}{c.surge}</> }]} />
        </header>

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <Badge tone={ALERT_TONE[level] ?? "amber"} className="text-[13px]">Alert {level.toLowerCase()}</Badge>
          <span className={cn("num text-[44px] leading-none", level === "RED" ? "text-rose-600" : "text-slate-900")}>
            {breach !== null && breach !== undefined ? `${breach.toFixed(1)}%` : "…"}
          </span>
          <span className="text-[13px] text-slate-600">{c.breach}</span>
        </div>

        {shown && (
          <dl className="m-0 mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Fact label={c.harvest} value={`${Math.round(shown.recommended_harvest_within_hours)} h`} alert={shown.recommended_harvest_within_hours <= 24} />
            <Fact label={c.atRisk} value={`${Math.round(shown.boro_at_risk_tons).toLocaleString("en-IN")} t`} alert={level === "RED"} />
            <Fact label={c.rain} value={`${Math.round(shown.upstream_rainfall_72h_mm)} mm`} />
            <Fact label={c.backscatter} value={`${shown.sar_water_backscatter_db.toFixed(1)} dB`} />
          </dl>
        )}
        {shown && <p lang="bn" className="voice m-0 mt-4 text-[16px] leading-relaxed text-slate-900">{shown.voice_alert_bn}</p>}
        {!shown && cached && <p lang="bn" className="voice m-0 mt-4 text-[16px] leading-relaxed text-slate-900">{ABDUL_SNAPSHOT.advice}</p>}

        <div className="mt-5">
          <div className="mb-2 text-[12.5px] font-medium text-slate-600">{c.history}</div>
          <ul className="m-0 list-none space-y-1.5 p-0">
            {HISTORY.map((h) => (
              <li key={h.district} className="grid grid-cols-[6.5rem_1fr_2.5rem] items-center gap-2 text-[12.5px]">
                <span className="text-slate-700">{h.district}</span>
                <span className="h-2 rounded-full bg-slate-100"><span className="block h-full rounded-full bg-rose-500" style={{ width: `${h.loss}%` }} /></span>
                <span className="num text-right text-slate-900">{h.loss}%</span>
              </li>
            ))}
          </ul>
        </div>

        <p className="m-0 mt-4 text-[12px] leading-relaxed text-slate-500">{c.note}</p>
        <footer className="mt-auto pt-3">
          <SourceChip status={status} tool={cached ? `voice preset · run of ${SNAPSHOT_DATE}` : "calculate_haor_flash_flood_risk"} ms={ms} />
        </footer>
      </div>
    </article>
  );
}

function Fact({ label, value, alert = false }: { label: string; value: string; alert?: boolean }) {
  return (
    <div className="min-w-0 rounded-lg bg-slate-50 px-3 py-2 ring-1 ring-inset ring-slate-200">
      <dt className="truncate text-[12px] text-slate-500">{label}</dt>
      <dd className={cn("num m-0 text-[18px]", alert ? "text-rose-600" : "text-slate-900")}>{value}</dd>
    </div>
  );
}

/** Stylised Sentinel-1 scene of the Tanguar haor basin: speckled land, black open water that spreads in the surge. */
function SarMap({ flood, water, hills, sar }: { flood: number; water: string; hills: string; sar: number | null }) {
  const grow = 0.72 + flood * 0.5;
  const basins = [
    { cx: 150, cy: 132, d: "M100 118c18-30 70-34 96-12s20 58-8 70-74 10-90-14-16-28 2-44z" },
    { cx: 268, cy: 150, d: "M236 136c12-18 46-20 62-4s10 40-12 46-48 2-54-14 0-16 4-28z" },
    { cx: 214, cy: 226, d: "M184 214c14-14 44-14 58 0s8 30-12 34-42 0-48-12 0-14 2-22z" },
  ];
  return (
    <figure className="well relative m-0 min-h-[300px] overflow-hidden">
      <svg viewBox="0 0 420 320" className="absolute inset-0 h-full w-full" preserveAspectRatio="xMidYMid slice" role="img"
        aria-label={`Simulated Sentinel-1 radar scene of Tahirpur; open water ${flood ? "spreading across the haor" : "inside the haor basins"}`}>
        <defs>
          <filter id="speckle" x="0" y="0" width="100%" height="100%">
            <feTurbulence type="fractalNoise" baseFrequency="1.4" numOctaves="2" seed="11" />
            <feColorMatrix type="saturate" values="0" />
            <feComponentTransfer>
              <feFuncR type="linear" slope="0.32" intercept="0.13" />
              <feFuncG type="linear" slope="0.32" intercept="0.14" />
              <feFuncB type="linear" slope="0.32" intercept="0.16" />
            </feComponentTransfer>
          </filter>
          <filter id="shore"><feGaussianBlur stdDeviation="1.4" /></filter>
          <pattern id="hills" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(35)">
            <line x1="0" y1="0" x2="0" y2="10" stroke="#475569" strokeWidth="2" />
          </pattern>
        </defs>
        <rect width="420" height="320" filter="url(#speckle)" />
        <rect width="420" height="46" fill="url(#hills)" opacity="0.55" />
        <path d="M0 46 Q 110 58 210 44 T 420 50" fill="none" stroke="#64748b" strokeWidth="1" strokeDasharray="3 4" />
        <path d="M70 46 C 90 90 120 100 140 118" fill="none" stroke="#05070c" strokeWidth={3 + flood * 4} style={{ transition: "stroke-width 0.8s ease" }} />
        <path d="M300 46 C 290 90 280 110 268 130" fill="none" stroke="#05070c" strokeWidth={3 + flood * 4} style={{ transition: "stroke-width 0.8s ease" }} />
        {basins.map((b) => (
          <path key={b.d} d={b.d} fill="#03050a" filter="url(#shore)" style={{ transform: `scale(${grow})`, transformOrigin: `${b.cx}px ${b.cy}px`, transition: "transform 0.9s cubic-bezier(0.2,0.8,0.2,1)" }} />
        ))}
        {flood > 0 && (
          <g stroke="#f43f5e" strokeWidth="2" fill="none" className="animate-pulse-soft">
            <path d="M120 30 L 132 70" /><path d="M126 62 L 132 70 L 136 61" />
            <path d="M300 30 L 292 70" /><path d="M287 62 L 292 70 L 297 62" />
          </g>
        )}
        <circle cx="176" cy="156" r="5" fill="#f59e0b" stroke="#090d16" strokeWidth="2" />
      </svg>
      <figcaption className="pointer-events-none absolute inset-0 p-3 font-mono text-[11px] text-slate-300">
        <div className="flex items-start justify-between gap-2">
          <span>S1 IW · VV · {sar !== null ? `${sar.toFixed(1)} dB` : "…"}</span>
          <span className="text-slate-400">{hills}</span>
        </div>
        <span className="absolute top-[45%] left-[44%] rounded bg-black/70 px-1.5 py-0.5 font-sans text-[11.5px] text-amber-300">Abdul's fields</span>
        <span className="absolute top-[58%] left-[9%] rounded bg-black/70 px-1.5 py-0.5 font-sans text-[11.5px] text-slate-200">Tanguar haor</span>
        <span className="absolute bottom-3 left-3 flex items-center gap-1.5 font-sans text-[11.5px] text-slate-300">
          <span className="size-2.5 rounded-sm bg-[#03050a] ring-1 ring-slate-500" /> {water}
        </span>
      </figcaption>
    </figure>
  );
}
