import { Radio } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "../lib/format";

/** Semantic tones (Design System v2): emerald growth, amber action/quota, red = rose danger, sky cold chain, violet agents. */
export type Tone = "emerald" | "amber" | "red" | "sky" | "violet" | "slate";

const BADGE_LIGHT: Record<Tone, string> = {
  emerald: "bg-emerald-50 text-emerald-800 ring-emerald-700/20",
  amber: "bg-amber-100 text-amber-800 ring-amber-600/25",
  red: "bg-rose-100 text-rose-700 ring-rose-600/20",
  sky: "bg-sky-50 text-sky-800 ring-sky-600/20",
  violet: "bg-violet-50 text-violet-700 ring-violet-600/20",
  slate: "bg-slate-100 text-slate-700 ring-slate-500/15",
};

const BADGE_DARK: Record<Tone, string> = {
  emerald: "bg-emerald-400/10 text-emerald-300 ring-emerald-400/25",
  amber: "bg-amber-400/10 text-amber-300 ring-amber-400/25",
  red: "bg-rose-400/10 text-rose-300 ring-rose-400/30",
  sky: "bg-sky-400/10 text-sky-300 ring-sky-400/25",
  violet: "bg-violet-400/10 text-violet-300 ring-violet-400/25",
  slate: "bg-white/5 text-slate-300 ring-white/10",
};

export function Badge({ tone = "slate", dark = false, className, children }: {
  tone?: Tone;
  /** Inside an obsidian well. */
  dark?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[12px] font-medium whitespace-nowrap ring-1 ring-inset",
      (dark ? BADGE_DARK : BADGE_LIGHT)[tone], className)}>
      {children}
    </span>
  );
}

export function Panel({ title, icon, actions, well = false, className, bodyClassName, children }: {
  title?: ReactNode;
  icon?: ReactNode;
  actions?: ReactNode;
  /** Obsidian telemetry well instead of a white card. */
  well?: boolean;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}) {
  return (
    <section className={cn(well ? "well" : "surface", "flex min-h-0 min-w-0 flex-col", className)}>
      {(title || actions) && (
        <header className={cn("flex flex-wrap items-center justify-between gap-2 border-b px-4 py-3", well ? "border-white/10" : "border-slate-200")}>
          <h2 className={cn("m-0 flex min-w-0 items-center gap-2 text-[14px] font-semibold", well ? "text-slate-100" : "text-slate-900")}>
            {icon}
            <span className="truncate">{title}</span>
          </h2>
          {actions && <div className="flex min-w-0 max-w-full flex-wrap items-center gap-1.5">{actions}</div>}
        </header>
      )}
      <div className={cn("min-h-0 flex-1 p-4", bodyClassName)}>{children}</div>
    </section>
  );
}

const BUTTON_VARIANTS = {
  primary: "bg-emerald-700 text-white shadow-sm hover:bg-emerald-800 disabled:bg-emerald-700/45",
  amber: "bg-amber-600 text-white shadow-sm hover:bg-amber-700 disabled:bg-amber-600/45",
  danger: "bg-rose-600 text-white shadow-sm hover:bg-rose-700 disabled:bg-rose-600/45",
  ghost: "bg-white text-slate-800 ring-1 ring-slate-300 ring-inset hover:bg-slate-50 disabled:text-slate-400",
  quiet: "text-slate-700 hover:bg-slate-100 disabled:text-slate-400",
} as const;

export function Button({ variant = "ghost", className, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof BUTTON_VARIANTS;
}) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex min-h-9 items-center justify-center gap-1.5 rounded-lg px-3.5 text-[14px] font-semibold transition-colors max-sm:min-h-11",
        "disabled:cursor-not-allowed",
        BUTTON_VARIANTS[variant],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

const VALUE_TONE: Record<Tone, string> = {
  emerald: "text-emerald-700", amber: "text-amber-700", red: "text-rose-600", sky: "text-sky-700", violet: "text-violet-700", slate: "text-slate-900",
};

export function Stat({ label, value, hint, tone = "slate" }: { label: string; value: ReactNode; hint?: ReactNode; tone?: Tone }) {
  return (
    <div className="min-w-0">
      <div className="truncate text-[12.5px] text-slate-500">{label}</div>
      <div className={cn("num truncate text-[22px] leading-tight", VALUE_TONE[tone])}>{value}</div>
      {hint && <div className="line-clamp-2 text-[12px] text-slate-500">{hint}</div>}
    </div>
  );
}

const FILL: Record<Tone, string> = {
  emerald: "bg-emerald-600", amber: "bg-amber-500", red: "bg-rose-600", sky: "bg-sky-600", violet: "bg-violet-600", slate: "bg-slate-500",
};

export function ProgressBar({ value, max, tone = "emerald", className }: { value: number; max: number; tone?: Tone; className?: string }) {
  return (
    <div className={cn("h-2 w-full overflow-hidden rounded-full bg-slate-100", className)} role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={max}>
      <div className={cn("h-full rounded-full transition-[width] duration-700 ease-out", FILL[tone])} style={{ width: `${Math.min(100, (value / max) * 100)}%` }} />
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <span className={cn("inline-block size-3.5 animate-spin rounded-full border-2 border-current border-r-transparent", className)} aria-hidden />;
}

/** Where a figure came from: the live MCP tool (with its round trip) or the dated cached snapshot. */
export function SourceChip({ status, tool, ms, className }: {
  status: "loading" | "live" | "cached";
  tool?: string;
  ms?: number | null;
  className?: string;
}) {
  return (
    <span className={cn("inline-flex min-w-0 items-center gap-1.5 text-[12px] text-slate-500", className)}>
      <span className={cn("size-1.5 shrink-0 rounded-full",
        status === "live" ? "bg-emerald-600" : status === "cached" ? "bg-amber-500" : "animate-pulse-soft bg-slate-400")} />
      <span className="shrink-0">{status === "live" ? "Live" : status === "cached" ? "Cached snapshot" : "Calling"}</span>
      {tool && <span className="truncate font-mono text-[11px] text-slate-600">{tool}</span>}
      {status === "live" && ms !== undefined && ms !== null && <span className="shrink-0 tabular-nums">{Math.round(ms)} ms</span>}
    </span>
  );
}

/** A small radio group drawn as a segmented control. */
export function Segmented<T extends string>({ value, options, onChange, label, className }: {
  value: T;
  options: { value: T; label: ReactNode }[];
  onChange: (value: T) => void;
  label: string;
  className?: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className={cn("inline-flex max-w-full rounded-lg bg-slate-100 p-0.5 ring-1 ring-slate-200 ring-inset", className)}>
      {options.map((option) => (
        <button key={option.value} type="button" role="radio" aria-checked={value === option.value} onClick={() => onChange(option.value)}
          className={cn("inline-flex min-h-8 min-w-0 items-center justify-center gap-1.5 rounded-md px-3 text-[13px] font-medium transition-colors max-sm:min-h-10",
            value === option.value ? "bg-white text-slate-900 shadow-sm ring-1 ring-slate-200" : "text-slate-600 hover:text-slate-900")}>
          {option.label}
        </button>
      ))}
    </div>
  );
}

/** Live WebSocket indicator used by trace views. */
export function LiveDot({ status }: { status: "connecting" | "open" | "closed" }) {
  return (
    <span className={cn("inline-flex items-center gap-1 text-[12px] font-medium",
      status === "open" ? "text-emerald-400" : status === "connecting" ? "text-amber-300" : "text-rose-300")}>
      <Radio className={cn("size-3", status === "open" && "animate-pulse-soft")} aria-hidden /> ws/agent-trace {status}
    </span>
  );
}
