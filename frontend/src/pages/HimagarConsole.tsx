import { FileSignature, Snowflake, Timer, Warehouse } from "lucide-react";
import { lazy, Suspense, useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import { api, ApiError, type ChamberTelemetry, type Crop, type QuotaResult, type ShelfLifeResult, type StorageReservation } from "../api/client";
import { Badge, Button, Panel, Spinner, Stat } from "../components/ui";
import { cn, tk } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { pushAlert, refreshQuota, refreshTelemetry, setState, useAppState } from "../state/store";
import { IncidentControl } from "./IncidentControl";

// Three.js stays out of the main OS chunk until this panel renders.
const ColdStorage3DTwin = lazy(() => import("../components/ColdStorage3DTwin").then((m) => ({ default: m.ColdStorage3DTwin })));

/** The four districts with seeded BCSA facilities (coldchain_iot_mcp.FACILITIES). */
const DISTRICTS = ["Bogura", "Munshiganj", "Rangpur", "Thakurgaon"];
const CROPS: Crop[] = ["Cardinal Potato", "Diamant Potato", "Green Chili", "Brinjal", "Boro Rice"];
const FIELD = "min-h-10 w-full rounded-lg bg-white px-3 text-[14px] text-slate-900 ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-sky-600 focus:outline-none";
const mt = (value: number) => `${Math.round(value).toLocaleString("en-IN")} t`;

const COPY = {
  en: {
    facility: "Facility", district: "District", capacity: "Capacity", open: "Open smallholder quota", booked: "Booked by farmers",
    tariff: "Tariff", power: "Power", split: "Who holds the space", traders: "Traders", owners: "Plant owners", farmers: "Farmers",
    farmersOpen: "farmers, still open", chambers: "Chambers", inBand: "In band", alert: "Alert", outage: "Power cut", rot: "rot risk",
    pick: "Pick a chamber to inspect it in 3D.", booking: "Book a pooled slot", bookingLede: "Reserve space for a farmer group against the open smallholder quota. The node signs a warehouse receipt the group can borrow against.",
    cluster: "Farmer group ID", tons: "Tonnes (up to 50)", farmersCount: "Farmers in the group", reserve: "Reserve and sign",
    receipt: "Warehouse receipt", status: "Status", reserved: "Reserved", waitlisted: "Waitlisted", bags: "50 kg bags", charge: "Total charge",
    perFarmer: "Per farmer", validUntil: "Valid until", remaining: "Open quota left", signature: "HMAC-SHA256",
    shelf: "Shelf-life check", shelfLede: "How long a lot keeps at this chamber's temperature and humidity (Q10 model), and the spoilage to expect.",
    crop: "Crop", grade: "Grade", temp: "Temperature °C", rh: "Humidity %", check: "Check", days: "days left", lambda: "expected spoilage",
    chilling: "Chilling-injury risk", failed: "Request failed", booked2: "Slot booked",
  },
  bn: {
    facility: "হিমাগার", district: "জেলা", capacity: "ধারণক্ষমতা", open: "কৃষকের খোলা কোটা", booked: "কৃষকের বুকিং",
    tariff: "ভাড়া", power: "বিদ্যুৎ", split: "জায়গা কার দখলে", traders: "ব্যবসায়ী", owners: "মালিক", farmers: "কৃষক",
    farmersOpen: "কৃষক, এখনও খালি", chambers: "চেম্বার", inBand: "ঠিক আছে", alert: "সতর্কতা", outage: "বিদ্যুৎ নেই", rot: "পচনের ঝুঁকি",
    pick: "৩ডিতে দেখতে একটি চেম্বার বেছে নিন।", booking: "যৌথ বুকিং", bookingLede: "কৃষকের খোলা কোটা থেকে একটি কৃষক দলের জন্য জায়গা রাখুন। নোড একটি স্বাক্ষরিত গুদাম-রসিদ দেয়, যা দিয়ে ঋণ নেওয়া যায়।",
    cluster: "কৃষক দলের আইডি", tons: "টন (সর্বোচ্চ ৫০)", farmersCount: "দলে কৃষক", reserve: "বুক ও স্বাক্ষর",
    receipt: "গুদাম-রসিদ", status: "অবস্থা", reserved: "বুক হয়েছে", waitlisted: "অপেক্ষায়", bags: "৫০ কেজির বস্তা", charge: "মোট ভাড়া",
    perFarmer: "কৃষক প্রতি", validUntil: "মেয়াদ", remaining: "বাকি কোটা", signature: "HMAC-SHA256",
    shelf: "সংরক্ষণকাল যাচাই", shelfLede: "এই চেম্বারের তাপমাত্রা ও আর্দ্রতায় লট কতদিন ভালো থাকবে (Q10 মডেল), আর কতটা পচন আশা করা যায়।",
    crop: "ফসল", grade: "গ্রেড", temp: "তাপমাত্রা °সে", rh: "আর্দ্রতা %", check: "যাচাই", days: "দিন বাকি", lambda: "প্রত্যাশিত পচন",
    chilling: "অতিরিক্ত ঠান্ডার ঝুঁকি", failed: "অনুরোধ ব্যর্থ", booked2: "বুকিং হয়েছে",
  },
};

const message = (error: unknown) => (error instanceof ApiError ? error.message : String(error));

/** The cold-storage manager's seat: one facility's quota, every chamber's health, signed bookings and shelf life. */
export function HimagarConsole() {
  const c = useCopy(COPY);
  const user = useAppState((s) => s.user);
  const focus = useAppState((s) => s.focusChamber);
  const liveTelemetry = useAppState((s) => s.telemetry);
  const [district, setDistrict] = useState(() => DISTRICTS.find((d) => d === user?.district) ?? focus.district);
  const [quota, setQuota] = useState<QuotaResult | null>(null);
  const [facilityId, setFacilityId] = useState(focus.facilityId);
  const [chambers, setChambers] = useState<ChamberTelemetry[] | null>(null);

  const loadQuota = async (forDistrict: string) => {
    const result = await api.coldStorageQuota(forDistrict);
    setQuota(result.data);
    return result.data;
  };

  // A district's facilities; keep the focused facility when it is among them.
  useEffect(() => {
    void loadQuota(district).then((q) => {
      const own = q.facilities.filter((f) => f.district === district);
      const list = own.length ? own : q.facilities;
      setFacilityId((current) => (list.some((f) => f.facility_id === current) ? current : list[0]?.facility_id ?? current));
    });
  }, [district]);

  const facility = quota?.facilities.find((f) => f.facility_id === facilityId) ?? null;

  // Every chamber of the facility, polled every 10 s: a cut on the whole plant must show on every row, not only on the
  // chamber being inspected.
  const readChambers = useCallback(async () => {
    if (!facility) return;
    const ids = Array.from({ length: facility.chambers }, (_, i) => `CH-${String(i + 1).padStart(2, "0")}`);
    setChambers(await Promise.all(ids.map((id) => api.chamberTelemetry(facility.facility_id, id).then((r) => r.data))));
  }, [facility?.facility_id, facility?.chambers]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!facility) return;
    setChambers(null);
    void readChambers();
    const timer = window.setInterval(() => void readChambers(), 10_000);
    if (focus.facilityId !== facility.facility_id) {
      setState({ focusChamber: { facilityId: facility.facility_id, chamberId: "CH-01", district: facility.district } });
    }
    return () => window.clearInterval(timer);
  }, [readChambers]); // eslint-disable-line react-hooks/exhaustive-deps

  const facilities = useMemo(() => {
    const all = quota?.facilities ?? [];
    const own = all.filter((f) => f.district === district);
    return own.length ? own : all;
  }, [quota, district]);

  const inspect = (chamberId: string) => {
    if (facility) setState({ focusChamber: { facilityId: facility.facility_id, chamberId, district: facility.district } });
  };

  // The focused chamber's polled reading replaces its once-read row, so the list and the 3D twin agree.
  const rows = chambers?.map((row) => (liveTelemetry && liveTelemetry.facility_id === row.facility_id && liveTelemetry.chamber_id === row.chamber_id ? liveTelemetry : row));

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <Panel title={c.facility} icon={<Warehouse className="size-4 text-sky-700" aria-hidden />}>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="grid gap-1 text-[13px] font-medium text-slate-700">{c.district}
            <select value={district} onChange={(e) => setDistrict(e.target.value)} className={FIELD}>
              {DISTRICTS.map((d) => <option key={d}>{d}</option>)}
            </select>
          </label>
          <label className="grid gap-1 text-[13px] font-medium text-slate-700">{c.facility}
            <select value={facilityId} onChange={(e) => setFacilityId(e.target.value)} className={FIELD} disabled={!facilities.length}>
              {facilities.map((f) => <option key={f.facility_id} value={f.facility_id}>{f.name} · {f.facility_id}</option>)}
            </select>
          </label>
        </div>
        {!facility ? <div className="mt-4"><Spinner /></div> : (
          <>
            <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-5">
              <Stat label={c.capacity} value={mt(facility.total_capacity_mt)} hint={`${facility.chambers} ${c.chambers.toLowerCase()}`} />
              <Stat label={c.open} value={mt(facility.open_smallholder_quota_mt)} tone="amber" />
              <Stat label={c.booked} value={mt(facility.farmer_quota_booked_mt)} />
              <Stat label={c.tariff} value={`Tk ${facility.tariff_tk_per_kg.toFixed(2)}/kg`} />
              <Stat label={c.power} value={facility.power_status} tone={facility.power_status === "OUTAGE" ? "red" : "emerald"} />
            </div>
            <figure className="m-0 mt-4">
              <figcaption className="text-[13px] font-medium text-slate-700">{c.split}</figcaption>
              <div className="mt-2 flex h-3 overflow-hidden rounded-full" role="img"
                aria-label={`${c.traders} ${mt(facility.trader_quota_mt)}, ${c.owners} ${mt(facility.owner_quota_mt)}, ${c.farmers} ${mt(facility.farmer_quota_mt)}`}>
                <div className="h-full bg-slate-500" style={{ width: `${(facility.trader_quota_mt / facility.total_capacity_mt) * 100}%` }} />
                <div className="h-full bg-sky-600" style={{ width: `${(facility.owner_quota_mt / facility.total_capacity_mt) * 100}%` }} />
                <div className="h-full bg-amber-600" style={{ width: `${(facility.farmer_quota_booked_mt / facility.total_capacity_mt) * 100}%` }} />
                <div className="h-full bg-amber-300" style={{ width: `${(facility.open_smallholder_quota_mt / facility.total_capacity_mt) * 100}%` }} />
              </div>
              <ul className="m-0 mt-2 flex list-none flex-wrap gap-x-4 gap-y-1 p-0 text-[12.5px] text-slate-600">
                <li><span className="mr-1.5 inline-block size-2.5 rounded-[3px] bg-slate-500" />{c.traders} {mt(facility.trader_quota_mt)}</li>
                <li><span className="mr-1.5 inline-block size-2.5 rounded-[3px] bg-sky-600" />{c.owners} {mt(facility.owner_quota_mt)}</li>
                <li><span className="mr-1.5 inline-block size-2.5 rounded-[3px] bg-amber-600" />{c.farmers} {mt(facility.farmer_quota_booked_mt)}</li>
                <li><span className="mr-1.5 inline-block size-2.5 rounded-[3px] bg-amber-300" />{c.farmersOpen} {mt(facility.open_smallholder_quota_mt)}</li>
              </ul>
            </figure>
          </>
        )}
      </Panel>

      {facility && (
        <IncidentControl facility={facility} rows={rows} facilities={quota?.facilities ?? []}
          onChanged={async () => { await Promise.all([readChambers(), refreshTelemetry(), loadQuota(district), refreshQuota()]); }} />
      )}

      <div className="grid min-w-0 gap-4 xl:grid-cols-5">
        <Suspense fallback={<div className="well min-h-[420px] xl:col-span-3" aria-busy />}>
          <ColdStorage3DTwin className="xl:col-span-3" />
        </Suspense>
        <Panel className="xl:col-span-2" title={c.chambers} icon={<Snowflake className="size-4 text-sky-700" aria-hidden />}>
          <p className="m-0 mb-3 text-[13px] text-slate-600">{c.pick}</p>
          {!rows ? <Spinner /> : (
            <ul className="m-0 grid list-none gap-2 p-0">
              {rows.map((t) => {
                const selected = focus.facilityId === t.facility_id && focus.chamberId === t.chamber_id;
                const outage = t.power_source === "OUTAGE";
                const ok = !outage && t.alerts.length === 0;
                return (
                  <li key={t.chamber_id}>
                    <button type="button" onClick={() => inspect(t.chamber_id)} aria-pressed={selected}
                      className={cn("grid w-full grid-cols-[64px_minmax(0,1fr)_auto] items-center gap-3 rounded-xl px-3 py-2 text-left ring-1 ring-inset transition-colors",
                        selected ? "bg-sky-50 ring-2 ring-sky-600" : "bg-white ring-slate-200 hover:bg-slate-50")}>
                      <span className="font-mono text-[13px] font-semibold text-slate-900">{t.chamber_id}</span>
                      <span className="min-w-0 text-[12.5px] text-slate-600">
                        <span className="num text-slate-900">{t.temperature_c.toFixed(1)} °C · {t.relative_humidity_pct.toFixed(0)}% RH</span>
                        <span className="block truncate">{t.stored_crop} · {Math.round(t.stored_tons).toLocaleString("en-IN")} t · {c.rot} {t.rot_risk_pct.toFixed(1)}%</span>
                      </span>
                      <Badge tone={outage ? "red" : ok ? "emerald" : "amber"}>{outage ? c.outage : ok ? c.inBand : c.alert}</Badge>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
      </div>

      <div className="grid min-w-0 gap-4 lg:grid-cols-2">
        <BookingDesk facilityId={facility?.facility_id ?? null} onBooked={() => { void loadQuota(district); void refreshQuota(); }} />
        <ShelfLifeCheck temperature={liveTelemetry?.temperature_c} humidity={liveTelemetry?.relative_humidity_pct} />
      </div>
    </div>
  );
}

function BookingDesk({ facilityId, onBooked }: { facilityId: string | null; onBooked: () => void }) {
  const c = useCopy(COPY);
  const [form, setForm] = useState({ cluster_id: "COOP-BOG-SHIBGANJ", tons: 20, farmer_count: 25 });
  const [busy, setBusy] = useState(false);
  const [receipt, setReceipt] = useState<StorageReservation | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!facilityId) return;
    setBusy(true);
    try {
      const result = await api.reserveStorage({ ...form, facility_id: facilityId });
      setReceipt(result);
      pushAlert(result.status === "REJECTED" ? "warn" : "success", c.booked2, `${result.reserved_tons} t · ${result.facility_name}`);
      onBooked();
    } catch (error) {
      pushAlert("danger", c.failed, message(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title={c.booking} icon={<FileSignature className="size-4 text-amber-600" aria-hidden />}>
      <p className="m-0 mb-3 text-[13px] text-slate-600">{c.bookingLede}</p>
      <form onSubmit={(e) => void submit(e)} className="grid gap-3 sm:grid-cols-3">
        <label className="grid gap-1 text-[13px] font-medium text-slate-700 sm:col-span-3">{c.cluster}
          <input required pattern="[A-Za-z0-9_\-]{3,40}" value={form.cluster_id} onChange={(e) => setForm({ ...form, cluster_id: e.target.value })} className={cn(FIELD, "font-mono")} />
        </label>
        <label className="grid gap-1 text-[13px] font-medium text-slate-700">{c.tons}
          <input required type="number" min={1} max={50} step={1} value={form.tons} onChange={(e) => setForm({ ...form, tons: Number(e.target.value) })} className={FIELD} />
        </label>
        <label className="grid gap-1 text-[13px] font-medium text-slate-700">{c.farmersCount}
          <input required type="number" min={1} max={500} step={1} value={form.farmer_count} onChange={(e) => setForm({ ...form, farmer_count: Number(e.target.value) })} className={FIELD} />
        </label>
        <div className="flex items-end">
          <Button variant="amber" type="submit" className="min-h-10 w-full" disabled={busy || !facilityId}>{busy ? <Spinner /> : null} {c.reserve}</Button>
        </div>
      </form>
      {receipt && (
        <div className="mt-4 rounded-xl bg-amber-50/60 p-3 ring-1 ring-inset ring-amber-600/20">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-[14px] font-semibold text-slate-900">{c.receipt}</span>
            <Badge tone={receipt.status === "CONFIRMED" ? "emerald" : receipt.status === "PARTIAL" ? "amber" : "red"}>{receipt.status}</Badge>
          </div>
          <div className="mt-1 font-mono text-[12px] text-slate-600">{receipt.receipt_id ?? "—"}</div>
          <dl className="m-0 mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-[13px]">
            {[
              [c.reserved, `${receipt.reserved_tons} t`], [c.waitlisted, `${receipt.waitlisted_tons} t`],
              [c.bags, receipt.bags_50kg.toLocaleString("en-IN")], [c.charge, tk(receipt.total_charge_tk, 0)],
              [c.perFarmer, tk(receipt.per_farmer_charge_tk, 0)], [c.validUntil, receipt.valid_until ?? "—"],
              [c.remaining, mt(receipt.remaining_open_quota_mt)],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between gap-2"><dt className="text-slate-600">{label}</dt><dd className="num m-0 text-slate-900">{value}</dd></div>
            ))}
          </dl>
          {receipt.receipt_signature && <div className="mt-2 truncate font-mono text-[11px] text-slate-500">{c.signature} {receipt.receipt_signature}</div>}
        </div>
      )}
    </Panel>
  );
}

function ShelfLifeCheck({ temperature, humidity }: { temperature?: number; humidity?: number }) {
  const c = useCopy(COPY);
  const [form, setForm] = useState<{ crop: Crop; grade: "A" | "B" | "C"; transit_temp_c: number; rh_pct: number }>(
    { crop: "Cardinal Potato", grade: "A", transit_temp_c: 9.5, rh_pct: 93 });
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ShelfLifeResult | null>(null);

  // Start from the inspected chamber's live reading until the manager edits the numbers.
  const [edited, setEdited] = useState(false);
  useEffect(() => {
    if (!edited && temperature !== undefined && humidity !== undefined) {
      setForm((f) => ({ ...f, transit_temp_c: Math.round(temperature * 10) / 10, rh_pct: Math.round(humidity) }));
    }
  }, [temperature, humidity, edited]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      setResult(await api.shelfLife(form));
    } catch (error) {
      pushAlert("danger", c.failed, message(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title={c.shelf} icon={<Timer className="size-4 text-sky-700" aria-hidden />}>
      <p className="m-0 mb-3 text-[13px] text-slate-600">{c.shelfLede}</p>
      <form onSubmit={(e) => void submit(e)} className="grid gap-3 sm:grid-cols-2">
        <label className="grid gap-1 text-[13px] font-medium text-slate-700">{c.crop}
          <select value={form.crop} onChange={(e) => setForm({ ...form, crop: e.target.value as Crop })} className={FIELD}>
            {CROPS.map((crop) => <option key={crop}>{crop}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-[13px] font-medium text-slate-700">{c.grade}
          <select value={form.grade} onChange={(e) => setForm({ ...form, grade: e.target.value as "A" | "B" | "C" })} className={FIELD}>
            {(["A", "B", "C"] as const).map((g) => <option key={g}>{g}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-[13px] font-medium text-slate-700">{c.temp}
          <input required type="number" min={-5} max={50} step={0.1} value={form.transit_temp_c}
            onChange={(e) => { setEdited(true); setForm({ ...form, transit_temp_c: Number(e.target.value) }); }} className={FIELD} />
        </label>
        <label className="grid gap-1 text-[13px] font-medium text-slate-700">{c.rh}
          <input required type="number" min={5} max={100} step={1} value={form.rh_pct}
            onChange={(e) => { setEdited(true); setForm({ ...form, rh_pct: Number(e.target.value) }); }} className={FIELD} />
        </label>
        <Button variant="primary" type="submit" className="min-h-10 sm:col-span-2" disabled={busy}>{busy ? <Spinner /> : null} {c.check}</Button>
      </form>
      {result && (
        <div className="mt-4 rounded-xl bg-sky-50/60 p-3 ring-1 ring-inset ring-sky-600/20">
          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
            <span className="num text-[24px] font-semibold text-slate-900">{result.remaining_shelf_life_days.toFixed(1)}</span>
            <span className="text-[13px] text-slate-600">{c.days}</span>
            <span className="num text-[15px] font-semibold text-slate-900">{(result.lambda_rot * 100).toFixed(1)}%</span>
            <span className="text-[13px] text-slate-600">{c.lambda}</span>
            {result.chilling_injury_risk && <Badge tone="amber">{c.chilling}</Badge>}
          </div>
          <ul className="m-0 mt-2 grid list-disc gap-1 pl-5 text-[13px] text-slate-700">
            {result.storage_advice.map((line) => <li key={line}>{line}</li>)}
          </ul>
        </div>
      )}
    </Panel>
  );
}

export default HimagarConsole;
