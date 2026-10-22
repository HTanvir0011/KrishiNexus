import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "../lib/format";

export type Tone = "emerald" | "amber" | "red" | "sky" | "violet" | "slate";

const BADGE_TONES: Record<Tone, string> = {
  emerald: "bg-emerald-500/15 text-emerald-300 ring-emerald-400/30",
  amber: "bg-amber-500/15 text-amber-300 ring-amber-400/30",
  red: "bg-red-500/15 text-red-300 ring-red-400/30",
  sky: "bg-sky-500/15 text-sky-300 ring-sky-400/30",
  violet: "bg-violet-500/15 text-violet-300 ring-violet-400/30",
  slate: "bg-slate-500/15 text-slate-300 ring-slate-400/25",
};

export function Badge({ tone = "slate", className, children }: { tone?: Tone; className?: string; children: ReactNode }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset", BADGE_TONES[tone], className)}>
      {children}
    </span>
  );
}

export function Panel({ title, icon, actions, className, bodyClassName, children }: {
  title?: ReactNode;
  icon?: ReactNode;
  actions?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}) {
  return (
    <section className={cn("panel flex min-h-0 flex-col", className)}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-2 border-b border-ink-700 px-3 py-2">
          <h2 className="flex min-w-0 items-center gap-2 text-[13px] font-semibold tracking-wide text-slate-100">
            {icon}
            <span className="truncate">{title}</span>
          </h2>
          {actions && <div className="flex shrink-0 items-center gap-1.5">{actions}</div>}
        </header>
      )}
      <div className={cn("min-h-0 flex-1 p-3", bodyClassName)}>{children}</div>
    </section>
  );
}

const BUTTON_VARIANTS = {
  primary: "bg-emerald-500 text-ink-950 hover:bg-emerald-400 disabled:bg-emerald-500/40",
  amber: "bg-amber-400 text-ink-950 hover:bg-amber-300 disabled:bg-amber-400/40",
  danger: "bg-red-500/90 text-white hover:bg-red-500 disabled:bg-red-500/40",
  ghost: "bg-ink-800 text-slate-200 ring-1 ring-ink-600 hover:bg-ink-700 disabled:opacity-50",
} as const;

export function Button({ variant = "ghost", className, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof BUTTON_VARIANTS;
}) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400 disabled:cursor-not-allowed",
        BUTTON_VARIANTS[variant],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function Stat({ label, value, hint, tone = "slate" }: { label: string; value: ReactNode; hint?: ReactNode; tone?: Tone }) {
  const valueTone = {
    emerald: "text-emerald-300", amber: "text-amber-300", red: "text-red-300", sky: "text-sky-300", violet: "text-violet-300", slate: "text-slate-100",
  }[tone];
  return (
    <div className="min-w-0">
      <div className="truncate text-[10px] font-medium uppercase tracking-wider text-slate-500">{label}</div>
      <div className={cn("truncate font-mono text-sm font-semibold tabular-nums", valueTone)}>{value}</div>
      {hint && <div className="truncate text-[10px] text-slate-500">{hint}</div>}
    </div>
  );
}

export function ProgressBar({ value, max, tone = "emerald", className }: { value: number; max: number; tone?: Tone; className?: string }) {
  const fill = { emerald: "bg-emerald-400", amber: "bg-amber-400", red: "bg-red-400", sky: "bg-sky-400", violet: "bg-violet-400", slate: "bg-slate-400" }[tone];
  return (
    <div className={cn("h-2 w-full overflow-hidden rounded-full bg-ink-700", className)} role="progressbar" aria-valuenow={value} aria-valuemax={max}>
      <div className={cn("h-full rounded-full transition-[width] duration-700 ease-out", fill)} style={{ width: `${Math.min(100, (value / max) * 100)}%` }} />
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <span className={cn("inline-block size-3.5 animate-spin rounded-full border-2 border-current border-r-transparent", className)} aria-hidden />;
}
