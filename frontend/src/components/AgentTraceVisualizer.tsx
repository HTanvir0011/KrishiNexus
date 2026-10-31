import { Activity, CheckCircle2, CircleDashed, Cpu, Database, EyeOff, Gauge, Layers, Loader2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import type { AgentState, StepType, TraceEvent } from "../api/client";
import { cn, timeOf, tk } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { useAppState, type Lang } from "../state/store";
import { nodeOf, PIPELINE } from "../story/pipeline";
import { Badge, LiveDot, Panel, Segmented, type Tone } from "./ui";

const STEP_TONE: Record<StepType, Tone> = {
  THOUGHT: "slate",
  MCP_CALL: "sky",
  RAG_CRAG: "violet",
  GUARDRAIL: "amber",
  DECISION: "emerald",
};

const INTENT_WORDS: Record<string, string> = {
  STORAGE_CONDITIONS: "storage conditions", STORAGE_ACCESS: "cold-storage space", SELLING_CHANNEL: "where to sell", PRICE: "price",
  DISEASE: "crop disease", PESTICIDE_SAFETY: "pesticide safety", FLOOD: "flood risk", HARVEST: "harvest timing", CREDIT: "credit",
  TRANSPORT: "transport", GENERAL: "general advice",
};

const INTENT_WORDS_BN: Record<string, string> = {
  STORAGE_CONDITIONS: "সংরক্ষণের শর্ত", STORAGE_ACCESS: "কোল্ড স্টোরেজের জায়গা", SELLING_CHANNEL: "কোথায় বিক্রি", PRICE: "দাম",
  DISEASE: "ফসলের রোগ", PESTICIDE_SAFETY: "কীটনাশকের নিরাপত্তা", FLOOD: "বন্যার ঝুঁকি", HARVEST: "ফসল তোলার সময়", CREDIT: "ঋণ",
  TRANSPORT: "পরিবহন", GENERAL: "সাধারণ পরামর্শ",
};

const COPY = {
  en: {
    title: "Live agent and MCP trace",
    traceView: "Trace view",
    plainShort: "Plain language", plainLong: "Plain-language judge view",
    rawShort: "Raw JSON-RPC", rawLong: "Raw JSON-RPC and telemetry",
    piiHidden: (n: number) => `${n} personal detail${n === 1 ? "" : "s"} hidden`,
    mcpBadge: (calls: number, tools: number, ms: string) => `${calls} MCP calls · ${tools}/13 tools · ${ms} ms`,
    tokensSaved: (n: string) => `${n} tokens saved`,
    empty: "Waiting for a farmer request. Tap a voice preset on the farmer's phone, or run a simulation, and every agent step streams here.",
  },
  bn: {
    title: "লাইভ এজেন্ট ও এমসিপি ট্রেস",
    traceView: "ট্রেস ভিউ",
    plainShort: "সহজ ভাষায়", plainLong: "বিচারকের জন্য সহজ ভাষায়",
    rawShort: "Raw JSON-RPC", rawLong: "Raw JSON-RPC ও টেলিমেট্রি",
    piiHidden: (n: number) => `${n}টি ব্যক্তিগত তথ্য লুকানো`,
    mcpBadge: (calls: number, tools: number, ms: string) => `${calls}টি এমসিপি কল · ${tools}/13 টুল · ${ms} ms`,
    tokensSaved: (n: string) => `${n} টোকেন সাশ্রয়`,
    empty: "কৃষকের প্রশ্নের অপেক্ষায়। কৃষকের ফোনে একটি ভয়েস প্রিসেট চাপুন বা একটি সিমুলেশন চালান — প্রতিটি এজেন্ট ধাপ এখানে লাইভ দেখা যাবে।",
  },
};

/** One plain sentence per node, in the toggle's language, written from the run's final state; falls back to the node's own trace text. */
function plainSentence(node: string, s: AgentState | null, events: TraceEvent[], lang: Lang): string | null {
  const bn = lang === "bn";
  const own = events.filter((e) => nodeOf(e) === node);
  if (!s) return own.at(-1)?.payload_summary ?? null;
  const syn = s.syndicate_bypass_plan;
  const cold = s.cold_storage_arbitrage_plan;
  const credit = s.climate_credit_report;
  switch (node) {
    case "pii_guardrail": {
      const hidden = own.filter((e) => e.step_type === "GUARDRAIL").length;
      const offer = s.farmer_offer_tk_per_kg;
      return bn
        ? `কোনো এজেন্ট প্রশ্ন পড়ার আগেই ${hidden}টি ব্যক্তিগত তথ্য লুকানো হয়েছে${offer !== null ? `; ফড়িয়ার অফার ${tk(offer)}/kg` : ""}।`
        : `Hid ${hidden} personal detail${hidden === 1 ? "" : "s"} before any agent read the question${offer !== null ? `; the middleman offers ${tk(offer)}/kg` : ""}.`;
    }
    case "token_compression": {
      const c = s.compression_report;
      if (!c.reduction_factor) return null;
      return bn
        ? `7 দিনের ডিএএম দামের ডেটা ${c.reduction_factor}x ছোট করা হয়েছে (${c.original_tokens} থেকে ${c.compressed_tokens} টোকেন), একটি সংখ্যাও বাদ পড়েনি।`
        : `Shrank the 7-day DAM price data ${c.reduction_factor}x (${c.original_tokens} to ${c.compressed_tokens} tokens) without dropping a number.`;
    }
    case "crag_retrieval": {
      const r = s.rag_crag_result;
      if (!r) return null;
      const words = bn ? INTENT_WORDS_BN : INTENT_WORDS;
      const intents = r.intents.map((i) => words[i] ?? i).join(bn ? " ও " : " and ");
      return bn
        ? `প্রশ্নটি ${r.dialect} হিসেবে পড়া হয়েছে, বিষয় ${intents}; পাওয়া নির্দেশনা CRAG যাচাইয়ে পাস করেছে (${r.verdict.toLowerCase()}, ${r.confidence.toFixed(2)})।`
        : `Read the question as ${r.dialect}, about ${intents}; the retrieved guidance passed the CRAG check (${r.verdict.toLowerCase()}, ${r.confidence.toFixed(2)}).`;
    }
    case "vision_grading":
      if (!s.optical_grade_cert) return null;
      return bn
        ? `${s.quantity_kg.toLocaleString("en-IN")} kg লটকে ${s.optical_grade_cert.grade} গ্রেড দেওয়া হয়েছে এবং সনদ ${s.optical_grade_cert.certificate_id} স্বাক্ষর করা হয়েছে।`
        : `Graded the ${s.quantity_kg.toLocaleString("en-IN")} kg lot ${s.optical_grade_cert.grade} and signed certificate ${s.optical_grade_cert.certificate_id}.`;
    case "syndicate_bypass":
      if (!syn) return null;
      return bn
        ? `খেত থেকে খুচরা পর্যন্ত ${syn.markup_pct.toFixed(0)}% মার্কআপ ধরা পড়েছে (${syn.severity.toLowerCase()}); ${syn.best_hub_name} পর্যন্ত পুল করা ট্রাকে মিলবে ${tk(syn.b2b_net_tk_per_kg)}/kg।`
        : `Found a ${syn.markup_pct.toFixed(0)}% farm-to-retail markup (${syn.severity.toLowerCase()}); a pooled truck to ${syn.best_hub_name} pays ${tk(syn.b2b_net_tk_per_kg)}/kg.`;
    case "coldchain_arbitrage": {
      if (!cold) return null;
      if (cold.distress_sale_blocked) {
        const floor = tk(cold.circuit_breaker?.production_cost_floor_bdt ?? 15, 0);
        return bn
          ? `${tk(s.farmer_offer_tk_per_kg)}-এর ফড়িয়া বিক্রি আটকানো হয়েছে, ${floor} উৎপাদন-খরচ সীমার নিচে বলে; ${cold.decision === "SELL_POOLED_B2B" ? "স্টোরেজের চেয়ে পুল করা ট্রাকই ভালো" : "এখন বিক্রির চেয়ে স্টোরেজই ভালো"}।`
          : `Blocked the ${tk(s.farmer_offer_tk_per_kg)} Faria sale, below the ${floor} cost floor; ${cold.decision === "SELL_POOLED_B2B" ? "the pooled truck beats storing" : "storing beats selling now"}.`;
      }
      return bn
        ? `স্টোরেজ আর পুল বিক্রির তুলনা করা হয়েছে: ${cold.decision.replaceAll("_", " ").toLowerCase()}।`
        : `Compared storage with the pooled sale: ${cold.decision.replaceAll("_", " ").toLowerCase()}.`;
    }
    case "climate_credit": {
      if (!credit) return null;
      const risk = credit.flood_applicable && credit.flood_breach_probability_pct !== null
        ? bn
          ? `হাওরে বাঁধ ভাঙার সম্ভাবনা ${credit.flood_breach_probability_pct.toFixed(1)}% (${credit.flood_alert_level?.toLowerCase()})`
          : `Haor breach chance ${credit.flood_breach_probability_pct.toFixed(1)}% (${credit.flood_alert_level?.toLowerCase()})`
        : bn
          ? credit.seventy_two_hour_clearance ? "আগামী 72 ঘণ্টায় ঝড় বা বন্যার ঝুঁকি নেই" : "আগামী 72 ঘণ্টায় ঝড়ের সতর্কতা আছে"
          : credit.seventy_two_hour_clearance ? "No storm or flood risk in the next 72 hours" : "Storm warning in the next 72 hours";
      const loan = credit.loan_eligible
        ? bn ? `, তাতে ${credit.annual_rate_pct}% সুদে ${tk(credit.loan_amount_tk, 0)} ঋণ মিলছে` : ` unlocks ${tk(credit.loan_amount_tk, 0)} at ${credit.annual_rate_pct}%`
        : "";
      return bn ? `${risk}; ক্রেডিট স্কোর ${credit.credit_score}${loan}।` : `${risk}; credit score ${credit.credit_score}${loan}.`;
    }
    case "supervisor_review": {
      const replanned = own.some((e) => e.payload_summary.includes("re-planning"));
      if (bn) return replanned ? "চেম্বার ঠিক তাপমাত্রায় না থাকায় কোল্ড-চেইন পরিকল্পনা ফেরত পাঠানো হয়, তারপর অনুমোদন দেওয়া হয়েছে।" : "পরিকল্পনাগুলো মিলছে কি না যাচাই হয়েছে; নতুন পরিকল্পনার দরকার পড়েনি।";
      return replanned ? "Sent the cold-chain plan back because the chamber was out of band, then approved it." : "Checked that the plans agree; no re-plan needed.";
    }
    case "voice_synthesizer":
      if (!s.final_bangla_voice_response) return null;
      return bn
        ? `${s.final_bangla_voice_response.length} অক্ষরের বাংলা উত্তর লেখা হয়েছে${s.requires_farmer_voice_approval ? " এবং কৃষকের কাছে হ্যাঁ চাওয়া হয়েছে" : ""}।`
        : `Wrote a ${s.final_bangla_voice_response.length}-character Bangla reply${s.requires_farmer_voice_approval ? " and asked the farmer for a yes" : ""}.`;
    default:
      return own.at(-1)?.payload_summary ?? null;
  }
}

function summarize(events: TraceEvent[]) {
  const pii = events.filter((e) => e.agent_name === "pii_guardrail" && e.step_type === "GUARDRAIL").length;
  const compression = events.find((e) => e.agent_name === "token_compression");
  const factor = compression?.payload_summary.match(/\(([\d.]+)x/)?.[1];
  const crag = events.find((e) => e.agent_name === "crag_retrieval");
  const cragMatch = crag?.payload_summary.match(/CRAG (\w+) \(([\d.]+)\)/);
  const mcp = events.filter((e) => e.step_type === "MCP_CALL");
  const tools = new Set(mcp.map((e) => e.tool_name).filter(Boolean));
  const tokensSaved = events.reduce((sum, e) => sum + e.token_saved, 0);
  const latency = mcp.reduce((sum, e) => sum + e.latency_ms, 0);
  return { pii, factor, cragVerdict: cragMatch?.[1], cragConfidence: cragMatch?.[2], mcpCalls: mcp.length, tools: tools.size, tokensSaved, latency };
}

export function AgentTraceVisualizer({ className, maxHeightClass = "max-h-[420px]" }: { className?: string; maxHeightClass?: string }) {
  const traces = useAppState((s) => s.traces);
  const sessionId = useAppState((s) => s.activeSessionId);
  const status = useAppState((s) => s.traceStatus);
  const voice = useAppState((s) => s.lastVoice);
  const lang = useAppState((s) => s.lang);
  const c = useCopy(COPY);
  const [view, setView] = useState<"plain" | "raw">("plain");
  const scrollRef = useRef<HTMLDivElement>(null);

  const events = useMemo(() => (sessionId ? traces.filter((e) => e.session_id === sessionId) : []), [traces, sessionId]);
  const stats = useMemo(() => summarize(events), [events]);
  const state = voice?.orchestration?.state.session_id === sessionId ? voice?.orchestration?.state ?? null : null;
  const seen = useMemo(() => new Set(events.map(nodeOf)), [events]);
  const latest = events.length ? nodeOf(events[events.length - 1]) : null;
  const finished = seen.has("voice_synthesizer");

  useEffect(() => {
    if (view === "raw") scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [events.length, view]);

  return (
    <Panel well className={className} icon={<Activity className="size-4 text-emerald-400" aria-hidden />} title={c.title}
      actions={
        <>
          <LiveDot status={status} />
          <Segmented label={c.traceView} value={view} onChange={setView} className="bg-white/5 ring-white/10 [&_[aria-checked=false]]:text-slate-300 [&_[aria-checked=true]]:bg-slate-100"
            options={[
              { value: "plain", label: <><span className="sm:hidden">{c.plainShort}</span><span className="hidden sm:inline">{c.plainLong}</span></> },
              { value: "raw", label: <><span className="sm:hidden">{c.rawShort}</span><span className="hidden sm:inline">{c.rawLong}</span></> },
            ]} />
        </>
      }
      bodyClassName="flex flex-col gap-3">
      <div className="flex flex-wrap gap-1.5">
        <Badge dark tone="amber"><EyeOff className="size-3" aria-hidden /> {c.piiHidden(stats.pii)}</Badge>
        <Badge dark tone="violet"><Layers className="size-3" aria-hidden /> LLMLingua-2 {stats.factor ? `${stats.factor}x` : "-"}</Badge>
        <Badge dark tone="violet"><Gauge className="size-3" aria-hidden /> CRAG {stats.cragVerdict ?? "-"} {stats.cragConfidence ?? ""}</Badge>
        <Badge dark tone="sky"><Database className="size-3" aria-hidden /> {c.mcpBadge(stats.mcpCalls, stats.tools, stats.latency.toFixed(0))}</Badge>
        <Badge dark tone="emerald"><Cpu className="size-3" aria-hidden /> {c.tokensSaved(stats.tokensSaved.toLocaleString())}</Badge>
      </div>

      {events.length === 0 && (
        <p className="m-0 py-8 text-center text-[13px] text-slate-400">{c.empty}</p>
      )}

      {events.length > 0 && view === "plain" && (
        <ol className={cn("scroll-thin m-0 list-none space-y-1.5 overflow-y-auto p-0", maxHeightClass)}>
          {PIPELINE.map((node, i) => {
            const done = seen.has(node.id) && (finished || latest !== node.id);
            const active = !finished && latest === node.id;
            const sentence = seen.has(node.id) ? plainSentence(node.id, state, events, lang) : null;
            return (
              <li key={node.id} className={cn("flex gap-3 rounded-lg px-3 py-2 ring-1 ring-inset",
                active ? "bg-emerald-400/10 ring-emerald-400/30" : "bg-white/[0.03] ring-white/[0.06]")}>
                <span className="mt-0.5 shrink-0" aria-hidden>
                  {done ? <CheckCircle2 className="size-4 text-emerald-400" /> : active ? <Loader2 className="size-4 animate-spin text-emerald-300" /> : <CircleDashed className="size-4 text-slate-600" />}
                </span>
                <div className="min-w-0">
                  <div className={cn("text-[13px] font-semibold", seen.has(node.id) ? "text-slate-100" : "text-slate-500")}>
                    <span className="num mr-1.5 text-slate-500">{i + 1}</span>{lang === "bn" ? node.title_bn : node.title}
                  </div>
                  {sentence && <p className="m-0 text-[13px] leading-snug text-slate-300">{sentence}</p>}
                </div>
              </li>
            );
          })}
        </ol>
      )}

      {events.length > 0 && view === "raw" && (
        <div ref={scrollRef} className={cn("scroll-thin min-h-[160px] overflow-y-auto rounded-lg bg-black/40 p-2 font-mono text-[11.5px] leading-relaxed", maxHeightClass)}>
          {events.map((e) => (
            <div key={`${e.session_id}#${e.seq}`} className="border-b border-white/5 py-1 last:border-0">
              <div className="flex gap-2">
                <span className="shrink-0 text-slate-500 tabular-nums">{timeOf(e.timestamp)}</span>
                <Badge dark tone={STEP_TONE[e.step_type]} className="h-fit shrink-0">{e.step_type}</Badge>
                <div className="min-w-0 flex-1 break-words">
                  <span className="text-emerald-300">{e.agent_name}</span>
                  {e.tool_name && <span className="text-sky-300"> → {e.tool_name}</span>}
                  <span className="text-slate-300"> {e.payload_summary}</span>
                </div>
                <span className="shrink-0 text-right text-slate-400 tabular-nums">
                  {e.latency_ms > 0 && `${e.latency_ms.toFixed(0)} ms`}
                  {e.token_saved > 0 && <span className="block text-emerald-400">-{e.token_saved} tok</span>}
                </span>
              </div>
              {Object.keys(e.data).length > 0 && (
                <div className="mt-0.5 truncate pl-[4.5rem] text-[10.5px] text-slate-500" title={JSON.stringify(e.data)}>{JSON.stringify(e.data)}</div>
              )}
            </div>
          ))}
        </div>
      )}
      {sessionId && <div className="font-mono text-[11px] text-slate-500">session {sessionId} · {events.length} events</div>}
    </Panel>
  );
}
