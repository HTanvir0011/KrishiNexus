import { useEffect, useState, type Ref } from "react";

import { cn } from "../../lib/format";
import { Link, routeOf, useLocation } from "../../lib/router";
import { useAppState } from "../../state/store";

const BDT_TIME = new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Dhaka", hour: "2-digit", minute: "2-digit" });

function useBdtClock(): string {
  const [now, setNow] = useState(() => BDT_TIME.format(new Date()));
  useEffect(() => {
    const timer = window.setInterval(() => setNow(BDT_TIME.format(new Date())), 20_000);
    return () => window.clearInterval(timer);
  }, []);
  return now;
}

export function Wordmark() {
  return (
    <Link to="/" className="flex items-center gap-2.5 text-slate-50 no-underline" aria-label="KrishiNexus, back to the story">
      <svg viewBox="0 0 24 24" className="size-[22px]" aria-hidden>
        <rect x="3" y="3" width="8" height="18" rx="1.5" fill="#006a4e" />
        <rect x="13" y="3" width="8" height="8" rx="1.5" fill="#edb723" />
        <rect x="13" y="13" width="8" height="8" rx="1.5" fill="#6fa8b5" opacity="0.85" />
      </svg>
      <span className="wide text-[19px] leading-none tracking-[0.01em]">KrishiNexus</span>
    </Link>
  );
}

const LINKS = [
  { to: "/", label: "Story", page: "story" },
  { to: "/os", label: "Live OS", page: "os" },
  { to: "/docs", label: "Whitepaper", page: "docs" },
] as const;

/**
 * Site header. On the story it floats over the landscape and the HUD reports the place the camera is
 * looking at (written straight into `coordsRef` by the landscape, not through React state).
 */
export function TopBar({ overlay = false, coordsRef, coords = "25.57°N 89.28°E" }: {
  overlay?: boolean;
  coordsRef?: Ref<HTMLSpanElement>;
  coords?: string;
}) {
  const route = routeOf(useLocation());
  const live = useAppState((s) => s.backendLive);
  const clock = useBdtClock();

  return (
    <header className={cn(
      "z-30 flex flex-wrap items-center gap-x-8 gap-y-2 px-4 py-3 sm:px-8 lg:px-12",
      // Over the story a fading shade keeps scrolling text from running into the links. On a phone the
      // header scrolls away so the landscape band keeps the top of the screen.
      overlay
        ? "absolute inset-x-0 top-0 md:fixed before:pointer-events-none before:absolute before:inset-x-0 before:top-0 before:-z-10 before:h-[calc(100%+48px)] before:bg-[linear-gradient(180deg,rgb(14_33_26/0.94)_0%,rgb(14_33_26/0.82)_55%,rgb(14_33_26/0)_100%)]"
        : "sticky top-0 border-b border-slate-50/[0.06] bg-ink-900/70 backdrop-blur-md",
    )}>
      <Wordmark />
      <nav aria-label="Main" className="flex gap-1 max-sm:order-1">
        {LINKS.map((link) => (
          <Link key={link.to} to={link.to} aria-current={route.page === link.page ? "page" : undefined}
            className={cn("rounded-full px-3.5 py-1.5 text-[15px] whitespace-nowrap no-underline transition-colors",
              route.page === link.page ? "bg-emerald-600 text-slate-50" : "text-slate-400 hover:text-slate-100")}>
            {link.label}
          </Link>
        ))}
      </nav>
      <div className="label ml-auto flex items-center gap-5 text-[13px] text-slate-400 tabular-nums" aria-label="Status">
        <span className="flex items-center gap-2 whitespace-nowrap text-slate-100">
          <span className={cn("size-2 rounded-full",
            live === null ? "bg-slate-500" : live ? "bg-emerald-500 shadow-[0_0_0_3px_rgb(0_106_78/0.35)]" : "bg-amber-400")} />
          {live === null ? "Connecting" : live ? "Backend live" : "Cached demo"}
        </span>
        {overlay && <span ref={coordsRef} className="hidden whitespace-nowrap sm:inline">{coords}</span>}
        <span className="hidden whitespace-nowrap sm:inline">{clock} BDT</span>
      </div>
    </header>
  );
}
