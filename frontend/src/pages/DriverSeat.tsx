import { CheckCircle2, MapPinned, PackageCheck, ShieldAlert, Thermometer, Truck } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { api, ApiError, type MarketLot } from "../api/client";
import { RouteSteps } from "../components/RouteSteps";
import { Badge, Button, Panel, Spinner } from "../components/ui";
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

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {!driver && <p className="m-0 text-[13px] text-slate-600 xl:col-span-2">{c.readOnly}</p>}
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
          <div className="text-[12.5px] text-slate-600">{c.route(d.origin_district, d.destination_district, d.distance_km, d.eta_hours)}</div>
          <div className="text-[12.5px] text-slate-600">{c.farmer}: {job.farmer_name}{job.upazila ? `, ${job.upazila}` : ""} · {c.buyer}: {buyer?.buyer_name ?? "—"}</div>
        </div>
        <Badge tone={d.status === "DELIVERED" ? "emerald" : d.status === "PICKED_UP" ? "sky" : "amber"}>{c.states[d.status]}</Badge>
      </div>

      <RouteSteps className="mt-3" steps={c.steps} at={STAGE[d.status]} label={c.stepsLabel}
        icon={d.status === "PICKED_UP" ? <Truck className="size-3" aria-hidden /> : undefined} />

      {job.escrow && (
        <div className={cn("-mx-1 mt-2 rounded-md px-1 py-0.5 text-[12.5px] text-slate-700", released && "animate-flash")}>
          {job.escrow.status === "RELEASED" ? <CheckCircle2 className={cn("mr-1 inline size-3.5 text-emerald-700", released && "animate-pop")} aria-hidden /> : null}
          {job.escrow.status === "RELEASED" ? c.released : c.payment}: <span className="num font-semibold">{tk(job.escrow.amount_tk, 0)}</span>
        </div>
      )}

      {d.shelf_life_hours !== null && d.status !== "DELIVERED" && (
        <div className={d.at_risk ? "mt-2 rounded-lg bg-rose-50 px-2 py-1.5 text-[12.5px] text-rose-800 ring-1 ring-inset ring-rose-600/20" : "mt-2 rounded-lg bg-emerald-50 px-2 py-1.5 text-[12.5px] text-emerald-900 ring-1 ring-inset ring-emerald-700/15"}>
          {d.at_risk && <ShieldAlert className="mr-1 inline size-3.5" aria-hidden />}
          {d.last_temp_c} °C, {d.last_rh_pct}% RH: {c.shelf(d.shelf_life_hours)}. {d.at_risk ? c.atRisk : c.safe}
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
