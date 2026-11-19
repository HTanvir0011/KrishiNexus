import { Columns2, Gavel, Landmark, LayoutDashboard, LogOut, Scale, ShieldCheck, Smartphone, Snowflake, Truck, type LucideIcon } from "lucide-react";
import { useLayoutEffect, useRef, useState } from "react";

import { cn } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { Badge, Button } from "../components/ui";
import { homeOf, ROLE_LABEL, ROLE_TONE, ROLE_VIEWS } from "../lib/roles";
import { Link, navigate, type OsView } from "../lib/router";
import { BankDesk } from "../pages/BankDesk";
import { BuyerBankPortal } from "../pages/BuyerBankPortal";
import { CommandCenter } from "../pages/CommandCenter";
import { CoopDesk } from "../pages/CoopDesk";
import { FarmerZeroUIApp } from "../pages/FarmerZeroUIApp";
import { DriverSeat } from "../pages/DriverSeat";
import { HimagarConsole } from "../pages/HimagarConsole";
import { MarketplaceSeat } from "../pages/MarketplaceSeat";
import { logout, useAppState } from "../state/store";

const VIEWS: { view: OsView; to: string; icon: LucideIcon }[] = [
  { view: "judge", to: "/os", icon: Columns2 },
  { view: "field", to: "/os/field", icon: Smartphone },
  { view: "coop", to: "/os/coop", icon: LayoutDashboard },
  { view: "himagar", to: "/os/himagar", icon: Snowflake },
  { view: "trade", to: "/os/trade", icon: Gavel },
  { view: "driver", to: "/os/driver", icon: Truck },
  { view: "market", to: "/os/market", icon: Landmark },
  { view: "bank", to: "/os/bank", icon: Scale },
];

const COPY = {
  en: {
    title: "Live operations workspace",
    lede: "One backend, seven seats: the farmer's phone, the co-op desk, the himagar (cold storage), the direct market, the truck driver, and the buyer and bank desk. An action in one updates the others.",
    views: { judge: "Split-screen judge mode", field: "Farmer mobile companion", coop: "Co-op and cold-chain command", himagar: "Himagar OS (cold storage)", trade: "Direct market (lots and bids)", driver: "Truck driver", market: "B2B market and credit", bank: "Bank desk (payments and disputes)" },
    welcome: (name: string) => `Welcome, ${name}`,
    admin: "Admin panel",
    logout: "Log out",
    notAllowed: "This seat is not part of your role's workspace.",
    toHome: "Go to my workspace",
  },
  bn: {
    title: "লাইভ অপারেশনস ওয়ার্কস্পেস",
    lede: "একই ব্যাকএন্ড, সাতটি আসন: কৃষকের ফোন, সমবায় ডেস্ক, হিমাগার, সরাসরি বাজার, ট্রাকচালক, আর ক্রেতা ও ব্যাংক ডেস্ক। এক জায়গার কাজ অন্যগুলোতেও দেখা যায়।",
    views: { judge: "বিচারক স্প্লিট-স্ক্রিন", field: "কৃষকের মোবাইল", coop: "সমবায় ও কোল্ড চেইন", himagar: "হিমাগার ওএস", trade: "সরাসরি বাজার (লট ও দর)", driver: "ট্রাক চালক", market: "বাজার ও ঋণ", bank: "ব্যাংক ডেস্ক (লেনদেন ও অভিযোগ)" },
    welcome: (name: string) => `স্বাগতম, ${name}`,
    admin: "অ্যাডমিন প্যানেল",
    logout: "লগআউট",
    notAllowed: "এই আসনটি আপনার ভূমিকার কাজের জায়গায় নেই।",
    toHome: "আমার কাজের জায়গা",
  },
};

/** Where the current tab sits inside its row, measured before paint and again whenever the row resizes (fonts, language). */
function useActiveTab(view: OsView) {
  const row = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState<{ left: number; width: number } | null>(null);
  useLayoutEffect(() => {
    const el = row.current;
    if (!el) return;
    const measure = () => {
      const tab = el.querySelector<HTMLElement>('[aria-current="page"]');
      setBox(tab ? { left: tab.offsetLeft, width: tab.offsetWidth } : null);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [view]);
  return { row, box };
}

/** The live workspace for the logged-in account: only the seats its role may open (lib/roles.ts). */
export function OsPage({ view }: { view: OsView }) {
  const c = useCopy(COPY);
  const lang = useAppState((s) => s.lang);
  const user = useAppState((s) => s.user);
  const { row, box } = useActiveTab(view);
  if (!user) return null;
  const allowed = ROLE_VIEWS[user.role];
  const views = VIEWS.filter((v) => allowed.includes(v.view));
  return (
    <main className="mx-auto max-w-[1440px] px-4 pt-6 pb-16 sm:px-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="m-0 text-[24px] font-semibold tracking-[-0.02em] text-slate-900">{c.title}</h1>
          <p className="m-0 mt-1 max-w-[52rem] text-[14px] text-slate-600">{c.lede}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[14px] text-slate-700">{c.welcome(user.name)}</span>
          <Badge tone={ROLE_TONE[user.role]}>{ROLE_LABEL[lang][user.role]}{user.district ? ` · ${user.district}` : ""}</Badge>
          {user.role === "admin" && (
            <Link to="/admin" className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-[14px] font-medium text-slate-700 no-underline hover:bg-slate-100">
              <ShieldCheck className="size-4" aria-hidden /> {c.admin}
            </Link>
          )}
          <Button variant="quiet" onClick={() => { logout(); navigate("/"); }}><LogOut className="size-4" aria-hidden /> {c.logout}</Button>
        </div>
      </div>
      <nav aria-label="Workspace views" className="scroll-thin mt-4 -mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
        <div ref={row} className="relative inline-flex gap-1 rounded-lg bg-slate-100 p-0.5 ring-1 ring-inset ring-slate-200">
          {box && (
            <span aria-hidden className="absolute top-0.5 bottom-0.5 left-0 rounded-md bg-white shadow-sm ring-1 ring-slate-200 transition-[transform,width] duration-300 ease-(--ease-out-expo)"
              style={{ width: box.width, transform: `translateX(${box.left}px)` }} />
          )}
          {views.map((v) => (
            <Link key={v.view} to={v.to} aria-current={view === v.view ? "page" : undefined}
              className={cn("relative flex min-h-9 shrink-0 items-center gap-2 rounded-md px-3.5 text-[14px] font-medium whitespace-nowrap no-underline transition-colors max-sm:min-h-10",
                view === v.view ? "text-slate-900" : "text-slate-600 hover:text-slate-900")}>
              <v.icon className="size-4" aria-hidden /> {c.views[v.view]}
            </Link>
          ))}
        </div>
      </nav>

      {/* Each seat fades in when you switch to it; the tab pill above carries the movement. */}
      <div key={view} className="mt-5 animate-fade-in">
        {!allowed.includes(view) && (
          <p className="m-0 rounded-xl bg-slate-50 p-4 text-[14px] text-slate-700 ring-1 ring-inset ring-slate-200">
            {c.notAllowed} <Link to={homeOf(user.role)} className="font-semibold text-emerald-700">{c.toHome}</Link>
          </p>
        )}
        {allowed.includes(view) && view === "judge" && (
          <div className="grid gap-5 lg:grid-cols-12">
            <FarmerZeroUIApp className="lg:sticky lg:top-[84px] lg:col-span-5 lg:max-h-[calc(100vh-100px)] xl:col-span-4 [&>div]:lg:max-h-[calc(100vh-100px)]" />
            <CommandCenter className="lg:col-span-7 xl:col-span-8" />
          </div>
        )}
        {allowed.includes(view) && view === "field" && <FarmerZeroUIApp className="mx-auto max-w-[440px]" />}
        {allowed.includes(view) && view === "coop" && <CoopDesk />}
        {allowed.includes(view) && view === "himagar" && <HimagarConsole />}
        {allowed.includes(view) && view === "trade" && <MarketplaceSeat />}
        {allowed.includes(view) && view === "driver" && <DriverSeat />}
        {allowed.includes(view) && view === "market" && <BuyerBankPortal />}
        {allowed.includes(view) && view === "bank" && <BankDesk />}
      </div>
    </main>
  );
}

export default OsPage;
