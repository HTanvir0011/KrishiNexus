import { Activity, Cpu, Database, EyeOff, Gauge, Layers, Radio } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import type { StepType, TraceEvent } from "../api/client";
import { cn, timeOf } from "../lib/format";
import { useAppState } from "../state/store";
import { Badge, Panel, type Tone } from "./ui";

const PIPELINE: { node: string; label: string }[] = [
  { node: "pii_guardrail", label: "PII" },
  { node: "token_compression", label: "LLMLingua" },
  { node: "crag_retrieval", label: "HyDE+CRAG" },
  { node: "vision_grading", label: "A1 Vision" },
  { node: "syndicate_bypass", label: "A2 Market" },
  { node: "coldchain_arbitrage", label: "A3 Cold-chain" },
  { node: "climate_credit", label: "A4 Climate+Credit" },
  { node: "supervisor", label: "Review" },
  { node: "voice_synthesizer", label: "Voice" },
];

const STEP_TONE: Record<StepType, Tone> = {
  THOUGHT: "slate",
  MCP_CALL: "sky",
  RAG_CRAG: "violet",
  GUARDRAIL: "amber",
  DECISION: "emerald",
};

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

export function AgentTraceVisualizer({ className, maxHeightClass = "max-h-[360px]" }: { className?: string; maxHeightClass?: string }) {
  const traces = useAppState((s) => s.traces);
  const sessionId = useAppState((s) => s.activeSessionId);
  const status = useAppState((s) => s.traceStatus);
  const [allSessions, setAllSessions] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const events = useMemo(
    () => (allSessions || !sessionId ? traces : traces.filter((e) => e.session_id === sessionId)),
    [traces, sessionId, allSessions],
  );
  const stats = useMemo(() => summarize(events), [events]);
  const seenNodes = useMemo(() => new Set(events.map((e) => e.agent_name)), [events]);
  const latestNode = events.at(-1)?.agent_name;

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [events.length]);

  return (
    <Panel
      className={className}
      icon={<Activity className="size-4 text-emerald-400" />}
      title="Live LangGraph + MCP Reasoning Trace"
      actions={
        <>
          <span className={cn("flex items-center gap-1 text-[10px] font-medium",
            status === "open" ? "text-emerald-300" : status === "connecting" ? "text-amber-300" : "text-red-300")}>
            <Radio className={cn("size-3", status === "open" && "animate-pulse-soft")} /> ws/agent-trace {status}
          </span>
          <button type="button" onClick={() => setAllSessions((v) => !v)}
            className="rounded-md bg-ink-800 px-1.5 py-0.5 text-[10px] text-slate-300 ring-1 ring-ink-600 hover:bg-ink-700">
            {allSessions ? "all sessions" : "this session"}
          </button>
        </>
      }
      bodyClassName="flex flex-col gap-2"
    >
      <div className="flex flex-wrap items-center gap-1">
        {PIPELINE.map((step, i) => (
          <div key={step.node} className="flex items-center gap-1">
            <span className={cn(
              "rounded-md px-1.5 py-0.5 text-[10px] font-semibold ring-1 transition-colors",
              seenNodes.has(step.node) ? "bg-emerald-500/15 text-emerald-300 ring-emerald-400/40" : "bg-ink-800 text-slate-500 ring-ink-600",
              latestNode === step.node && "animate-pulse-soft bg-emerald-400/30",
            )}>
              {step.label}
            </span>
            {i < PIPELINE.length - 1 && <span className="text-[10px] text-ink-600">→</span>}
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-1.5">
        <Badge tone="amber"><EyeOff className="size-3" /> {stats.pii} PII redacted → &lt;BD_PHONE_REDACTED&gt;</Badge>
        <Badge tone="violet"><Layers className="size-3" /> LLMLingua-2 {stats.factor ? `${stats.factor}x` : "-"}</Badge>
        <Badge tone="violet"><Gauge className="size-3" /> CRAG {stats.cragVerdict ?? "-"} {stats.cragConfidence ?? ""}</Badge>
        <Badge tone="sky"><Database className="size-3" /> {stats.mcpCalls} MCP calls · {stats.tools}/13 tools · {stats.latency.toFixed(0)} ms</Badge>
        <Badge tone="emerald"><Cpu className="size-3" /> {stats.tokensSaved.toLocaleString()} tokens saved</Badge>
      </div>

      <div ref={scrollRef} className={cn("scroll-thin min-h-[140px] flex-1 overflow-y-auto rounded-lg bg-black/40 p-2 font-mono text-[11px] leading-relaxed", maxHeightClass)}>
        {events.length === 0 && (
          <div className="py-8 text-center text-slate-500">
            Waiting for a farmer request. Trigger a voice preset or the 3D-twin simulations to stream agent thoughts here.
          </div>
        )}
        {events.map((e) => (
          <div key={`${e.session_id}#${e.seq}`} className="flex gap-2 border-b border-white/5 py-1 last:border-0">
            <span className="shrink-0 text-slate-600">{timeOf(e.timestamp)}</span>
            <Badge tone={STEP_TONE[e.step_type]} className="h-fit shrink-0">{e.step_type}</Badge>
            <div className="min-w-0 flex-1">
              <span className="text-emerald-300">{e.agent_name}</span>
              {e.tool_name && <span className="text-sky-300"> ⇢ {e.tool_name}</span>}
              <span className="text-slate-300"> {e.payload_summary}</span>
            </div>
            <span className="shrink-0 text-right text-slate-500">
              {e.latency_ms > 0 && `${e.latency_ms.toFixed(0)}ms`}
              {e.token_saved > 0 && <span className="block text-emerald-400">-{e.token_saved}t</span>}
            </span>
          </div>
        ))}
      </div>
    </Panel>
  );
}
