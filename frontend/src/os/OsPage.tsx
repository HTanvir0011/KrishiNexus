import { Columns2, Landmark, LayoutDashboard, LogOut, ShieldCheck, Smartphone, type LucideIcon } from "lucide-react";

import { cn } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { Badge, Button } from "../components/ui";
import { homeOf, ROLE_LABEL, ROLE_TONE, ROLE_VIEWS } from "../lib/roles";
import { Link, navigate, type OsView } from "../lib/router";
import { BuyerBankPortal } from "../pages/BuyerBankPortal";
import { CommandCenter } from "../pages/CommandCenter";
import { FarmerZeroUIApp } from "../pages/FarmerZeroUIApp";
import { logout, useAppState } from "../state/store";

const VIEWS: { view: OsView; to: string; icon: LucideIcon }[] = [
  { view: "judge", to: "/os", icon: Columns2 },
  { view: "field", to: "/os/field", icon: Smartphone },
  { view: "coop", to: "/os/coop", icon: LayoutDashboard },
  { view: "market", to: "/os/market", icon: Landmark },
];

const COPY = {
  en: {
    title: "Live operations workspace",
    lede: "One backend, four seats: the farmer's phone, the co-op and cold-chain desk, and the buyer and bank desk. An action in one updates the others.",
    views: { judge: "Split-screen judge mode", field: "Farmer mobile companion", coop: "Co-op and cold-chain command", market: "B2B market and bank desk" },
    welcome: (name: string) => `Welcome, ${name}`,
    admin: "Admin panel",
    logout: "Log out",
    notAllowed: "This seat is not part of your role's workspace.",
    toHome: "Go to my workspace",
  },
  bn: {
    title: "লাইভ অপারেশনস ওয়ার্কস্পেস",
    lede: "একই ব্যাকএন্ড, চারটি আসন: কৃষকের ফোন, সমবায় ও কোল্ড-চেইন ডেস্ক, আর ক্রেতা ও ব্যাংক ডেস্ক। এক জায়গার কাজ অন্যগুলোতেও দেখা যায়।",
    views: { judge: "বিচারক স্প্লিট-স্ক্রিন", field: "কৃষকের মোবাইল", coop: "সমবায় ও কোল্ড চেইন", market: "বাজার ও ব্যাংক ডেস্ক" },
    welcome: (name: string) => `স্বাগতম, ${name}`,
    admin: "অ্যাডমিন প্যানেল",
    logout: "লগআউট",
    notAllowed: "এই আসনটি আপনার ভূমিকার কাজের জায়গায় নেই।",
    toHome: "আমার কাজের জায়গা",
  },
};

/** The live workspace for the logged-in account: only the seats its role may open (lib/roles.ts). */
export function OsPage({ view }: { view: OsView }) {
  const c = useCopy(COPY);
  const lang = useAppState((s) => s.lang);
  const user = useAppState((s) => s.user);
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
        <div className="inline-flex gap-1 rounded-lg bg-slate-100 p-0.5 ring-1 ring-inset ring-slate-200">
          {views.map((v) => (
            <Link key={v.view} to={v.to} aria-current={view === v.view ? "page" : undefined}
              className={cn("flex min-h-9 shrink-0 items-center gap-2 rounded-md px-3.5 text-[14px] font-medium whitespace-nowrap no-underline transition-colors max-sm:min-h-10",
                view === v.view ? "bg-white text-slate-900 shadow-sm ring-1 ring-slate-200" : "text-slate-600 hover:text-slate-900")}>
              <v.icon className="size-4" aria-hidden /> {c.views[v.view]}
            </Link>
          ))}
        </div>
      </nav>

      <div className="mt-5">
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
        {allowed.includes(view) && view === "coop" && <CommandCenter />}
        {allowed.includes(view) && view === "market" && <BuyerBankPortal />}
      </div>
    </main>
  );
}

export default OsPage;
