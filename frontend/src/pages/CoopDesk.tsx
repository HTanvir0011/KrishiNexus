import { Lock, PackagePlus, Route, Truck, Users } from "lucide-react";
import { useState, type FormEvent } from "react";

import { api, ApiError, type LotGrade, type PoolView } from "../api/client";
import { TruckPoolMap } from "../components/TruckPoolMap";
import { Badge, Button, Panel, Spinner, Stat } from "../components/ui";
import { cn, kg, tk } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { pushAlert, refreshPools, setState, useAppState } from "../state/store";

const COPY = {
  en: {
    howTitle: "How the co-op works",
    how: [
      ["Gather small lots", "Members bring 200-600 kg each; alone, none can afford a truck to Dhaka."],
      ["Fill a 5-ton truck", "Lots of the same crop in one union share one truck; the pool fills to 5,000 kg."],
      ["Dispatch to the best buyer", "A full truck goes straight to the buyer, with the payment locked in escrow."],
      ["Watch the road", "The driver's load temperature is checked; a load at risk is rerouted to a nearer buyer."],
    ],
    stats: { pooled: "Pooled in trucks", farmers: "Member farmers", trucks: "Trucks dispatched", quota: "Open cold-store quota" },
    hints: { pooled: (n: number) => `${n} pools`, farmers: "lots in the pools", trucks: "escrow-locked 5-ton loads", quota: (d: string) => `within 60 km of ${d}` },
    board: "Truck pools", pick: "Pick a pool to see its members on the map and add a lot.",
    forming: "Forming", dispatched: "Dispatched", toFill: (k: string) => `${k} to fill`, members: (n: number, of: number) => `${n} of ${of} union farmers`,
    grades: "Grades", buyer: "Buyer", contract: "Contract", escrow: "Escrow", eta: (h: number) => `about ${h} h`, rerouted: (from: string) => `rerouted from ${from}`,
    addTitle: "Add a member's lot", farmer: "Farmer ID", weight: "Kilograms", grade: "Grade", add: "Add to the truck",
    added: "Lot added", full: "Truck full: dispatched", pickFirst: "Pick a forming pool first.",
    failed: "Request failed",
  },
  bn: {
    howTitle: "সমবায় কীভাবে কাজ করে",
    how: [
      ["ছোট লট জড়ো করা", "সদস্যরা ২০০-৬০০ কেজি করে আনেন; একা কেউ ঢাকার ট্রাক ভাড়া করতে পারেন না।"],
      ["৫ টনের ট্রাক ভরানো", "এক ইউনিয়নের একই ফসলের লট এক ট্রাকে যায়; পুল ৫,০০০ কেজি পর্যন্ত ভরে।"],
      ["সেরা ক্রেতার কাছে পাঠানো", "ভরা ট্রাক সরাসরি ক্রেতার কাছে যায়, টাকা এসক্রোতে আটকে থাকে।"],
      ["পথে নজর রাখা", "চালকের দেওয়া তাপমাত্রা যাচাই হয়; ঝুঁকিতে থাকলে কাছের ক্রেতার দিকে ঘুরিয়ে দেওয়া হয়।"],
    ],
    stats: { pooled: "ট্রাকে জমা", farmers: "সদস্য কৃষক", trucks: "পাঠানো ট্রাক", quota: "হিমাগারে খালি কোটা" },
    hints: { pooled: (n: number) => `${n}টি পুল`, farmers: "পুলে থাকা লট", trucks: "এসক্রো-লক করা ৫ টনের লোড", quota: (d: string) => `${d}-এর ৬০ কিমির মধ্যে` },
    board: "ট্রাক পুল", pick: "পুল বেছে নিন: মানচিত্রে সদস্যরা দেখা যাবে, লটও যোগ করা যাবে।",
    forming: "ভরছে", dispatched: "রওনা দিয়েছে", toFill: (k: string) => `আরও ${k} লাগবে`, members: (n: number, of: number) => `ইউনিয়নের ${of} জনের ${n} জন`,
    grades: "গ্রেড", buyer: "ক্রেতা", contract: "চুক্তি", escrow: "এসক্রো", eta: (h: number) => `প্রায় ${h} ঘণ্টা`, rerouted: (from: string) => `${from} থেকে ঘুরিয়ে দেওয়া`,
    addTitle: "সদস্যের লট যোগ করুন", farmer: "কৃষকের আইডি", weight: "কেজি", grade: "গ্রেড", add: "ট্রাকে যোগ করুন",
    added: "লট যোগ হয়েছে", full: "ট্রাক ভরে গেছে: রওনা দিয়েছে", pickFirst: "আগে একটি ভরতে থাকা পুল বাছুন।",
    failed: "অনুরোধ ব্যর্থ",
  },
};

const FIELD = "min-h-10 w-full rounded-lg bg-white px-3 text-[14px] text-slate-900 ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-emerald-700 focus:outline-none";
const HOW_ICON = [Users, PackagePlus, Lock, Route];
const message = (error: unknown) => (error instanceof ApiError ? error.message : String(error));

/** The co-op's own seat: members' small lots pooled into shared 5-ton trucks, dispatched with escrow and watched on the road. */
export function CoopDesk() {
  const c = useCopy(COPY);
  const pools = useAppState((s) => s.pools);
  const quota = useAppState((s) => s.quota);
  const focusId = useAppState((s) => s.focusPoolId);
  const pool = pools.find((p) => p.pool_id === focusId) ?? pools[0];
  const pooled = pools.reduce((sum, p) => sum + p.loaded_kg, 0);
  const farmers = pools.reduce((sum, p) => sum + p.smallholders, 0);
  const dispatched = pools.filter((p) => p.status === "DISPATCHED").length;

  return (
    <div className="grid gap-4">
      <section className="surface p-4" aria-labelledby="coop-how">
        <h2 id="coop-how" className="m-0 text-[15px] font-semibold text-slate-900">{c.howTitle}</h2>
        <ol className="m-0 mt-3 grid list-none gap-3 p-0 sm:grid-cols-2 xl:grid-cols-4">
          {c.how.map(([title, text], i) => {
            const Icon = HOW_ICON[i];
            return (
              <li key={title} className="flex gap-2.5">
                <span className="relative grid size-8 shrink-0 place-items-center rounded-lg bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-700/15">
                  <Icon className="size-4" aria-hidden />
                  <span className="num absolute -top-1.5 -right-1.5 grid size-4 place-items-center rounded-full bg-emerald-700 text-[10px] text-white">{i + 1}</span>
                </span>
                <span className="min-w-0">
                  <span className="block text-[13.5px] font-semibold text-slate-900">{title}</span>
                  <span className="block text-[12.5px] text-slate-600">{text}</span>
                </span>
              </li>
            );
          })}
        </ol>
      </section>

      <section className="surface grid grid-cols-2 gap-4 p-4 md:grid-cols-4" aria-label="Co-op summary">
        <Stat label={c.stats.pooled} value={kg(pooled)} hint={c.hints.pooled(pools.length)} tone="emerald" />
        <Stat label={c.stats.farmers} value={farmers} hint={c.hints.farmers} />
        <Stat label={c.stats.trucks} value={dispatched} hint={c.hints.trucks} tone="amber" />
        <Stat label={c.stats.quota} value={quota ? `${Math.round(quota.total_open_smallholder_quota_mt).toLocaleString("en-IN")} t` : "-"}
          hint={quota ? c.hints.quota(quota.district) : undefined} tone="sky" />
      </section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <Panel title={`${c.board} (${pools.length})`} icon={<Truck className="size-4 text-emerald-700" aria-hidden />}>
          <p className="m-0 mb-3 text-[13px] text-slate-600">{c.pick}</p>
          {pools.length === 0 ? <Spinner /> : (
            <div className="grid gap-3 md:grid-cols-2">
              {pools.map((p) => <PoolCard key={p.pool_id} p={p} selected={p.pool_id === pool?.pool_id} />)}
            </div>
          )}
        </Panel>
        <div className="grid content-start gap-4">
          <TruckPoolMap />
          {/* A dispatched pool's road check lives in the map panel above (its truck temperature form). */}
          {pool?.status === "OPEN" && <AddLot pool={pool} />}
        </div>
      </div>
    </div>
  );
}

function PoolCard({ p, selected }: { p: PoolView; selected: boolean }) {
  const c = useCopy(COPY);
  const grades = (["A", "B", "C"] as LotGrade[]).map((g) => [g, p.lots.filter((l) => l.grade === g).length] as const);
  return (
    <button type="button" onClick={() => setState({ focusPoolId: p.pool_id })} aria-pressed={selected}
      className={cn("grid gap-2 rounded-xl bg-white p-3 text-left ring-1 ring-inset transition-colors",
        selected ? "bg-emerald-50/50 ring-2 ring-emerald-700" : "ring-slate-200 hover:bg-slate-50")}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-[14.5px] font-semibold text-slate-900">{p.union}</div>
          <div className="truncate text-[12.5px] text-slate-600">{p.upazila}, {p.district} · {p.crop}</div>
        </div>
        <Badge tone={p.status === "DISPATCHED" ? "amber" : "emerald"}>{p.status === "DISPATCHED" ? c.dispatched : c.forming}</Badge>
      </div>
      <div>
        <div className="flex items-baseline justify-between text-[12.5px]">
          <span className="num font-semibold text-slate-900">{kg(p.loaded_kg)} / {kg(p.capacity_kg)}</span>
          <span className="text-slate-500">{p.status === "OPEN" ? c.toFill(kg(p.remaining_kg)) : `${Math.round(p.fill_pct)}%`}</span>
        </div>
        <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100">
          <div className={cn("h-full rounded-full transition-[width] duration-700 ease-(--ease-out-expo)", p.status === "DISPATCHED" ? "bg-amber-500" : "bg-emerald-600")}
            style={{ width: `${Math.min(100, p.fill_pct)}%` }} />
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-1.5 text-[12px] text-slate-600">
        <span>{c.members(p.smallholders, p.roster_size)}</span>
        <span aria-hidden>·</span>
        <span>{c.grades}</span>
        {grades.map(([g, n]) => <Badge key={g} tone={g === "A" ? "emerald" : g === "B" ? "amber" : "red"}>{g} {n}</Badge>)}
      </div>
      {p.dispatch && (
        <div className="rounded-lg bg-amber-50/70 px-2.5 py-1.5 text-[12.5px] text-amber-950 ring-1 ring-inset ring-amber-600/20">
          {c.buyer}: <span className="font-semibold">{p.dispatch.buyer_name}</span> · {c.contract} <span className="num font-semibold">{tk(p.dispatch.contract_value_tk, 0)}</span>
          <span className="block">{c.escrow} <span className="font-mono">{p.dispatch.escrow_id}</span> · {c.eta(p.dispatch.eta_hours)}{p.dispatch.rerouted_from ? ` · ${c.rerouted(p.dispatch.rerouted_from)}` : ""}</span>
        </div>
      )}
    </button>
  );
}

function AddLot({ pool }: { pool: PoolView }) {
  const c = useCopy(COPY);
  const code = pool.district.slice(0, 3).toUpperCase();
  const [farmer, setFarmer] = useState(`FARM-${code}-${String(pool.lots.length + 1).padStart(3, "0")}`);
  const [weight, setWeight] = useState(String(Math.min(500, Math.max(50, Math.round(pool.remaining_kg)))));
  const [grade, setGrade] = useState<LotGrade>("A");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await api.joinPool({ cluster_id: pool.pool_id, farmer_id: farmer, crop: pool.crop, weight_kg: Number(weight), grade });
      const full = result.pool.status === "DISPATCHED";
      pushAlert(result.accepted ? "success" : "warn", full ? c.full : c.added, result.message);
      await refreshPools();
      setFarmer(`FARM-${code}-${String(result.pool.lots.length + 1).padStart(3, "0")}`);
    } catch (error) {
      pushAlert("danger", c.failed, message(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title={`${c.addTitle} · ${pool.union}`} icon={<PackagePlus className="size-4 text-emerald-700" aria-hidden />}>
      <form onSubmit={(e) => void submit(e)} className="grid grid-cols-2 gap-3">
        <label className="col-span-2 grid gap-1 text-[13px] font-medium text-slate-700">{c.farmer}
          <input required pattern="[A-Za-z0-9\-]{3,40}" value={farmer} onChange={(e) => setFarmer(e.target.value.toUpperCase())} className={cn(FIELD, "font-mono")} />
        </label>
        <label className="grid gap-1 text-[13px] font-medium text-slate-700">{c.weight}
          <input required type="number" min={10} max={5000} step={10} value={weight} onChange={(e) => setWeight(e.target.value)} className={FIELD} />
        </label>
        <label className="grid gap-1 text-[13px] font-medium text-slate-700">{c.grade}
          <select value={grade} onChange={(e) => setGrade(e.target.value as LotGrade)} className={FIELD}>
            {(["A", "B", "C"] as LotGrade[]).map((g) => <option key={g}>{g}</option>)}
          </select>
        </label>
        <Button variant="primary" type="submit" className="col-span-2 min-h-11" disabled={busy}>
          {busy ? <Spinner /> : <PackagePlus className="size-4" aria-hidden />} {c.add}
        </Button>
      </form>
    </Panel>
  );
}

export default CoopDesk;
