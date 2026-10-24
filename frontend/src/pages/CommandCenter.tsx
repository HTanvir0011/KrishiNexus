import { Cpu, Server, Truck, WifiOff } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api, type LocalModelsReport } from "../api/client";
import { AgentTraceVisualizer } from "../components/AgentTraceVisualizer";
import { ColdStorage3DTwin } from "../components/ColdStorage3DTwin";
import { TruckPoolMap } from "../components/TruckPoolMap";
import { Badge, Stat } from "../components/ui";
import { cn, kg } from "../lib/format";
import { useAppState } from "../state/store";

/** What answers the farmer right now: the cloud core, or the on-device model when the navbar's blackout toggle is on. */
function CoreLine() {
  const offline = useAppState((s) => s.offlineMode);
  const voice = useAppState((s) => s.lastVoice);
  const [models, setModels] = useState<LocalModelsReport | null>(null);
  const state = voice?.orchestration?.state;

  useEffect(() => {
    if (offline && !models) void api.localModels().then((r) => setModels(r.data));
  }, [offline, models]);

  const qwen = models?.models.find((m) => m.key === "qwen2.5-7b");
  const runtimeUp = models?.runtimes.some((r) => r.reachable);
  return (
    <div className={cn("flex flex-wrap items-center gap-2 rounded-lg px-3 py-2 text-[13px] ring-1 ring-inset",
      offline ? "bg-amber-100/60 text-amber-900 ring-amber-600/25" : "bg-white text-slate-600 ring-slate-200")}>
      {offline ? <WifiOff className="size-4 text-amber-700" aria-hidden /> : <Server className="size-4 text-emerald-700" aria-hidden />}
      {offline
        ? <span>Offline edge mode: {qwen?.display_name ?? "Qwen-2.5-7B Q4_K_M"} {runtimeUp ? "on the local runtime" : "on-device fallback"}{qwen ? ` · ${qwen.telemetry.vram_mb} MB (modelled)` : ""}; weather falls back to climatology.</span>
        : <span>Cloud core: 3 MCP servers, 13 tools, a LangGraph supervisor and 4 agents.</span>}
      {state?.rag_crag_result && <Badge tone="violet">CRAG {state.rag_crag_result.verdict.toLowerCase()} {state.rag_crag_result.confidence.toFixed(2)}</Badge>}
      {state?.compression_report.reduction_factor && <Badge tone="violet"><Cpu className="size-3" aria-hidden /> {state.compression_report.reduction_factor}x context compression</Badge>}
    </div>
  );
}

export function CommandCenter({ className }: { className?: string }) {
  const pools = useAppState((s) => s.pools);
  const quota = useAppState((s) => s.quota);
  const voice = useAppState((s) => s.lastVoice);
  const kpis = useMemo(() => {
    const pooled = pools.reduce((sum, p) => sum + p.loaded_kg, 0);
    const dispatched = pools.filter((p) => p.status === "DISPATCHED").length;
    const smallholders = pools.reduce((sum, p) => sum + p.smallholders, 0);
    return { pooled, dispatched, smallholders };
  }, [pools]);
  const state = voice?.orchestration?.state;
  const markup = state?.syndicate_bypass_plan?.markup_pct;

  return (
    <div className={cn("flex min-w-0 flex-col gap-4", className)}>
      <div className="surface grid grid-cols-2 gap-4 p-4 md:grid-cols-4">
        <Stat label="Live markup seen" value={markup ? `${markup.toFixed(0)}%` : "-"} hint={state ? `${state.crop}, ${state.district}` : "run a farmer question"} tone="red" />
        <Stat label="Pooled micro-lots" value={kg(kpis.pooled)} hint={`${kpis.smallholders} farmers · ${pools.length} pools`} tone="emerald" />
        <Stat label="Trucks dispatched" value={<span className="flex items-center gap-1"><Truck className="size-4" aria-hidden />{kpis.dispatched}</span>} hint="escrow-locked 5-ton loads" tone="amber" />
        <Stat label="Open smallholder quota" value={quota ? `${Math.round(quota.total_open_smallholder_quota_mt).toLocaleString("en-IN")} t` : "-"} hint={quota ? `within 60 km of ${quota.district}` : ""} tone="sky" />
      </div>
      <CoreLine />
      <div className="grid min-w-0 gap-4 xl:grid-cols-5">
        <ColdStorage3DTwin className="xl:col-span-3" />
        <TruckPoolMap className="xl:col-span-2" />
      </div>
      <AgentTraceVisualizer />
    </div>
  );
}
