import { Cpu, Server, Truck, WifiOff } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";

import { api, type LocalModelsReport } from "../api/client";
import { AgentTraceVisualizer } from "../components/AgentTraceVisualizer";

// Three.js stays out of the main OS chunk until this panel actually renders.
const ColdStorage3DTwin = lazy(() => import("../components/ColdStorage3DTwin").then((m) => ({ default: m.ColdStorage3DTwin })));
import { TruckPoolMap } from "../components/TruckPoolMap";
import { Badge, Stat } from "../components/ui";
import { cn, kg } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { useAppState } from "../state/store";

const COPY = {
  en: {
    core: {
      offlinePrefix: "Offline edge mode:",
      onRuntime: "on the local runtime",
      onDevice: "on-device fallback",
      modelled: "(modelled)",
      weatherTail: "; weather falls back to climatology.",
      cloud: "Cloud core: 3 MCP servers, 13 tools, a LangGraph supervisor and 4 agents.",
      compression: "context compression",
    },
    stats: {
      markup: "Live markup seen",
      markupHint: "run a farmer question",
      pooled: "Pooled micro-lots",
      farmersSuffix: " farmers",
      poolsSuffix: " pools",
      trucks: "Trucks dispatched",
      trucksHint: "escrow-locked 5-ton loads",
      quota: "Open smallholder quota",
      quotaHintPre: "within 60 km of ",
      quotaHintPost: "",
    },
  },
  bn: {
    core: {
      offlinePrefix: "অফলাইন এজ মোড:",
      onRuntime: "লোকাল রানটাইমে",
      onDevice: "অন-ডিভাইস ফলব্যাকে",
      modelled: "(মডেলড)",
      weatherTail: "; আবহাওয়া ক্লাইমাটোলজি ফলব্যাকে চলছে।",
      cloud: "ক্লাউড কোর: 3টি MCP সার্ভার, 13টি টুল, একটি LangGraph সুপারভাইজার আর 4টি এজেন্ট।",
      compression: "কনটেক্সট কমপ্রেশন",
    },
    stats: {
      markup: "লাইভ মার্কআপ",
      markupHint: "কৃষকের একটা প্রশ্ন চালিয়ে দেখুন",
      pooled: "পুল করা মাইক্রো-লট",
      farmersSuffix: " জন কৃষক",
      poolsSuffix: "টি পুল",
      trucks: "ডিসপ্যাচ হওয়া ট্রাক",
      trucksHint: "এসক্রো-লক করা 5 টনের লোড",
      quota: "প্রান্তিক কৃষকের খোলা কোটা",
      quotaHintPre: "",
      quotaHintPost: "-এর 60 কিমির মধ্যে",
    },
  },
};

/** What answers the farmer right now: the cloud core, or the on-device model when the navbar's blackout toggle is on. */
function CoreLine() {
  const c = useCopy(COPY).core;
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
        ? <span>{c.offlinePrefix} {qwen?.display_name ?? "Qwen-2.5-7B Q4_K_M"} {runtimeUp ? c.onRuntime : c.onDevice}{qwen ? ` · ${qwen.telemetry.vram_mb} MB ${c.modelled}` : ""}{c.weatherTail}</span>
        : <span>{c.cloud}</span>}
      {state?.rag_crag_result && <Badge tone="violet">CRAG {state.rag_crag_result.verdict.toLowerCase()} {state.rag_crag_result.confidence.toFixed(2)}</Badge>}
      {state?.compression_report.reduction_factor && <Badge tone="violet"><Cpu className="size-3" aria-hidden /> {state.compression_report.reduction_factor}x {c.compression}</Badge>}
    </div>
  );
}

export function CommandCenter({ className }: { className?: string }) {
  const c = useCopy(COPY).stats;
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
        <Stat label={c.markup} value={markup ? `${markup.toFixed(0)}%` : "-"} hint={state ? `${state.crop}, ${state.district}` : c.markupHint} tone="red" />
        <Stat label={c.pooled} value={kg(kpis.pooled)} hint={`${kpis.smallholders}${c.farmersSuffix} · ${pools.length}${c.poolsSuffix}`} tone="emerald" />
        <Stat label={c.trucks} value={<span className="flex items-center gap-1"><Truck className="size-4" aria-hidden />{kpis.dispatched}</span>} hint={c.trucksHint} tone="amber" />
        <Stat label={c.quota} value={quota ? `${Math.round(quota.total_open_smallholder_quota_mt).toLocaleString("en-IN")} t` : "-"} hint={quota ? `${c.quotaHintPre}${quota.district}${c.quotaHintPost}` : ""} tone="sky" />
      </div>
      <CoreLine />
      <div className="grid min-w-0 gap-4 xl:grid-cols-5">
        <Suspense fallback={<div className="well min-h-[420px] xl:col-span-3" aria-busy />}>
          <ColdStorage3DTwin className="xl:col-span-3" />
        </Suspense>
        <TruckPoolMap className="xl:col-span-2" />
      </div>
      <AgentTraceVisualizer />
    </div>
  );
}
