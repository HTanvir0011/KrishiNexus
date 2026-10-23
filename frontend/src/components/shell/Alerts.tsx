import { X } from "lucide-react";

import { cn } from "../../lib/format";
import { setState, useAppState, type AlertTone } from "../../state/store";

const TONE: Record<AlertTone, string> = {
  info: "border-sky-400/40",
  success: "border-emerald-400/45",
  warn: "border-amber-400/45",
  danger: "border-red-400/50",
};

export function Alerts() {
  const alerts = useAppState((s) => s.alerts);
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[360px] max-w-[calc(100vw-2rem)] flex-col gap-2" aria-live="polite">
      {alerts.map((alert) => (
        <div key={alert.id} className={cn("pointer-events-auto rounded-2xl border bg-ink-850/95 p-3 text-[13px] backdrop-blur", TONE[alert.tone])}>
          <div className="flex items-start justify-between gap-2">
            <div className="font-semibold text-slate-50">{alert.title}</div>
            <button type="button" aria-label="Dismiss" className="rounded-full p-0.5 text-slate-400 hover:text-slate-100"
              onClick={() => setState((s) => ({ alerts: s.alerts.filter((a) => a.id !== alert.id) }))}>
              <X className="size-3.5" />
            </button>
          </div>
          {alert.detail && <div className="mt-1 leading-relaxed text-slate-300">{alert.detail}</div>}
        </div>
      ))}
    </div>
  );
}
