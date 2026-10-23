import { useMemo, type ButtonHTMLAttributes, type CSSProperties, type ReactNode } from "react";

import { bnDigits, cn } from "../lib/format";
import { SNAPSHOT_DATE, type SourceStatus } from "./data";

export function ChapterHeading({ index, children }: { index: number; children: ReactNode }) {
  return (
    <h2 className="mb-6 flex items-baseline gap-4 text-slate-50">
      <span className="text-[30px] leading-none font-medium text-mustard-400" aria-hidden>{bnDigits(index)}</span>
      <span className="wide text-[clamp(30px,3.4vw,46px)] leading-[1.08]">{children}</span>
    </h2>
  );
}

/** Says where a number came from: the live agents, or the dated snapshot when the backend is down. */
export function SourceNote({ status, label, children }: { status: SourceStatus; label?: string; children?: ReactNode }) {
  return (
    <p className="label mt-5 flex flex-wrap items-center gap-2 text-[13px] text-slate-500">
      <span className={cn("size-1.5 rounded-full", status === "live" ? "bg-emerald-400" : status === "cached" ? "bg-amber-400" : "bg-slate-500")} />
      {label ?? (status === "live" ? "Live from the agents" : status === "cached" ? `Backend offline: cached run from ${SNAPSHOT_DATE}` : "Asking the agents")}
      {children && <span className="text-slate-500">{children}</span>}
    </p>
  );
}

type StoryButtonVariant = "primary" | "ghost" | "link";

export function storyButtonClass(variant: StoryButtonVariant = "primary", className?: string): string {
  return cn(
    "inline-flex min-h-12 items-center gap-2.5 rounded-full text-[16px] font-semibold no-underline transition-colors disabled:cursor-not-allowed disabled:opacity-55",
    variant === "primary" && "bg-mustard-400 px-6 text-ink-900 hover:bg-mustard-300",
    variant === "ghost" && "border border-slate-50/30 px-6 text-slate-50 hover:border-slate-50/60",
    variant === "link" && "min-h-11 px-1 font-medium text-slate-400 underline underline-offset-4 hover:text-slate-100",
    className,
  );
}

export function StoryButton({ variant = "primary", className, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: StoryButtonVariant;
}) {
  return (
    <button type="button" className={storyButtonClass(variant, className)} {...props}>
      {children}
    </button>
  );
}

function mulberry32(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** The line the question sits on: one swell per word, drawn from the sentence (an illustration, not audio). */
export function Waveform({ words, className }: { words: number; className?: string }) {
  const { d, length } = useMemo(() => {
    const rand = mulberry32(5 + words);
    const points: string[] = [];
    let len = 0;
    let prev: [number, number] | null = null;
    for (let x = 0; x <= 640; x += 3) {
      const syllable = Math.abs(Math.sin((x / 640) * Math.PI * words));
      const envelope = 0.12 + 0.88 * syllable ** 1.6 * (x < 600 ? 1 : (640 - x) / 40);
      const y = 23 + Math.sin(x / 4.6) * 14 * envelope * (0.75 + rand() * 0.25);
      if (prev) len += Math.hypot(x - prev[0], y - prev[1]);
      prev = [x, y];
      points.push(`${x},${y.toFixed(1)}`);
    }
    return { d: `M${points.join(" L")}`, length: len };
  }, [words]);
  return (
    <svg viewBox="0 0 640 46" className={className} aria-hidden>
      <path d={d} fill="none" stroke="rgb(157 176 163 / 0.28)" strokeWidth={1.5} strokeLinecap="round" />
      <path d={d} fill="none" stroke="rgb(239 235 221 / 0.8)" strokeWidth={1.8} strokeLinecap="round"
        className="story-wave-said" style={{ strokeDasharray: length, "--len": length } as CSSProperties} />
    </svg>
  );
}

export function Anchor({ lat, lon, alt = 0, chapters, alert = false, followTruck = false, children }: {
  lat: number;
  lon: number;
  alt?: number;
  chapters: number[];
  alert?: boolean;
  /** Ride along with the truck instead of staying at lat/lon. */
  followTruck?: boolean;
  children: ReactNode;
}) {
  return (
    <span className={cn("anchor", alert && "is-alert")} data-lat={lat} data-lon={lon} data-alt={alt} data-ch={chapters.join(" ")}
      data-follow={followTruck ? "truck" : undefined}>
      <span>{children}</span>
    </span>
  );
}
