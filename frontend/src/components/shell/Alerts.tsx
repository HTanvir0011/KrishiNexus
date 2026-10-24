import { X } from "lucide-react";

import { cn } from "../../lib/format";
import { setState, useAppState, type AlertTone } from "../../state/store";

const TONE: Record<AlertTone, string> = {
  info: "border-l-sky-600",
  success: "border-l-emerald-700",
  warn: "border-l-amber-600",
  danger: "border-l-rose-600",
};

export function Alerts() {
  const alerts = useAppState((s) => s.alerts);
  return (
    <div className="pointer-events-none fixed right-4 bottom-4 z-50 flex w-[360px] max-w-[calc(100vw-2rem)] flex-col gap-2" aria-live="polite">
      {alerts.map((alert) => (
        <div key={alert.id} className={cn("pointer-events-auto animate-rise rounded-xl border border-l-4 border-slate-200 bg-white p-3 text-[13px] shadow-lift", TONE[alert.tone])}>
          <div className="flex items-start justify-between gap-2">
            <div className="font-semibold text-slate-900">{alert.title}</div>
            <button type="button" aria-label="Dismiss" className="rounded-md p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              onClick={() => setState((s) => ({ alerts: s.alerts.filter((a) => a.id !== alert.id) }))}>
              <X className="size-3.5" />
            </button>
          </div>
          {alert.detail && <div className="mt-1 leading-relaxed text-slate-600">{alert.detail}</div>}
        </div>
      ))}
    </div>
  );
}
