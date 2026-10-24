import { useEffect, useState } from "react";

import { mcpCall } from "../api/client";
import { SourceChip } from "../components/ui";
import { cn, tk } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { RANGPUR_QUOTA_SNAPSHOT, SNAPSHOT_DATE } from "./data";
import { Select } from "./SyndicateCard";
import { useLive } from "./useLive";

/** The parts of `query_cold_storage_quota` output this card renders. */
interface QuotaOut {
  district: string;
  tons_needed: number;
  facilities_found: number;
  total_open_smallholder_quota_mt: number;
  single_facility_fulfilment: boolean;
  recommended_allocation: { facility_id: string; tons: number; all_in_cost_tk: number }[];
  unallocated_tons: number;
  quota_capture: { traders_pct: number; plant_owners_pct: number; farmers_pct: number; non_farmer_capture_pct: number };
  district_gap: { storage_coverage_pct: number; potato_output_mt: number; storage_capacity_mt: number } | null;
  facilities: { facility_id: string; name: string; total_capacity_mt: number; trader_quota_mt: number; owner_quota_mt: number;
    farmer_quota_mt: number; open_smallholder_quota_mt: number; tariff_tk_per_kg: number }[];
}

const DISTRICTS = ["Rangpur", "Bogura", "Munshiganj", "Thakurgaon"];

const COPY = {
  en: {
    title: "Who holds the cold-storage space",
    sub: "BCSA plants within 60 km, live quota",
    district: "District",
    tons: "Co-op needs (t)",
    held: "held by traders and plant owners before a farmer arrives",
    traders: "Traders", owners: "Plant owners", booked: "Farmers, booked", open: "Farmers, still open",
    fits: (t: string, open: string, n: number) => `${t} fits: ${open} is still open to smallholders across ${n} stores.`,
    short: (t: string, open: string, gap: string) => `${t} does not fit: only ${open} is open, ${gap} short.`,
    coverage: (d: string, pct: string) => `${d}'s cold stores hold ${pct} of the district's potato harvest.`,
  },
  bn: {
    title: "হিমাগারের জায়গা কার দখলে",
    sub: "৬০ কিমির মধ্যে বিসিএসএ হিমাগার, লাইভ কোটা",
    district: "জেলা",
    tons: "সমিতির দরকার (টন)",
    held: "কৃষক আসার আগেই ব্যবসায়ী ও মালিকদের দখলে",
    traders: "ব্যবসায়ী", owners: "হিমাগার মালিক", booked: "কৃষক, বুক করা", open: "কৃষক, এখনো খালি",
    fits: (t: string, open: string, n: number) => `${t} জায়গা আছে: ${n}টি হিমাগারে কৃষকের জন্য ${open} খালি।`,
    short: (t: string, open: string, gap: string) => `${t} হবে না: খালি মাত্র ${open}, ঘাটতি ${gap}।`,
    coverage: (d: string, pct: string) => `${d} জেলার হিমাগারে আলুর ফলনের ${pct} রাখা যায়।`,
  },
};

const tonnes = (v: number) => `${Math.round(v).toLocaleString("en-IN")} t`;

/** Offline: the dated Rangpur run, with shares recomputed from its facilities. */
function rangpurSnapshot(tons: number): QuotaOut {
  const f = RANGPUR_QUOTA_SNAPSHOT.facilities;
  const sum = (pick: (x: (typeof f)[number]) => number) => f.reduce((s, x) => s + pick(x), 0);
  const capacity = sum((x) => x.total_capacity_mt);
  const share = (v: number) => (v / capacity) * 100;
  const open = RANGPUR_QUOTA_SNAPSHOT.total_open_smallholder_quota_mt;
  return {
    district: "Rangpur", tons_needed: tons, facilities_found: f.length, total_open_smallholder_quota_mt: open,
    single_facility_fulfilment: f.some((x) => x.open_smallholder_quota_mt >= tons), recommended_allocation: [],
    unallocated_tons: Math.max(0, tons - open),
    quota_capture: {
      traders_pct: share(sum((x) => x.trader_quota_mt)), plant_owners_pct: share(sum((x) => x.owner_quota_mt)),
      farmers_pct: share(sum((x) => x.farmer_quota_mt)), non_farmer_capture_pct: share(sum((x) => x.trader_quota_mt + x.owner_quota_mt)),
    },
    district_gap: null,
    facilities: f,
  };
}

export function QuotaCard({ className }: { className?: string }) {
  const c = useCopy(COPY);
  const [district, setDistrict] = useState("Rangpur");
  const [draft, setDraft] = useState("50");
  const [tons, setTons] = useState(50);

  useEffect(() => {
    const value = Number(draft);
    if (!Number.isFinite(value) || value <= 0 || value > 2000) return;
    const timer = window.setTimeout(() => setTons(value), 400);
    return () => window.clearTimeout(timer);
  }, [draft]);

  const live = useLive<QuotaOut>(
    `${district}|${tons}`,
    () => mcpCall<QuotaOut>("query_cold_storage_quota", { district, radius_km: 60, tons_needed: tons }),
    () => (district === "Rangpur" ? rangpurSnapshot(tons) : null),
  );
  const q = live.data;
  const capacity = q ? q.facilities.reduce((s, f) => s + f.total_capacity_mt, 0) : 0;
  const booked = q ? q.facilities.reduce((s, f) => s + f.farmer_quota_mt - f.open_smallholder_quota_mt, 0) : 0;
  const segments = q
    ? [
        { label: c.traders, pct: q.quota_capture.traders_pct, t: q.facilities.reduce((s, f) => s + f.trader_quota_mt, 0), color: "bg-slate-400" },
        { label: c.owners, pct: q.quota_capture.plant_owners_pct, t: q.facilities.reduce((s, f) => s + f.owner_quota_mt, 0), color: "bg-sky-600" },
        { label: c.booked, pct: (booked / Math.max(1, capacity)) * 100, t: booked, color: "bg-amber-300" },
        { label: c.open, pct: (q.total_open_smallholder_quota_mt / Math.max(1, capacity)) * 100, t: q.total_open_smallholder_quota_mt, color: "bg-amber-600" },
      ]
    : [];
  const names = new Map(q?.facilities.map((f) => [f.facility_id, f.name]) ?? []);
  const fits = q ? q.unallocated_tons <= 0 : false;

  return (
    <article className={cn("surface flex min-w-0 flex-col p-5", className)}>
      <header>
        <h3 className="m-0 text-[17px] font-semibold tracking-[-0.01em] text-slate-900">{c.title}</h3>
        <p className="m-0 text-[13px] text-slate-500">{c.sub}</p>
      </header>
      <div className="mt-4 flex flex-wrap gap-2">
        <Select label={c.district} value={district} onChange={setDistrict} options={DISTRICTS.map((d) => ({ value: d, label: d }))} />
        <label className="flex flex-col gap-0.5 text-[12px] text-slate-500">
          {c.tons}
          <input type="number" min={1} max={2000} step={10} value={draft} onChange={(e) => setDraft(e.target.value)}
            className="num min-h-9 w-28 rounded-lg border border-slate-300 bg-white px-2.5 text-[14px] font-medium text-slate-900 shadow-sm max-sm:min-h-11" />
        </label>
      </div>

      {live.error && <p className="mt-4 text-[13px] text-rose-600">{live.error}</p>}
      {!q && !live.error && (
        <p className="mt-4 text-[13px] text-slate-500">{live.status === "loading" ? "Calling query_cold_storage_quota…" : `Start the backend to query ${district}; the cached snapshot covers Rangpur only.`}</p>
      )}

      {q && (
        <>
          <div className="mt-5">
            <div className="num text-[40px] leading-none text-slate-900">{q.quota_capture.non_farmer_capture_pct.toFixed(2)}%</div>
            <div className="text-[13px] text-slate-600">{c.held}</div>
          </div>
          <div className="mt-4 flex h-4 overflow-hidden rounded-full bg-slate-100" role="img"
            aria-label={segments.map((s) => `${s.label} ${s.pct.toFixed(2)}%`).join(", ")}>
            {segments.map((s) => <div key={s.label} className={s.color} style={{ width: `${s.pct}%` }} />)}
          </div>
          <ul className="m-0 mt-3 grid list-none grid-cols-2 gap-x-4 gap-y-1.5 p-0 text-[12.5px]">
            {segments.map((s) => (
              <li key={s.label} className="flex min-w-0 items-center gap-1.5 text-slate-600">
                <span className={cn("size-2.5 shrink-0 rounded-sm", s.color)} />
                <span className="truncate">{s.label}</span>
                <span className="num ml-auto text-slate-900">{s.pct.toFixed(2)}%</span>
              </li>
            ))}
          </ul>

          <div className={cn("mt-4 rounded-lg px-3 py-2.5 text-[13px] ring-1 ring-inset",
            fits ? "bg-emerald-50 text-emerald-800 ring-emerald-700/15" : "bg-rose-100/60 text-rose-700 ring-rose-600/15")}>
            {fits
              ? c.fits(tonnes(tons), tonnes(q.total_open_smallholder_quota_mt), q.facilities_found)
              : c.short(tonnes(tons), tonnes(q.total_open_smallholder_quota_mt), tonnes(q.unallocated_tons))}
            {q.recommended_allocation.length > 0 && (
              <ul className="m-0 mt-2 list-none space-y-0.5 p-0 text-[12.5px] text-slate-700">
                {q.recommended_allocation.slice(0, 3).map((leg) => (
                  <li key={leg.facility_id} className="flex justify-between gap-2">
                    <span className="truncate">{names.get(leg.facility_id) ?? leg.facility_id}</span>
                    <span className="num shrink-0">{tonnes(leg.tons)} · {tk(leg.all_in_cost_tk, 0)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {q.district_gap && (
            <p className="m-0 mt-3 text-[12.5px] text-slate-500">{c.coverage(q.district, `${q.district_gap.storage_coverage_pct.toFixed(0)}%`)}</p>
          )}
        </>
      )}

      <footer className="mt-auto pt-4">
        <SourceChip status={live.error ? "live" : live.status} tool={live.status === "cached" ? `query_cold_storage_quota · run of ${SNAPSHOT_DATE}` : "query_cold_storage_quota"} ms={live.ms} />
      </footer>
    </article>
  );
}
