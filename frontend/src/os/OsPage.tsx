import { Columns2, Landmark, LayoutDashboard, Smartphone, type LucideIcon } from "lucide-react";

import { Backdrop } from "../components/shell/Backdrop";
import { TopBar } from "../components/shell/TopBar";
import { cn } from "../lib/format";
import { Link, type OsView } from "../lib/router";
import { BuyerBankPortal } from "../pages/BuyerBankPortal";
import { CommandCenter } from "../pages/CommandCenter";
import { FarmerZeroUIApp } from "../pages/FarmerZeroUIApp";

const VIEWS: { view: OsView; to: string; label: string; icon: LucideIcon }[] = [
  { view: "judge", to: "/os", label: "Judge mode", icon: Columns2 },
  { view: "field", to: "/os/field", label: "Farmer's phone", icon: Smartphone },
  { view: "coop", to: "/os/coop", label: "Co-op and cold storage", icon: LayoutDashboard },
  { view: "market", to: "/os/market", label: "Market and credit", icon: Landmark },
];

export function OsPage({ view }: { view: OsView }) {
  return (
    <div className="relative min-h-screen">
      <Backdrop />
      <div className="relative z-10">
        <TopBar />
        <div className="px-4 pt-5 pb-12 sm:px-8 lg:px-12">
          <nav aria-label="Live OS views" className="panel mb-5 flex w-fit max-w-full gap-1 overflow-x-auto rounded-full p-1">
            {VIEWS.map((v) => (
              <Link key={v.view} to={v.to} aria-current={view === v.view ? "page" : undefined}
                className={cn("flex min-h-10 shrink-0 items-center gap-2 rounded-full px-4 text-[15px] whitespace-nowrap no-underline transition-colors",
                  view === v.view ? "bg-slate-50 font-semibold text-ink-900" : "text-slate-300 hover:text-slate-50")}>
                <v.icon className="size-4" aria-hidden /> {v.label}
              </Link>
            ))}
          </nav>
          {view === "judge" && (
            <div className="grid gap-4 xl:grid-cols-[minmax(360px,32%)_1fr]">
              <FarmerZeroUIApp className="xl:sticky xl:top-24 xl:max-h-[calc(100vh-7.5rem)]" />
              <CommandCenter />
            </div>
          )}
          {view === "field" && <FarmerZeroUIApp className="mx-auto max-w-md" />}
          {view === "coop" && <CommandCenter />}
          {view === "market" && <BuyerBankPortal />}
        </div>
      </div>
    </div>
  );
}

export default OsPage;
