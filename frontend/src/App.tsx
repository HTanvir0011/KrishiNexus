import { BookOpen, Columns2, Landmark, LayoutDashboard, Smartphone, Sprout, X } from "lucide-react";
import { useEffect, useState } from "react";

import { api, connectAgentTrace } from "./api/client";
import { cn } from "./lib/format";
import { BuyerBankPortal } from "./pages/BuyerBankPortal";
import { CommandCenter } from "./pages/CommandCenter";
import { DocsPage } from "./pages/DocsPage";
import { FarmerZeroUIApp } from "./pages/FarmerZeroUIApp";
import { pushTraces, refreshPools, refreshQuota, refreshTelemetry, setState, useAppState, type AlertTone } from "./state/store";

type View = "split" | "farmer" | "command" | "bank" | "docs";

const TABS: { id: View; label: string; icon: typeof Sprout }[] = [
  { id: "split", label: "Split-Screen Judge Mode", icon: Columns2 },
  { id: "farmer", label: "Farmer Zero-UI", icon: Smartphone },
  { id: "command", label: "OS Command Center (3D Twin)", icon: LayoutDashboard },
  { id: "bank", label: "B2B & Bank Credit Portal", icon: Landmark },
  { id: "docs", label: "/docs Whitepaper & MCP Inspector", icon: BookOpen },
];

/** `/docs`, `/docs#section` and `#docs` open the whitepaper directly (shareable submission link). */
function viewFromLocation(): View {
  return location.pathname.replace(/\/+$/, "") === "/docs" || location.hash === "#docs" ? "docs" : "split";
}

const ALERT_STYLE: Record<AlertTone, string> = {
  info: "border-sky-400/40 bg-sky-950/90",
  success: "border-emerald-400/40 bg-emerald-950/90",
  warn: "border-amber-400/40 bg-amber-950/90",
  danger: "border-red-400/40 bg-red-950/90",
};

function useBackendBootstrap() {
  useEffect(() => {
    const stopTrace = connectAgentTrace(pushTraces, (traceStatus) => setState({ traceStatus }));
    const health = () => api.health().then(() => setState({ backendLive: true })).catch(() => setState({ backendLive: false }));
    void health();
    void refreshPools();
    void refreshTelemetry();
    void refreshQuota();
    const timers = [
      window.setInterval(health, 10_000),
      window.setInterval(() => void refreshTelemetry(), 6_000),
      window.setInterval(() => void refreshPools(), 9_000),
    ];
    return () => {
      stopTrace();
      timers.forEach((t) => window.clearInterval(t));
    };
  }, []);
}

export default function App() {
  const [view, setViewState] = useState<View>(viewFromLocation);
  const live = useAppState((s) => s.backendLive);
  const alerts = useAppState((s) => s.alerts);
  useBackendBootstrap();

  useEffect(() => {
    const onPop = () => setViewState(viewFromLocation());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const setView = (next: View) => {
    setViewState(next);
    const path = next === "docs" ? "/docs" : "/";
    if (location.pathname !== path) history.pushState(null, "", path);
  };

  return (
    <div className="flex h-full flex-col">
      <nav className="sticky top-0 z-20 flex flex-wrap items-center gap-2 border-b border-ink-700 bg-ink-950/95 px-3 py-2 backdrop-blur">
        <div className="mr-2 flex items-center gap-2">
          <div className="grid size-8 place-items-center rounded-lg bg-emerald-500/20 ring-1 ring-emerald-400/40">
            <Sprout className="size-5 text-emerald-300" />
          </div>
          <div className="leading-tight">
            <div className="text-sm font-bold text-slate-50">KrishiNexus OS</div>
            <div className="text-[10px] text-slate-500">Edge-to-cloud agri OS · Bangladesh</div>
          </div>
        </div>
        <div className="flex flex-1 flex-wrap gap-1" role="tablist">
          {TABS.map((tab) => (
            <button key={tab.id} type="button" role="tab" aria-selected={view === tab.id} onClick={() => setView(tab.id)}
              className={cn("flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors",
                view === tab.id ? "bg-emerald-500 text-ink-950" : "text-slate-300 hover:bg-ink-800")}>
              <tab.icon className="size-3.5" /> {tab.label}
            </button>
          ))}
        </div>
        <span className={cn("flex items-center gap-1.5 rounded-full px-2 py-1 text-[10px] font-semibold ring-1",
          live === null ? "text-slate-400 ring-ink-600" : live ? "text-emerald-300 ring-emerald-500/40" : "text-red-300 ring-red-500/40")}>
          <span className={cn("size-2 rounded-full", live === null ? "bg-slate-500" : live ? "bg-emerald-400 animate-pulse-soft" : "bg-red-400")} />
          {live === null ? "connecting" : live ? "FastAPI :8000 live" : "backend offline · cached demo"}
        </span>
      </nav>

      <main className="min-h-0 flex-1 p-3">
        {view === "split" && (
          <div className="grid h-full min-h-0 gap-3 xl:grid-cols-[minmax(360px,35%)_1fr]">
            <FarmerZeroUIApp className="xl:sticky xl:top-16 xl:max-h-[calc(100vh-5rem)]" />
            <CommandCenter />
          </div>
        )}
        {view === "farmer" && <FarmerZeroUIApp className="mx-auto max-w-md" />}
        {view === "command" && <CommandCenter />}
        {view === "bank" && <BuyerBankPortal />}
        {view === "docs" && <DocsPage />}
      </main>

      <div className="pointer-events-none fixed bottom-3 right-3 z-30 flex w-[360px] max-w-[calc(100vw-1.5rem)] flex-col gap-2" aria-live="polite">
        {alerts.map((alert) => (
          <div key={alert.id} className={cn("pointer-events-auto rounded-xl border p-3 text-xs shadow-xl backdrop-blur", ALERT_STYLE[alert.tone])}>
            <div className="flex items-start justify-between gap-2">
              <div className="font-semibold text-slate-50">{alert.title}</div>
              <button type="button" aria-label="Dismiss" onClick={() => setState((s) => ({ alerts: s.alerts.filter((a) => a.id !== alert.id) }))}>
                <X className="size-3.5 text-slate-400" />
              </button>
            </div>
            {alert.detail && <div className="mt-1 leading-relaxed text-slate-300">{alert.detail}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}
