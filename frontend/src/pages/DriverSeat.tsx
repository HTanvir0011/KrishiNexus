import { CheckCircle2, MapPinned, PackageCheck, ShieldAlert, Thermometer, Truck } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { api, ApiError, type MarketLot } from "../api/client";
import { DisputeBox } from "../components/DisputeBox";
import { RouteSteps } from "../components/RouteSteps";
import { Badge, Button, Panel, Spinner, Stat } from "../components/ui";
import { cn, tk } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { useBecame } from "../lib/motion";
import { pushAlert, useAppState } from "../state/store";

const FIELD = "min-h-10 w-full rounded-lg bg-white px-3 text-[14px] text-slate-900 ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-amber-600 focus:outline-none";

const COPY = {
  en: {
    available: "Jobs waiting for a driver", mine: "My deliveries", none: "No jobs right now.",
    take: "Take this job", pickedUp: "Loaded: start the trip", delivered: "Delivered: release payment",
    temp: "Load temperature °C", rh: "Humidity %", report: "Report", shelf: (h: number) => `${Math.round(h)} h of shelf life left at this temperature`,
    atRisk: "At risk: the load may spoil before arrival. Cool it, or deliver sooner.", safe: "Safe to arrive.",
    route: (from: string, to: string, km: number, h: number) => `${from} → ${to} · ${km} km · about ${h} h`,
    buyer: "Buyer", farmer: "Farmer", payment: "Payment held", released: "Payment released to the farmer",
    states: { AWAITING_DRIVER: "Waiting for a driver", ASSIGNED: "Assigned to you", PICKED_UP: "On the road", DELIVERED: "Delivered" },
    readOnly: "Read-only view for judges and admins: only driver accounts take jobs.", failed: "Request failed", done: "Updated",
    steps: ["Waiting", "Taken", "On the road", "Delivered"], stepsLabel: "Delivery progress",
    stats: { waiting: "Jobs waiting", road: "On the road", delivered: "Delivered", paid: "Payments released" },
    statHints: { waiting: "sold lots without a driver", road: "taken or loaded", delivered: "weighed at the buyer", paid: "to farmers, on delivery" },
    trip: (km: number, h: number) => `${km} km · about ${h} h`,
    shelfBar: (eta: number, life: number) => `Trip ${eta} h of ${Math.round(life)} h shelf life (arrive with at least a quarter left)`,
  },
  bn: {
    available: "চালকের অপেক্ষায় কাজ", mine: "আমার ডেলিভারি", none: "এখন কোনো কাজ নেই।",
    take: "কাজটি নিন", pickedUp: "মাল তোলা হয়েছে: রওনা", delivered: "পৌঁছে দিয়েছি: টাকা ছাড়",
    temp: "মালের তাপমাত্রা °সে", rh: "আর্দ্রতা %", report: "জানান", shelf: (h: number) => `এই তাপমাত্রায় আর ${Math.round(h)} ঘণ্টা ভালো থাকবে`,
    atRisk: "ঝুঁকি: পৌঁছানোর আগে মাল নষ্ট হতে পারে। ঠান্ডা রাখুন বা দ্রুত পৌঁছান।", safe: "নিরাপদে পৌঁছাবে।",
    route: (from: string, to: string, km: number, h: number) => `${from} → ${to} · ${km} কিমি · প্রায় ${h} ঘণ্টা`,
    buyer: "ক্রেতা", farmer: "কৃষক", payment: "টাকা আটকে আছে", released: "টাকা কৃষককে ছাড় হয়েছে",
    states: { AWAITING_DRIVER: "চালকের অপেক্ষা", ASSIGNED: "আপনার কাজ", PICKED_UP: "পথে", DELIVERED: "পৌঁছেছে" },
    readOnly: "বিচারক ও অ্যাডমিনের জন্য শুধু দেখা: কেবল চালক কাজ নিতে পারেন।", failed: "অনুরোধ ব্যর্থ", done: "হালনাগাদ হয়েছে",
    steps: ["অপেক্ষা", "নেওয়া হয়েছে", "পথে", "পৌঁছেছে"], stepsLabel: "ডেলিভারির অগ্রগতি",
    stats: { waiting: "অপেক্ষমাণ কাজ", road: "পথে", delivered: "পৌঁছেছে", paid: "ছাড় হওয়া টাকা" },
    statHints: { waiting: "বিক্রি হয়েছে, চালক নেই", road: "নেওয়া বা লোড করা", delivered: "ক্রেতার কাছে ওজন হয়েছে", paid: "ডেলিভারিতে কৃষকের কাছে" },
    trip: (km: number, h: number) => `${km} কিমি · প্রায় ${h} ঘণ্টা`,
    shelfBar: (eta: number, life: number) => `যাত্রা ${eta} ঘণ্টা, মাল ভালো থাকবে ${Math.round(life)} ঘণ্টা (অন্তত এক-চতুর্থাংশ সময় হাতে রেখে পৌঁছাতে হবে)`,
  },
};

const STAGE = { AWAITING_DRIVER: 0, ASSIGNED: 1, PICKED_UP: 2, DELIVERED: 3 } as const;
const message = (error: unknown) => (error instanceof ApiError ? error.message : String(error));

/** The truck driver's seat: open delivery jobs, then pickup, temperature reports on the road, and delivery. */
export function DriverSeat() {
  const c = useCopy(COPY);
  const user = useAppState((s) => s.user);
  const [jobs, setJobs] = useState<MarketLot[] | null>(null);

  const load = useCallback(async () => {
    try {
      setJobs(await api.deliveries());
    } catch (error) {
      pushAlert("danger", c.failed, message(error));
    }
  }, [c.failed]);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 8_000);
    return () => window.clearInterval(timer);
  }, [load]);

  if (!user) return null;
  if (!jobs) return <Spinner />;
  const driver = user.role === "driver";
  const waiting = jobs.filter((j) => j.delivery?.status === "AWAITING_DRIVER");
  const mine = jobs.filter((j) => j.delivery?.status !== "AWAITING_DRIVER" && (!driver || j.delivery?.driver_id === user.user_id));

  const onRoad = mine.filter((j) => j.delivery?.status === "ASSIGNED" || j.delivery?.status === "PICKED_UP");
  const delivered = mine.filter((j) => j.delivery?.status === "DELIVERED");
  const paid = delivered.reduce((sum, j) => sum + (j.escrow?.status === "RELEASED" ? j.escrow.amount_tk : 0), 0);

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {!driver && <p className="m-0 text-[13px] text-slate-600 xl:col-span-2">{c.readOnly}</p>}
      <section className="surface grid grid-cols-2 gap-4 p-4 sm:grid-cols-4 xl:col-span-2" aria-label="Driver summary">
        <Stat label={c.stats.waiting} value={waiting.length} hint={c.statHints.waiting} tone="amber" />
        <Stat label={c.stats.road} value={onRoad.length} hint={c.statHints.road} tone="sky" />
        <Stat label={c.stats.delivered} value={delivered.length} hint={c.statHints.delivered} tone="emerald" />
        <Stat label={c.stats.paid} value={tk(paid, 0)} hint={c.statHints.paid} tone="emerald" />
      </section>
      <Panel title={`${c.available} (${waiting.length})`} icon={<MapPinned className="size-4 text-amber-600" aria-hidden />}>
        {waiting.length === 0 ? <p className="m-0 text-[14px] text-slate-600">{c.none}</p>
          : <div className="grid gap-3">{waiting.map((job) => <JobCard key={job.lot_id} job={job} canAct={driver} onChange={load} />)}</div>}
      </Panel>
      <Panel title={`${c.mine} (${mine.length})`} icon={<Truck className="size-4 text-amber-600" aria-hidden />}>
        {mine.length === 0 ? <p className="m-0 text-[14px] text-slate-600">{c.none}</p>
          : <div className="grid gap-3">{mine.map((job) => <JobCard key={job.lot_id} job={job} canAct={driver} onChange={load} />)}</div>}
      </Panel>
    </div>
  );
}

function JobCard({ job, canAct, onChange }: { job: MarketLot; canAct: boolean; onChange: () => Promise<void> }) {
  const c = useCopy(COPY);
  const user = useAppState((s) => s.user);
  const lang = useAppState((s) => s.lang);
  const d = job.delivery!;
  const buyer = job.bids.find((b) => b.bid_id === job.accepted_bid_id);
  const [busy, setBusy] = useState(false);
  const [temp, setTemp] = useState(String(d.last_temp_c ?? 28));
  const [rh, setRh] = useState(String(d.last_rh_pct ?? 80));
  const released = useBecame(job.escrow?.status, "RELEASED");

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await action();
      pushAlert("success", c.done);
      await onChange();
    } catch (error) {
      pushAlert("danger", c.failed, message(error));
    } finally {
      setBusy(false);
    }
  };

  const report = (event: FormEvent) => {
    event.preventDefault();
    void run(() => api.reportTemperature(job.lot_id, Number(temp), Number(rh)));
  };

  return (
    <article className="rounded-xl bg-white p-3 ring-1 ring-inset ring-slate-200">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-[15px] font-semibold text-slate-900">{job.crop} · {Math.round(job.weight_kg).toLocaleString("en-IN")} kg</div>
          <div className="text-[12.5px] text-slate-600">{c.farmer}: {job.farmer_name}{job.upazila ? `, ${job.upazila}` : ""} · {c.buyer}: {buyer?.buyer_name ?? "—"}</div>
        </div>
        <Badge tone={d.status === "DELIVERED" ? "emerald" : d.status === "PICKED_UP" ? "sky" : "amber"}>{c.states[d.status]}</Badge>
      </div>

      {/* The road itself: the truck sits at the start until loaded, mid-way on the road, at the buyer once delivered. */}
      <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2.5 ring-1 ring-inset ring-slate-200" aria-label={c.route(d.origin_district, d.destination_district, d.distance_km, d.eta_hours)}>
        <div className="flex items-center gap-3">
          <span className="max-w-[35%] truncate text-[12.5px] font-medium text-slate-800">{job.upazila ? `${job.upazila}, ` : ""}{d.origin_district}</span>
          <span aria-hidden className="relative h-1 flex-1 rounded-full bg-slate-200">
            <span className="absolute inset-y-0 left-0 rounded-full bg-emerald-500 transition-[width] duration-700 ease-(--ease-out-expo)"
              style={{ width: `${d.status === "DELIVERED" ? 100 : d.status === "PICKED_UP" ? 50 : 0}%` }} />
            <span className="absolute top-1/2 grid size-6 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-md bg-amber-600 text-white shadow-sm transition-[left] duration-700 ease-(--ease-out-expo)"
              style={{ left: `${d.status === "DELIVERED" ? 100 : d.status === "PICKED_UP" ? 50 : 0}%` }}>
              <Truck className="size-3.5" />
            </span>
          </span>
          <span className="max-w-[35%] truncate text-right text-[12.5px] font-medium text-slate-800">{d.destination_district}</span>
        </div>
        <div className="num mt-1.5 text-center text-[12px] text-slate-500">{c.trip(d.distance_km, d.eta_hours)}</div>
      </div>

      <RouteSteps className="mt-3" steps={c.steps} at={STAGE[d.status]} label={c.stepsLabel}
        icon={d.status === "PICKED_UP" ? <Truck className="size-3" aria-hidden /> : undefined} />

      {job.escrow && (
        <div className={cn("-mx-1 mt-2 rounded-md px-1 py-0.5 text-[12.5px] text-slate-700", released && "animate-flash")}>
          {job.escrow.status === "RELEASED" ? <CheckCircle2 className={cn("mr-1 inline size-3.5 text-emerald-700", released && "animate-pop")} aria-hidden /> : null}
          {job.escrow.status === "RELEASED" ? c.released : c.payment}: <span className="num font-semibold">{tk(job.escrow.amount_tk, 0)}</span>
        </div>
      )}

      {canAct && user && <DisputeBox lot={job} me={user.user_id} lang={lang} onChange={onChange} />}

      {d.shelf_life_hours !== null && d.status !== "DELIVERED" && (
        <div className={d.at_risk ? "mt-2 rounded-lg bg-rose-50 px-2 py-1.5 text-[12.5px] text-rose-800 ring-1 ring-inset ring-rose-600/20" : "mt-2 rounded-lg bg-emerald-50 px-2 py-1.5 text-[12.5px] text-emerald-900 ring-1 ring-inset ring-emerald-700/15"}>
          {d.at_risk && <ShieldAlert className="mr-1 inline size-3.5" aria-hidden />}
          {d.last_temp_c} °C, {d.last_rh_pct}% RH: {c.shelf(d.shelf_life_hours)}. {d.at_risk ? c.atRisk : c.safe}
          {/* The trip against the usable shelf life (three quarters of it: the pools' arrival reserve). */}
          <span aria-hidden className="mt-1.5 block h-1.5 overflow-hidden rounded-full bg-white/80">
            <span className={cn("block h-full rounded-full", d.at_risk ? "bg-rose-500" : "bg-emerald-500")}
              style={{ width: `${Math.min(100, (d.eta_hours / Math.max(0.1, d.shelf_life_hours * 0.75)) * 100)}%` }} />
          </span>
          <span className="mt-1 block text-[11.5px] opacity-80">{c.shelfBar(d.eta_hours, d.shelf_life_hours)}</span>
        </div>
      )}

      {canAct && d.status === "AWAITING_DRIVER" && (
        <Button variant="amber" className="mt-3 min-h-11 w-full" disabled={busy} onClick={() => void run(() => api.deliveryStep(job.lot_id, "claim"))}>
          {busy ? <Spinner /> : <Truck className="size-4" aria-hidden />} {c.take}
        </Button>
      )}
      {canAct && d.status === "ASSIGNED" && (
        <Button variant="primary" className="mt-3 min-h-11 w-full" disabled={busy} onClick={() => void run(() => api.deliveryStep(job.lot_id, "pickup"))}>
          {busy ? <Spinner /> : <PackageCheck className="size-4" aria-hidden />} {c.pickedUp}
        </Button>
      )}
      {canAct && d.status === "PICKED_UP" && (
        <>
          <form onSubmit={report} className="mt-3 grid grid-cols-[1fr_1fr_auto] gap-2">
            <label className="grid gap-1 text-[12.5px] font-medium text-slate-700">{c.temp}
              <input required type="number" min={-5} max={55} step={0.5} value={temp} onChange={(e) => setTemp(e.target.value)} className={FIELD} />
            </label>
            <label className="grid gap-1 text-[12.5px] font-medium text-slate-700">{c.rh}
              <input required type="number" min={5} max={100} step={1} value={rh} onChange={(e) => setRh(e.target.value)} className={FIELD} />
            </label>
            <div className="flex items-end">
              <Button variant="ghost" type="submit" className="min-h-10" disabled={busy}><Thermometer className="size-4" aria-hidden /> {c.report}</Button>
            </div>
          </form>
          <Button variant="primary" className="mt-2 min-h-11 w-full" disabled={busy} onClick={() => void run(() => api.deliveryStep(job.lot_id, "deliver"))}>
            {busy ? <Spinner /> : <CheckCircle2 className="size-4" aria-hidden />} {c.delivered}
          </Button>
        </>
      )}

      <ol className="m-0 mt-3 grid list-none gap-1 border-t border-slate-100 p-0 pt-2 text-[12px] text-slate-600">
        {d.events.slice().reverse().map((e, i) => (
          <li key={i}><span className="font-mono text-slate-400">{new Date(e.at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}</span> {e.detail}</li>
        ))}
      </ol>
    </article>
  );
}

export default DriverSeat;
