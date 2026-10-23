import { Cpu, Leaf, TrendingDown, TrendingUp, Truck, WifiOff } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api, type LocalModelsReport } from "../api/client";
import { AgentTraceVisualizer } from "../components/AgentTraceVisualizer";
import { ColdStorage3DTwin } from "../components/ColdStorage3DTwin";
import { TruckPoolMap } from "../components/TruckPoolMap";
import { Badge, Stat } from "../components/ui";
import { cn, kg } from "../lib/format";
import { setState, useAppState } from "../state/store";

function OfflineToggle() {
  const offline = useAppState((s) => s.offlineMode);
  const [models, setModels] = useState<LocalModelsReport | null>(null);

  useEffect(() => {
    if (offline && !models) void api.localModels().then((r) => setModels(r.data));
  }, [offline, models]);

  const qwen = models?.models.find((m) => m.key === "qwen2.5-7b");
  const runtimeUp = models?.runtimes.some((r) => r.reachable);
  return (
    <div className={cn("flex items-center gap-2 rounded-xl px-3 py-2 ring-1", offline ? "bg-amber-500/10 ring-amber-400/40" : "bg-ink-800 ring-ink-600")}>
      <button type="button" role="switch" aria-checked={offline} onClick={() => setState({ offlineMode: !offline })}
        className={cn("relative h-5 w-9 rounded-full transition-colors", offline ? "bg-amber-400" : "bg-ink-600")}>
        <span className={cn("absolute top-0.5 size-4 rounded-full bg-white transition-all", offline ? "left-4.5" : "left-0.5")} />
      </button>
      <div className="text-[11px] leading-tight">
        <div className="flex items-center gap-1 font-semibold text-slate-100"><WifiOff className="size-3" /> Offline rural blackout</div>
        <div className="text-slate-400">
          {offline
            ? `${qwen?.display_name ?? "Qwen-2.5-7B Q4_K_M"} · ${runtimeUp ? "local runtime live" : "on-device fallback"} · ${qwen ? `${qwen.telemetry.vram_mb} MB` : ""}`
            : "Cloud agents + live weather"}
        </div>
      </div>
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
    <div className={cn("flex min-h-0 flex-col gap-3", className)}>
      <div className="panel grid grid-cols-2 gap-3 p-3 md:grid-cols-4 xl:grid-cols-7">
        <Stat label="Spoilage addressed" value="$2.4B / yr" hint="post-harvest loss target" tone="amber" />
        <Stat label="Syndicate spread" value={<span className="flex items-center gap-1"><TrendingDown className="size-3.5" />116% → 34%</span>} hint="compression target" tone="emerald" />
        <Stat label="Farmer income" value={<span className="flex items-center gap-1"><TrendingUp className="size-3.5" />+32%</span>} hint="BAU grading + MAP" tone="emerald" />
        <Stat label="Live markup seen" value={markup ? `${markup.toFixed(0)}%` : "-"} hint={state ? `${state.crop}, ${state.district}` : "run a farmer query"} tone="red" />
        <Stat label="Pooled micro-lots" value={kg(kpis.pooled)} hint={`${kpis.smallholders} smallholders · ${pools.length} pools`} tone="sky" />
        <Stat label="Trucks dispatched" value={<span className="flex items-center gap-1"><Truck className="size-3.5" />{kpis.dispatched}</span>} hint="escrow-locked 5-ton loads" tone="amber" />
        <Stat label="Open smallholder quota" value={quota ? `${quota.total_open_smallholder_quota_mt.toLocaleString()} t` : "-"} hint={quota ? `within 60 km of ${quota.district}` : ""} tone="violet" />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <Leaf className="size-4 text-emerald-400" />
          <span>Cloud core: 3 MCP servers, 13 tools, a LangGraph supervisor and 4 agents</span>
          {state?.rag_crag_result && <Badge tone="violet">CRAG {state.rag_crag_result.verdict} {state.rag_crag_result.confidence.toFixed(2)}</Badge>}
          {state?.compression_report.reduction_factor && <Badge tone="violet"><Cpu className="size-3" /> {state.compression_report.reduction_factor}x context compression</Badge>}
        </div>
        <OfflineToggle />
      </div>

      <div className="grid min-h-0 gap-3 lg:grid-cols-5">
        <ColdStorage3DTwin className="lg:col-span-3" />
        <TruckPoolMap className="lg:col-span-2" />
      </div>
      <AgentTraceVisualizer maxHeightClass="max-h-[320px]" />
    </div>
  );
}
