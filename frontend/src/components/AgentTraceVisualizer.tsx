import { Activity, CheckCircle2, CircleDashed, Cpu, Database, EyeOff, Gauge, Layers, Loader2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import type { AgentState, StepType, TraceEvent } from "../api/client";
import { cn, timeOf, tk } from "../lib/format";
import { useAppState } from "../state/store";
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

/** One plain sentence per node, written from the run's final state; falls back to the node's own trace text. */
function plainSentence(node: string, s: AgentState | null, events: TraceEvent[]): string | null {
  const own = events.filter((e) => nodeOf(e) === node);
  if (!s) return own.at(-1)?.payload_summary ?? null;
  const syn = s.syndicate_bypass_plan;
  const cold = s.cold_storage_arbitrage_plan;
  const credit = s.climate_credit_report;
  switch (node) {
    case "pii_guardrail": {
      const hidden = own.filter((e) => e.step_type === "GUARDRAIL").length;
      return `Hid ${hidden} personal detail${hidden === 1 ? "" : "s"} before any agent read the question${s.farmer_offer_tk_per_kg !== null ? `; the middleman offers ${tk(s.farmer_offer_tk_per_kg)}/kg` : ""}.`;
    }
    case "token_compression": {
      const c = s.compression_report;
      return c.reduction_factor ? `Shrank the 7-day DAM price data ${c.reduction_factor}x (${c.original_tokens} to ${c.compressed_tokens} tokens) without dropping a number.` : null;
    }
    case "crag_retrieval": {
      const r = s.rag_crag_result;
      return r ? `Read the question as ${r.dialect}, about ${r.intents.map((i) => INTENT_WORDS[i] ?? i).join(" and ")}; the retrieved guidance passed the CRAG check (${r.verdict.toLowerCase()}, ${r.confidence.toFixed(2)}).` : null;
    }
    case "vision_grading":
      return s.optical_grade_cert ? `Graded the ${s.quantity_kg.toLocaleString("en-IN")} kg lot ${s.optical_grade_cert.grade} and signed certificate ${s.optical_grade_cert.certificate_id}.` : null;
    case "syndicate_bypass":
      return syn ? `Found a ${syn.markup_pct.toFixed(0)}% farm-to-retail markup (${syn.severity.toLowerCase()}); a pooled truck to ${syn.best_hub_name} pays ${tk(syn.b2b_net_tk_per_kg)}/kg.` : null;
    case "coldchain_arbitrage":
      if (!cold) return null;
      return cold.distress_sale_blocked
        ? `Blocked the ${tk(s.farmer_offer_tk_per_kg)} Faria sale, below the ${tk(cold.circuit_breaker?.production_cost_floor_bdt ?? 15, 0)} cost floor; ${cold.decision === "SELL_POOLED_B2B" ? "the pooled truck beats storing" : "storing beats selling now"}.`
        : `Compared storage with the pooled sale: ${cold.decision.replaceAll("_", " ").toLowerCase()}.`;
    case "climate_credit":
      if (!credit) return null;
      return `${credit.flood_applicable && credit.flood_breach_probability_pct !== null
        ? `Haor breach chance ${credit.flood_breach_probability_pct.toFixed(1)}% (${credit.flood_alert_level?.toLowerCase()})`
        : credit.seventy_two_hour_clearance ? "No storm or flood risk in the next 72 hours" : "Storm warning in the next 72 hours"}; credit score ${credit.credit_score}${credit.loan_eligible ? ` unlocks ${tk(credit.loan_amount_tk, 0)} at ${credit.annual_rate_pct}%` : ""}.`;
    case "supervisor_review":
      return own.some((e) => e.payload_summary.includes("re-planning")) ? "Sent the cold-chain plan back because the chamber was out of band, then approved it." : "Checked that the plans agree; no re-plan needed.";
    case "voice_synthesizer":
      return s.final_bangla_voice_response ? `Wrote a ${s.final_bangla_voice_response.length}-character Bangla reply${s.requires_farmer_voice_approval ? " and asked the farmer for a yes" : ""}.` : null;
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
    <Panel well className={className} icon={<Activity className="size-4 text-emerald-400" aria-hidden />} title="Live agent and MCP trace"
      actions={
        <>
          <LiveDot status={status} />
          <Segmented label="Trace view" value={view} onChange={setView} className="bg-white/5 ring-white/10 [&_[aria-checked=false]]:text-slate-300 [&_[aria-checked=true]]:bg-slate-100"
            options={[
              { value: "plain", label: <><span className="sm:hidden">Plain language</span><span className="hidden sm:inline">Plain-language judge view</span></> },
              { value: "raw", label: <><span className="sm:hidden">Raw JSON-RPC</span><span className="hidden sm:inline">Raw JSON-RPC and telemetry</span></> },
            ]} />
        </>
      }
      bodyClassName="flex flex-col gap-3">
      <div className="flex flex-wrap gap-1.5">
        <Badge dark tone="amber"><EyeOff className="size-3" aria-hidden /> {stats.pii} personal detail{stats.pii === 1 ? "" : "s"} hidden</Badge>
        <Badge dark tone="violet"><Layers className="size-3" aria-hidden /> LLMLingua-2 {stats.factor ? `${stats.factor}x` : "-"}</Badge>
        <Badge dark tone="violet"><Gauge className="size-3" aria-hidden /> CRAG {stats.cragVerdict ?? "-"} {stats.cragConfidence ?? ""}</Badge>
        <Badge dark tone="sky"><Database className="size-3" aria-hidden /> {stats.mcpCalls} MCP calls · {stats.tools}/13 tools · {stats.latency.toFixed(0)} ms</Badge>
        <Badge dark tone="emerald"><Cpu className="size-3" aria-hidden /> {stats.tokensSaved.toLocaleString()} tokens saved</Badge>
      </div>

      {events.length === 0 && (
        <p className="m-0 py-8 text-center text-[13px] text-slate-400">
          Waiting for a farmer request. Tap a voice preset on the farmer's phone, or run a simulation, and every agent step streams here.
        </p>
      )}

      {events.length > 0 && view === "plain" && (
        <ol className={cn("scroll-thin m-0 list-none space-y-1.5 overflow-y-auto p-0", maxHeightClass)}>
          {PIPELINE.map((node, i) => {
            const done = seen.has(node.id) && (finished || latest !== node.id);
            const active = !finished && latest === node.id;
            const sentence = seen.has(node.id) ? plainSentence(node.id, state, events) : null;
            return (
              <li key={node.id} className={cn("flex gap-3 rounded-lg px-3 py-2 ring-1 ring-inset",
                active ? "bg-emerald-400/10 ring-emerald-400/30" : "bg-white/[0.03] ring-white/[0.06]")}>
                <span className="mt-0.5 shrink-0" aria-hidden>
                  {done ? <CheckCircle2 className="size-4 text-emerald-400" /> : active ? <Loader2 className="size-4 animate-spin text-emerald-300" /> : <CircleDashed className="size-4 text-slate-600" />}
                </span>
                <div className="min-w-0">
                  <div className={cn("text-[13px] font-semibold", seen.has(node.id) ? "text-slate-100" : "text-slate-500")}>
                    <span className="num mr-1.5 text-slate-500">{i + 1}</span>{node.title}
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
