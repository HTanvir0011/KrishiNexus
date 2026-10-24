import { ArrowRight, CloudRain, Landmark, Play, ShieldAlert, Snowflake, Truck, Volume2, Ban } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import { api, ApiError } from "../api/client";
import { Badge, Button, Segmented, SourceChip, Spinner } from "../components/ui";
import { cn, pct, tk } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { Link } from "../lib/router";
import { hasBanglaVoice, speak } from "../lib/speech";
import { getState, pushAlert, setState, useAppState } from "../state/store";
import { ABDUL_SNAPSHOT, abdulFrom, RAHIM_SNAPSHOT, rahimFrom, SNAPSHOT_DATE, type AbdulFacts, type RahimFacts } from "./data";
import { nodeOf, PIPELINE } from "./pipeline";
import { ABDUL, RAHIM } from "./presets";

type PersonaId = "rahim" | "abdul";

interface Run {
  sessionId: string;
  status: "running" | "live" | "cached";
  ms: number | null;
  rahim?: RahimFacts;
  abdul?: AbdulFacts;
}

const COPY = {
  en: {
    title: "Try a live farmer decision in one click",
    persona: { rahim: "Rahim Mia · potato", abdul: "Abdul · haor rice" },
    rahimLine: "400 kg Cardinal potato · Mithapukur, Rangpur",
    abdulLine: "4 acres of Boro rice · Tahirpur, Sunamganj haor",
    run: "Run live multi-agent orchestration",
    again: "Run it again",
    running: "Four agents are working",
    idle: "Press run to send this question to the four agents on the live backend.",
    blocked: "Financial circuit breaker: Faria sale blocked",
    blockedWhy: (offer: string, floor: string) => `The Faria offers ${offer}/kg, below the ${floor}/kg it costs to grow a kilo.`,
    worth: (kg: number) => `What each choice is worth for his ${kg.toLocaleString("en-IN")} kg`,
    faria: "Faria distress sale",
    store: (days: number) => `Cold storage, ${days} days`,
    pool: "5-ton pooled B2B truck",
    recommended: "Recommended",
    trace: "View full trace in OS",
    listen: "Listen in Bangla",
    noVoice: "This device has no Bangla voice installed, so the answer is shown but not spoken.",
    breach: "chance the haor embankment breaks in the next 72 hours",
    sar: "SAR backscatter",
    sarNote: "simulated pass",
    rain: "Upstream rain, 72 h",
    credit: "Agri-credit score",
  },
  bn: {
    title: "এক ক্লিকে কৃষকের সিদ্ধান্ত দেখুন",
    persona: { rahim: "রহিম মিয়া · আলু", abdul: "আব্দুল · হাওরের ধান" },
    rahimLine: "৪০০ কেজি কার্ডিনাল আলু · মিঠাপুকুর, রংপুর",
    abdulLine: "৪ একর বোরো ধান · তাহিরপুর, সুনামগঞ্জ হাওর",
    run: "চার এজেন্টকে লাইভ চালান",
    again: "আবার চালান",
    running: "চার এজেন্ট কাজ করছে",
    idle: "প্রশ্নটি লাইভ ব্যাকএন্ডের চার এজেন্টের কাছে পাঠাতে চালান চাপুন।",
    blocked: "আর্থিক সার্কিট ব্রেকার: ফড়িয়ার বিক্রি আটকানো হয়েছে",
    blockedWhy: (offer: string, floor: string) => `ফড়িয়ার দাম ${offer}/কেজি, যা উৎপাদন খরচ ${floor}/কেজির নিচে।`,
    worth: (kg: number) => `${kg.toLocaleString("en-IN")} কেজির জন্য কোন পথে কত টাকা`,
    faria: "ফড়িয়ার কাছে বিক্রি",
    store: (days: number) => `হিমাগার, ${days} দিন`,
    pool: "৫ টনের যৌথ ট্রাক",
    recommended: "সুপারিশ",
    trace: "ওএস-এ পুরো ট্রেস দেখুন",
    listen: "বাংলায় শুনুন",
    noVoice: "এই ডিভাইসে বাংলা কণ্ঠ নেই, তাই উত্তরটি লেখা আকারে দেখানো হলো।",
    breach: "আগামী ৭২ ঘণ্টায় হাওরের বাঁধ ভাঙার সম্ভাবনা",
    sar: "রাডার ব্যাকস্ক্যাটার",
    sarNote: "সিমুলেটেড পাস",
    rain: "উজানে বৃষ্টি, ৭২ ঘণ্টা",
    credit: "কৃষি-ঋণ স্কোর",
  },
};

const ALERT_TONE: Record<string, "emerald" | "amber" | "red"> = { GREEN: "emerald", YELLOW: "amber", ORANGE: "amber", RED: "red" };

export function LiveDecisionCard() {
  const c = useCopy(COPY);
  const [persona, setPersona] = useState<PersonaId>("rahim");
  const [runs, setRuns] = useState<Partial<Record<PersonaId, Run>>>({});
  const [notice, setNotice] = useState<string | null>(null);
  const traces = useAppState((s) => s.traces);
  const run = runs[persona];
  const preset = persona === "rahim" ? RAHIM : ABDUL;

  const seen = useMemo(() => {
    if (!run) return new Set<string>();
    return new Set(traces.filter((e) => e.session_id === run.sessionId).map(nodeOf));
  }, [traces, run]);

  const start = async () => {
    const who = persona;
    const sessionId = `KNX-WEB-${Math.random().toString(36).slice(2, 10).toUpperCase()}`;
    setNotice(null);
    setRuns((r) => ({ ...r, [who]: { sessionId, status: "running", ms: null } }));
    setState({ activeSessionId: sessionId });
    const started = performance.now();
    try {
      const response = await api.voiceInteract({ preset_id: (who === "rahim" ? RAHIM : ABDUL).id, session_id: sessionId, offline_mode: getState().offlineMode });
      const live = response.live;
      const facts = who === "rahim"
        ? { rahim: (live && rahimFrom(response.data)) || RAHIM_SNAPSHOT }
        : { abdul: (live && abdulFrom(response.data)) || ABDUL_SNAPSHOT };
      if (live) setState({ lastVoice: response.data });
      setRuns((r) => ({ ...r, [who]: { sessionId, status: live ? "live" : "cached", ms: live ? performance.now() - started : null, ...facts } }));
    } catch (error) {
      pushAlert("danger", "The agents rejected the request", error instanceof ApiError ? error.message : String(error));
      setRuns((r) => ({ ...r, [who]: undefined }));
    }
  };

  const listen = (text: string) => {
    if (!hasBanglaVoice()) {
      setNotice(c.noVoice);
      return;
    }
    setNotice(speak(text, "bn-BD") ? null : c.noVoice);
  };

  const running = run?.status === "running";
  return (
    <section className="surface overflow-hidden shadow-lift" aria-label={c.title}>
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
        <h2 className="m-0 text-[15px] font-semibold text-slate-900">{c.title}</h2>
        <Segmented label="Persona" value={persona} onChange={setPersona}
          options={[{ value: "rahim", label: c.persona.rahim }, { value: "abdul", label: c.persona.abdul }]} />
      </header>

      <div className="space-y-4 px-5 py-5">
        <div className="flex items-start gap-3">
          <span className={cn("grid size-10 shrink-0 place-items-center rounded-full text-[14px] font-semibold",
            persona === "rahim" ? "bg-emerald-50 text-emerald-800" : "bg-sky-50 text-sky-800")} aria-hidden>
            {persona === "rahim" ? "RM" : "AB"}
          </span>
          <div className="min-w-0">
            <div className="text-[15px] font-semibold text-slate-900">{preset.farmer}</div>
            <div className="text-[13px] text-slate-600">{persona === "rahim" ? c.rahimLine : c.abdulLine}</div>
          </div>
          <Badge tone="violet" className="ml-auto">{preset.dialect}</Badge>
        </div>

        <blockquote className="m-0 rounded-xl bg-slate-50 px-4 py-3 ring-1 ring-inset ring-slate-200">
          <p lang="bn" className="voice m-0 text-[26px] leading-snug text-slate-900">{preset.question}</p>
          <p className="m-0 mt-1 text-[14px] text-slate-600">“{preset.english}”</p>
        </blockquote>

        <Button variant="primary" className="w-full min-h-11 text-[15px]" onClick={() => void start()} disabled={running}>
          {running ? <Spinner /> : <Play className="size-4" aria-hidden />}
          {running ? c.running : run ? c.again : c.run}
        </Button>

        {running && (
          <ol className="m-0 grid list-none grid-cols-9 gap-1 p-0" aria-label="Pipeline progress">
            {PIPELINE.map((node) => (
              <li key={node.id} title={node.title} className={cn("h-1.5 rounded-full transition-colors", seen.has(node.id) ? "bg-emerald-600" : "bg-slate-200")} />
            ))}
          </ol>
        )}

        {!run && <p className="m-0 text-[13px] text-slate-500">{c.idle}</p>}

        {run?.rahim && !running && (
          <div className="animate-rise space-y-4">
            {run.rahim.blocked && (
              <div className="flex gap-3 rounded-xl bg-rose-100/70 p-3 ring-1 ring-inset ring-rose-600/15">
                <ShieldAlert className="mt-0.5 size-5 shrink-0 text-rose-600" aria-hidden />
                <div>
                  <div className="text-[14px] font-semibold text-rose-700">{c.blocked}</div>
                  <div className="text-[13px] text-rose-700/90">{c.blockedWhy(tk(run.rahim.offer), tk(run.rahim.floor, 0))}</div>
                </div>
              </div>
            )}
            <Payouts facts={run.rahim} copy={c} />
            {run.rahim.credit?.eligible && (
              <p className="m-0 flex items-center gap-2 text-[13px] text-slate-600">
                <Landmark className="size-4 text-violet-600" aria-hidden />
                {c.credit} <span className="num text-slate-900">{run.rahim.credit.score}</span> · {tk(run.rahim.credit.amount, 0)} at {run.rahim.credit.rate}% pre-approved
              </p>
            )}
            <Answer text={run.rahim.spokenBn} listen={listen} label={c.listen} />
          </div>
        )}

        {run?.abdul && !running && (
          <div className="animate-rise space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <Badge tone={ALERT_TONE[run.abdul.alertLevel ?? "GREEN"] ?? "emerald"} className="text-[13px]">Alert {(run.abdul.alertLevel ?? "GREEN").toLowerCase()}</Badge>
              <span className="num text-[34px] leading-none text-slate-900">{pct(run.abdul.breachPct)}</span>
              <span className="text-[13px] text-slate-600">{c.breach}</span>
            </div>
            <dl className="m-0 grid grid-cols-3 gap-3">
              <Fact label={c.sar} value={run.abdul.sarDb !== null ? `${run.abdul.sarDb.toFixed(1)} dB` : "-"} hint={c.sarNote} icon={<CloudRain className="size-3.5" aria-hidden />} />
              <Fact label={c.rain} value={`${run.abdul.rain72h.toFixed(0)} mm`} />
              <Fact label={c.credit} value={run.abdul.creditScore ?? "-"} hint={run.abdul.loan ? tk(run.abdul.loan, 0) : undefined} />
            </dl>
            <Answer text={run.abdul.advice} listen={listen} label={c.listen} />
          </div>
        )}
        {notice && <p className="m-0 text-[13px] text-slate-500" role="status">{notice}</p>}
      </div>

      {run && !running && (
        <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 bg-slate-50/70 px-5 py-3">
          <SourceChip status={run.status === "live" ? "live" : "cached"} tool={run.status === "live" ? "POST /edge/voice-interact" : `run of ${SNAPSHOT_DATE}`} ms={run.ms} />
          <Link to="/os" className="inline-flex items-center gap-1 text-[13px] font-semibold text-emerald-700 no-underline hover:text-emerald-800">
            {c.trace} <ArrowRight className="size-3.5" aria-hidden />
          </Link>
        </footer>
      )}
    </section>
  );
}

function Payouts({ facts: r, copy: c }: { facts: RahimFacts; copy: (typeof COPY)["en"] }) {
  const best = r.decision === "SELL_POOLED_B2B" ? "pool" : r.decision.startsWith("STORE") ? "store" : "faria";
  const rows = [
    { key: "faria", icon: <Ban className="size-4" aria-hidden />, label: c.faria, value: r.spotValue, note: `${tk(r.offer)}/kg`, bar: "bg-rose-500", struck: r.blocked },
    { key: "store", icon: <Snowflake className="size-4" aria-hidden />, label: c.store(r.horizonDays), value: r.storageValue,
      note: r.futurePrice !== null ? `farm-gate ${tk(r.futurePrice)}/kg by then` : "", bar: "bg-sky-600", struck: false },
    { key: "pool", icon: <Truck className="size-4" aria-hidden />, label: c.pool, value: r.lotValueB2b, note: `${tk(r.b2bNet)}/kg after ${tk(r.freight)}/kg freight`, bar: "bg-emerald-600", struck: false },
  ];
  const max = Math.max(...rows.map((row) => row.value), 1);
  return (
    <div>
      <div className="mb-2 text-[13px] font-medium text-slate-600">{c.worth(r.quantityKg)}</div>
      <ul className="m-0 list-none space-y-3 p-0">
        {rows.map((row) => (
          <li key={row.key}>
            <div className="flex items-baseline justify-between gap-3">
              <span className={cn("flex min-w-0 items-center gap-1.5 text-[14px]", row.key === best ? "font-semibold text-slate-900" : "text-slate-700")}>
                <span className={row.key === "faria" ? "text-rose-600" : row.key === "store" ? "text-sky-600" : "text-emerald-700"}>{row.icon}</span>
                <span className="truncate">{row.label}</span>
                {row.key === best && <Badge tone="emerald">{c.recommended}</Badge>}
              </span>
              <span className={cn("num text-[18px]", row.struck ? "text-rose-600 line-through decoration-2" : row.key === best ? "text-emerald-700" : "text-slate-900")}>
                {tk(row.value, 0)}
              </span>
            </div>
            <div className="mt-1.5 h-2 rounded-full bg-slate-100">
              <div className={cn("h-full rounded-full transition-[width] duration-700", row.bar)} style={{ width: `${Math.max(2, (row.value / max) * 100)}%` }} />
            </div>
            {row.note && <div className="mt-1 text-[12px] text-slate-500">{row.note}</div>}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Answer({ text, listen, label }: { text: string; listen: (text: string) => void; label: string }) {
  return (
    <div className="rounded-xl bg-emerald-50/70 p-3 ring-1 ring-inset ring-emerald-700/10">
      <p lang="bn" className="voice m-0 line-clamp-3 text-[16px] leading-relaxed text-slate-900">{text}</p>
      <button type="button" onClick={() => listen(text)} className="mt-2 inline-flex items-center gap-1.5 text-[13px] font-semibold text-emerald-800 hover:text-emerald-900">
        <Volume2 className="size-4" aria-hidden /> {label}
      </button>
    </div>
  );
}

function Fact({ label, value, hint, icon }: { label: string; value: ReactNode; hint?: string; icon?: ReactNode }) {
  return (
    <div className="min-w-0 rounded-lg bg-slate-50 px-3 py-2 ring-1 ring-inset ring-slate-200">
      <dt className="flex items-center gap-1 truncate text-[12px] text-slate-500">{icon}{label}</dt>
      <dd className="num m-0 text-[18px] text-slate-900">{value}</dd>
      {hint && <div className="truncate text-[11.5px] text-slate-500">{hint}</div>}
    </div>
  );
}
