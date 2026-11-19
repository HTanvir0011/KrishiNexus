import { ArrowRight, LogOut, Wifi, WifiOff } from "lucide-react";

import { useCopy } from "../lib/i18n";
import { cn } from "../lib/format";
import { homeOf } from "../lib/roles";
import { Link, navigate, routeOf, useLocation } from "../lib/router";
import { logout, setState, useAppState } from "../state/store";
import { Segmented } from "./ui";

const COPY = {
  en: {
    links: { story: "Overview", os: "My workspace", docs: "Whitepaper", login: "Log in" },
    online: "Online",
    offline: "Offline edge",
    cta: "Log in",
    logout: "Log out",
    connecting: "Connecting to the backend",
    down: "Backend offline · cached demo",
    status: (servers: number, tools: number) => `${servers} MCP servers online · ${tools} tools · BDT UTC+6`,
    network: "Network",
  },
  bn: {
    links: { story: "সারসংক্ষেপ", os: "আমার কাজের জায়গা", docs: "শ্বেতপত্র", login: "লগইন" },
    online: "অনলাইন",
    offline: "অফলাইন এজ",
    cta: "লগইন",
    logout: "লগআউট",
    connecting: "ব্যাকএন্ডে সংযোগ হচ্ছে",
    down: "ব্যাকএন্ড বন্ধ · সংরক্ষিত ডেমো",
    status: (servers: number, tools: number) => `${servers}টি এমসিপি সার্ভার চালু · ${tools}টি টুল · BDT UTC+6`,
    network: "নেটওয়ার্ক",
  },
};


export function Wordmark() {
  return (
    <Link to="/" className="flex shrink-0 items-center gap-2 text-slate-900 no-underline" aria-label="KrishiNexus OS, overview">
      <svg viewBox="0 0 24 24" className="size-6" aria-hidden>
        <rect x="2" y="2" width="20" height="20" rx="5" fill="#047857" />
        <rect x="6" y="6" width="5" height="12" rx="1.2" fill="#ecfdf5" />
        <rect x="13" y="6" width="5" height="5" rx="1.2" fill="#fbbf24" />
        <rect x="13" y="13" width="5" height="5" rx="1.2" fill="#7dd3fc" />
      </svg>
      <span className="text-[16px] font-semibold tracking-[-0.01em]">KrishiNexus <span className="text-emerald-700">OS</span></span>
    </Link>
  );
}

function StatusPill() {
  const c = useCopy(COPY);
  const live = useAppState((s) => s.backendLive);
  const health = useAppState((s) => s.health);
  const text = health && live ? c.status(health.mcpServers, health.tools) : live === false ? c.down : c.connecting;
  return (
    <span className={cn("hidden min-w-0 items-center gap-2 rounded-full px-2.5 py-1 text-[12px] font-medium ring-1 ring-inset xl:inline-flex",
      live ? "bg-emerald-50 text-emerald-800 ring-emerald-700/15" : live === false ? "bg-amber-100 text-amber-800 ring-amber-600/20" : "bg-slate-100 text-slate-600 ring-slate-300")}>
      <span className={cn("size-1.5 shrink-0 rounded-full", live ? "animate-pulse-soft bg-emerald-600" : live === false ? "bg-amber-500" : "bg-slate-400")} />
      <span className="truncate">{text}</span>
    </span>
  );
}

/** Sticky glass navigation for every page: brand + status, the three routes, language, network blackout and the judge CTA. */
export function Navbar() {
  const c = useCopy(COPY);
  const route = routeOf(useLocation());
  const lang = useAppState((s) => s.lang);
  const offline = useAppState((s) => s.offlineMode);
  const live = useAppState((s) => s.backendLive);
  const user = useAppState((s) => s.user);
  // The middle link is the account's own workspace once logged in, the login page before.
  const links = [
    { to: "/", label: c.links.story, current: route.page === "story" },
    user
      ? { to: homeOf(user.role), label: c.links.os, current: route.page === "os" || route.page === "admin" }
      : { to: "/login", label: c.links.login, current: route.page === "login" },
    { to: "/docs", label: c.links.docs, current: route.page === "docs" },
  ];

  const active = links.findIndex((link) => link.current);
  // The three columns are equal, so the white pill slides by whole columns when the route changes.
  const switcher = (className: string) => (
    <nav aria-label="Main" className={cn("relative rounded-lg bg-slate-100 p-0.5 ring-1 ring-inset ring-slate-200", className)}>
      {active >= 0 && (
        <span aria-hidden className="absolute top-0.5 bottom-0.5 left-0.5 rounded-md bg-white shadow-sm ring-1 ring-slate-200 transition-transform duration-300 ease-(--ease-out-expo)"
          style={{ width: `calc((100% - 4px) / ${links.length})`, transform: `translateX(${active * 100}%)` }} />
      )}
      {links.map((link) => (
        <Link key={link.label} to={link.to} aria-current={link.current ? "page" : undefined}
          className={cn("relative flex min-h-8 items-center justify-center rounded-md px-3.5 text-[14px] font-medium whitespace-nowrap no-underline transition-colors max-sm:min-h-10",
            link.current ? "text-slate-900" : "text-slate-600 hover:text-slate-900")}>
          {link.label}
        </Link>
      ))}
    </nav>
  );

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/75 backdrop-blur-md">
      <div className="mx-auto flex max-w-[1440px] items-center gap-3 px-4 py-3 sm:px-6 lg:gap-5">
        <Wordmark />
        <StatusPill />
        {live === false && <span className="size-2 shrink-0 rounded-full bg-amber-500 xl:hidden" title={c.down} />}
        {switcher("mx-auto hidden grid-cols-3 sm:grid")}
        <div className="ml-auto flex shrink-0 items-center gap-2 sm:ml-0">
          <Segmented label="Language" value={lang} onChange={(value) => setState({ lang: value })}
            options={[{ value: "bn", label: <span lang="bn">বাং</span> }, { value: "en", label: "EN" }]} />
          <Segmented label={c.network} value={offline ? "offline" : "online"} onChange={(value) => setState({ offlineMode: value === "offline" })}
            className={cn(offline && "bg-amber-100 ring-amber-600/25")}
            options={[
              { value: "online", label: <><Wifi className="size-3.5" aria-hidden /><span className="hidden md:inline">{c.online}</span></> },
              { value: "offline", label: <><WifiOff className="size-3.5" aria-hidden /><span className="hidden md:inline">{c.offline}</span></> },
            ]} />
          {user ? (
            <button type="button" onClick={() => { logout(); navigate("/"); }} title={user.name}
              className="hidden min-h-9 items-center gap-1.5 rounded-lg px-3 text-[14px] font-medium text-slate-700 ring-1 ring-inset ring-slate-300 transition-colors hover:bg-slate-50 lg:inline-flex">
              <span className="max-w-[10rem] truncate">{user.name}</span> <LogOut className="size-4" aria-hidden />
              <span className="sr-only">{c.logout}</span>
            </button>
          ) : (
            <Link to="/login" className="hidden min-h-9 items-center gap-1.5 rounded-lg bg-emerald-700 px-3.5 text-[14px] font-semibold text-white no-underline shadow-sm transition-colors hover:bg-emerald-800 lg:inline-flex">
              {c.cta} <ArrowRight className="size-4" aria-hidden />
            </Link>
          )}
        </div>
      </div>
      <div className="px-4 pb-2.5 sm:hidden">{switcher("grid grid-cols-3")}</div>
    </header>
  );
}
