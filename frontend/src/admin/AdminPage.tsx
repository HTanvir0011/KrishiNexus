import { Activity, ArrowRight, LayoutDashboard, LogOut, MessageSquare, MonitorPlay, ShieldCheck, Truck, Users, Wallet, Zap, type LucideIcon } from "lucide-react";

import { api } from "../api/client";
import { Panel, Spinner, Stat } from "../components/ui";
import { cn } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { ROLE_LABEL } from "../lib/roles";
import { Link, navigate, type AdminSection } from "../lib/router";
import { logout, useAppState } from "../state/store";
import { AccountsSection, ROLES } from "./AccountsSection";
import { ActivitySection, AnomaliesSection, EscrowsSection, FeedbackSection, PoolsSection } from "./OperationsSections";
import { useAdmin } from "./useAdmin";

const MENU: { id: AdminSection; to: string; icon: LucideIcon }[] = [
  { id: "overview", to: "/admin", icon: LayoutDashboard },
  { id: "accounts", to: "/admin/accounts", icon: Users },
  { id: "pools", to: "/admin/pools", icon: Truck },
  { id: "escrows", to: "/admin/escrows", icon: Wallet },
  { id: "anomalies", to: "/admin/anomalies", icon: Zap },
  { id: "activity", to: "/admin/activity", icon: Activity },
  { id: "feedback", to: "/admin/feedback", icon: MessageSquare },
];

const COPY = {
  en: {
    title: "Admin panel",
    menu: { overview: "Overview", accounts: "Accounts", pools: "Truck pools", escrows: "Escrows", anomalies: "Anomalies", activity: "Agent activity", feedback: "Feedback" },
    lede: {
      overview: "The platform at a glance. Changes made here apply to every visitor.",
      accounts: "Add, edit, disable and delete demo accounts, or restore the seeded ones.",
      pools: "Every 5-ton union truck pool, its fill and its buyer.",
      escrows: "Bids farmers have locked in one tap, newest first.",
      anomalies: "Power cuts and flash floods injected for the demo; clear them when you are done.",
      activity: "What the agents have been doing.",
      feedback: "How users rate the advice: the evidence a field test collects. Comments are stored with personal details removed.",
    },
    seats: "Open the workspace",
    logout: "Log out",
    activeUsers: "Active accounts",
    pools: "Truck pools",
    lots: (n: number) => `${n} lots pooled`,
    escrows: "Escrows locked",
    anomalies: "Active anomalies",
    traces: "Trace events",
    manage: "Manage",
  },
  bn: {
    title: "অ্যাডমিন প্যানেল",
    menu: { overview: "সারসংক্ষেপ", accounts: "অ্যাকাউন্ট", pools: "ট্রাক পুল", escrows: "এসক্রো", anomalies: "দুর্ঘটনা", activity: "এজেন্ট কার্যক্রম", feedback: "মতামত" },
    lede: {
      overview: "এক নজরে প্ল্যাটফর্ম। এখানের পরিবর্তন সব দর্শকের জন্য।",
      accounts: "ডেমো অ্যাকাউন্ট যোগ, সম্পাদনা, বন্ধ ও মুছুন, বা মূলগুলো ফিরিয়ে আনুন।",
      pools: "প্রতিটি ৫ টনের ইউনিয়ন ট্রাক পুল, ভরাট ও ক্রেতা।",
      escrows: "কৃষকদের এক ট্যাপে লক করা দর, নতুনটি আগে।",
      anomalies: "ডেমোর জন্য চালু করা বিদ্যুৎ বিভ্রাট ও বন্যা; শেষে মুছে দিন।",
      activity: "এজেন্টরা কী করছে।",
      feedback: "ব্যবহারকারীরা পরামর্শকে কেমন বলছেন; ব্যক্তিগত তথ্য বাদ দিয়ে মন্তব্য রাখা হয়।",
    },
    seats: "কাজের জায়গা খুলুন",
    logout: "লগআউট",
    activeUsers: "সক্রিয় অ্যাকাউন্ট",
    pools: "ট্রাক পুল",
    lots: (n: number) => `${n}টি লট`,
    escrows: "এসক্রো লক",
    anomalies: "সক্রিয় দুর্ঘটনা",
    traces: "ট্রেস ইভেন্ট",
    manage: "পরিচালনা",
  },
};

function OverviewSection() {
  const c = useCopy(COPY);
  const lang = useAppState((s) => s.lang);
  const { data: overview } = useAdmin(api.adminOverview);
  if (!overview) return <Spinner />;
  const cards: { id: AdminSection; label: string; value: number; hint?: string; tone: "slate" | "amber" | "emerald" | "red" | "sky" }[] = [
    { id: "accounts", label: c.activeUsers, value: overview.active_users, tone: "slate",
      hint: ROLES.filter((r) => overview.users_by_role[r]).map((r) => `${ROLE_LABEL[lang][r]} ${overview.users_by_role[r]}`).join(" · ") },
    { id: "pools", label: c.pools, value: overview.truck_pools, hint: c.lots(overview.lots_in_pools), tone: "amber" },
    { id: "escrows", label: c.escrows, value: overview.escrows_locked, tone: "emerald" },
    { id: "anomalies", label: c.anomalies, value: overview.active_anomalies, tone: overview.active_anomalies ? "red" : "slate" },
    { id: "activity", label: c.traces, value: overview.trace_events, tone: "sky" },
  ];
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {cards.map((card) => (
        <Panel key={card.id}>
          <Stat label={card.label} value={card.value} hint={card.hint} tone={card.tone} />
          <Link to={MENU.find((m) => m.id === card.id)!.to}
            className="mt-3 inline-flex items-center gap-1 text-[13px] font-semibold text-emerald-700 no-underline hover:text-emerald-800">
            {c.manage} {c.menu[card.id]} <ArrowRight className="size-3.5" aria-hidden />
          </Link>
        </Panel>
      ))}
    </div>
  );
}

/** The admin console: a sidebar menu (a scrolling strip on small screens) and one management page per route. */
export function AdminPage({ section }: { section: AdminSection }) {
  const c = useCopy(COPY);
  const user = useAppState((s) => s.user);

  return (
    <main className="mx-auto max-w-[1440px] px-4 pt-6 pb-16 sm:px-6 lg:grid lg:grid-cols-[232px_minmax(0,1fr)] lg:gap-6">
      <aside className="lg:sticky lg:top-[84px] lg:self-start">
        <div className="mb-3 flex items-center gap-2 px-1">
          <ShieldCheck className="size-5 text-rose-600" aria-hidden />
          <div className="min-w-0">
            <div className="text-[15px] font-semibold text-slate-900">{c.title}</div>
            {user && <div className="truncate text-[12px] text-slate-500">{user.name}</div>}
          </div>
        </div>
        <nav aria-label="Admin" className="scroll-thin -mx-4 overflow-x-auto px-4 lg:mx-0 lg:overflow-visible lg:px-0">
          <ul className="m-0 flex list-none gap-1 p-0 lg:flex-col">
            {MENU.map((item) => (
              <li key={item.id} className="shrink-0">
                <Link to={item.to} aria-current={section === item.id ? "page" : undefined}
                  className={cn("flex min-h-10 items-center gap-2.5 rounded-lg px-3 text-[14px] font-medium whitespace-nowrap no-underline transition-colors",
                    section === item.id ? "bg-white text-slate-900 shadow-sm ring-1 ring-slate-200" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900")}>
                  <item.icon className={cn("size-4", section === item.id ? "text-emerald-700" : "text-slate-400")} aria-hidden />
                  {c.menu[item.id]}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="mt-4 hidden border-t border-slate-200 pt-4 lg:grid lg:gap-1">
          <Link to="/os" className="flex min-h-10 items-center gap-2.5 rounded-lg px-3 text-[14px] font-medium text-slate-600 no-underline hover:bg-slate-100 hover:text-slate-900">
            <MonitorPlay className="size-4 text-slate-400" aria-hidden /> {c.seats}
          </Link>
          <button type="button" onClick={() => { logout(); navigate("/"); }}
            className="flex min-h-10 items-center gap-2.5 rounded-lg px-3 text-left text-[14px] font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900">
            <LogOut className="size-4 text-slate-400" aria-hidden /> {c.logout}
          </button>
        </div>
      </aside>

      <section className="mt-5 min-w-0 lg:mt-0" aria-labelledby="admin-heading">
        <h1 id="admin-heading" className="m-0 text-[24px] font-semibold tracking-[-0.02em] text-slate-900">{c.menu[section]}</h1>
        <p className="m-0 mt-1 mb-5 max-w-[52rem] text-[14px] text-slate-600">{c.lede[section]}</p>
        {section === "overview" && <OverviewSection />}
        {section === "accounts" && <AccountsSection />}
        {section === "pools" && <PoolsSection />}
        {section === "escrows" && <EscrowsSection />}
        {section === "anomalies" && <AnomaliesSection />}
        {section === "activity" && <ActivitySection />}
        {section === "feedback" && <FeedbackSection />}
      </section>
    </main>
  );
}

export default AdminPage;
