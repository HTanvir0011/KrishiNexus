import { Check } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "../lib/format";

/**
 * A lot's road as steps (listed, sold, on the road, delivered). The emerald line fills to the current step and eases
 * forward when the state advances, so a status change reads as progress along the route rather than a new label.
 */
export function RouteSteps({ steps, at, label, icon, className }: {
  steps: string[];
  /** Index of the current step; earlier steps are done. */
  at: number;
  label: string;
  /** Shown inside the current step's dot, such as a truck while the load is on the road. */
  icon?: ReactNode;
  className?: string;
}) {
  const n = steps.length;
  const inset = `${50 / n}%`; // the line runs from the first dot's centre to the last one's
  const done = at >= n - 1;
  return (
    <div className={cn("relative", className)}>
      <span aria-hidden className="absolute top-2.5 h-0.5 -translate-y-1/2 rounded-full bg-slate-200" style={{ left: inset, right: inset }} />
      <span aria-hidden className="absolute top-2.5 h-0.5 -translate-y-1/2 origin-left rounded-full bg-emerald-600 transition-transform duration-700 ease-(--ease-out-expo)"
        style={{ left: inset, right: inset, transform: `scaleX(${n > 1 ? Math.max(0, at) / (n - 1) : 1})` }} />
      <ol aria-label={label} className="relative m-0 grid list-none p-0" style={{ gridTemplateColumns: `repeat(${n}, minmax(0, 1fr))` }}>
        {steps.map((step, i) => (
          <li key={step} aria-current={i === at ? "step" : undefined} className="flex min-w-0 flex-col items-center gap-1 text-center">
            <span className={cn("grid size-5 place-items-center rounded-full ring-2 ring-white transition-colors duration-300",
              i < at || (i === at && done) ? "bg-emerald-600 text-white" : i === at ? "bg-emerald-700 text-white shadow-sm" : "bg-slate-200 text-slate-400")}>
              {i < at || (i === at && done) ? <Check className="size-3" strokeWidth={3} aria-hidden />
                : i === at ? (icon ?? <span className="size-1.5 rounded-full bg-white" />) : null}
            </span>
            <span className={cn("max-w-full truncate text-[11.5px] leading-tight", i <= at ? "font-medium text-slate-800" : "text-slate-500")}>{step}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
