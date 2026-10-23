import { useCallback, useEffect, useMemo, useState } from "react";

import { api, ApiError, type ChamberTelemetry, type QuotaResult } from "../../api/client";
import { ArcGauge } from "../../components/gauges";
import { cn } from "../../lib/format";
import { pushAlert } from "../../state/store";
import { RANGPUR_QUOTA_SNAPSHOT, type SourceStatus } from "../data";
import { FACILITIES, type FacilitySeed } from "../geo";
import { ChapterHeading, SourceNote, StoryButton } from "../parts";

export const COLD_DISTRICTS: FacilitySeed["district"][] = ["Rangpur", "Bogura", "Munshiganj", "Thakurgaon"];

function chamberFor(district: FacilitySeed["district"]): { facility: FacilitySeed; chamber: string } {
  if (district === "Rangpur") return { facility: FACILITIES.find((f) => f.id === "BCSA-RAN-02") ?? FACILITIES[0], chamber: "CH-03" };
  return { facility: FACILITIES.find((f) => f.district === district) ?? FACILITIES[0], chamber: "CH-01" };
}

const POWER: Record<ChamberTelemetry["power_source"], string> = { GRID: "Grid", DIESEL_GENERATOR: "Diesel generator", OUTAGE: "None, outage" };

export function ColdChapter({ district, onDistrict }: { district: FacilitySeed["district"]; onDistrict: (d: FacilitySeed["district"]) => void }) {
  const [quota, setQuota] = useState<{ data: QuotaResult; status: SourceStatus; sample: boolean } | null>(null);
  const [telemetry, setTelemetry] = useState<{ data: ChamberTelemetry; live: boolean } | null>(null);
  const [cut, setCut] = useState(false);
  const [busy, setBusy] = useState(false);
  const { facility, chamber } = chamberFor(district);

  useEffect(() => {
    let active = true;
    setQuota(null);
    api.coldStorageQuota(district)
      .then((r) => {
        if (!active) return;
        if (r.live) setQuota({ data: r.data, status: "live", sample: false });
        else if (district === "Rangpur") setQuota({ data: RANGPUR_QUOTA_SNAPSHOT, status: "cached", sample: false });
        else setQuota({ data: r.data, status: "cached", sample: true });
      })
      .catch((error: unknown) => active && pushAlert("warn", "Quota unavailable", error instanceof Error ? error.message : String(error)));
    return () => {
      active = false;
    };
  }, [district]);

  const readTelemetry = useCallback(async () => {
    const r = await api.chamberTelemetry(facility.id, chamber);
    setTelemetry({ data: r.data, live: r.live });
  }, [facility.id, chamber]);

  useEffect(() => {
    void readTelemetry();
  }, [readTelemetry]);

  const totals = useMemo(() => {
    const list = quota?.data.facilities ?? [];
    const sum = (pick: (f: QuotaResult["facilities"][number]) => number) => list.reduce((s, f) => s + pick(f), 0);
    const capacity = sum((f) => f.total_capacity_mt);
    const traders = sum((f) => f.trader_quota_mt);
    const owners = sum((f) => f.owner_quota_mt);
    const farmers = sum((f) => f.farmer_quota_mt);
    const open = quota?.data.total_open_smallholder_quota_mt ?? 0;
    const traderCells = capacity ? Math.round((traders / capacity) * 100) : 45;
    const ownerCells = capacity ? Math.round((owners / capacity) * 100) : 32;
    const farmerCells = 100 - traderCells - ownerCells;
    const openCells = farmers ? Math.min(farmerCells, Math.round((farmerCells * open) / farmers)) : 0;
    return { count: list.length, capacity, traders, owners, farmers, open, traderCells, ownerCells, farmerCells, openCells };
  }, [quota]);

  const cells = useMemo(() => {
    const kinds: string[] = [];
    for (let i = 0; i < totals.traderCells; i++) kinds.push("trader");
    for (let i = 0; i < totals.ownerCells; i++) kinds.push("owner");
    for (let i = 0; i < totals.farmerCells - totals.openCells; i++) kinds.push("booked");
    for (let i = 0; i < totals.openCells; i++) kinds.push("open");
    return kinds;
  }, [totals]);

  const toggleCut = async () => {
    setBusy(true);
    try {
      if (cut) {
        await api.clearAnomalies();
        setCut(false);
      } else {
        await api.simulatePowerCut(facility.id);
        setCut(true);
      }
      await readTelemetry();
    } catch (error) {
      pushAlert("danger", "The simulation did not run", error instanceof ApiError ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const t = telemetry?.data;
  const inBand = t ? t.temperature_f >= 48 && t.temperature_f <= 50 && t.power_source !== "OUTAGE" : true;
  const tonnes = (v: number) => `${Math.round(v).toLocaleString("en-IN")} t`;

  return (
    <>
      <ChapterHeading index={1}>Who holds the cold</ChapterHeading>
      <label className="label mb-5 inline-flex items-center gap-3 text-[14px] text-slate-400">
        District
        <select value={district} onChange={(e) => onDistrict(e.target.value as FacilitySeed["district"])}
          className="min-h-11 rounded-full border border-slate-50/25 bg-ink-900/80 px-4 text-[15px] text-slate-50">
          {COLD_DISTRICTS.map((d) => <option key={d}>{d}</option>)}
        </select>
      </label>
      <p className="text-[18px] leading-relaxed text-slate-200">
        {quota
          ? `${totals.count} cold stores within 60 km of ${district} can hold ${tonnes(totals.capacity)} of potatoes. Before a farmer arrives, traders have booked ${totals.traderCells}% of it and the plant owners ${totals.ownerCells}%.`
          : `Asking the cold stores around ${district} how much space is left…`}
      </p>

      <figure className="m-0 mt-6">
        <div className="grid w-full max-w-[22rem] grid-cols-10 gap-1" role="img"
          aria-label={`Of every 100 chambers: ${totals.traderCells} traders, ${totals.ownerCells} owners, ${totals.farmerCells - totals.openCells} farmers booked, ${totals.openCells} still open`}>
          {cells.map((kind, i) => (
            <span key={i} className={cn("aspect-square rounded-[3px]",
              kind === "trader" && "bg-slate-600", kind === "owner" && "bg-sky-600",
              kind === "booked" && "bg-mustard-400/35", kind === "open" && "bg-mustard-400")} />
          ))}
        </div>
        <figcaption className="label mt-3 grid max-w-[24rem] grid-cols-2 gap-x-6 gap-y-1 text-[14px] text-slate-400">
          <span className="flex items-center gap-2"><span className="size-2.5 rounded-[2px] bg-slate-600" />Traders {quota ? tonnes(totals.traders) : ""}</span>
          <span className="flex items-center gap-2"><span className="size-2.5 rounded-[2px] bg-sky-600" />Plant owners {quota ? tonnes(totals.owners) : ""}</span>
          <span className="flex items-center gap-2"><span className="size-2.5 rounded-[2px] bg-mustard-400/35" />Farmers, booked {quota ? tonnes(Math.max(0, totals.farmers - totals.open)) : ""}</span>
          <span className="flex items-center gap-2"><span className="size-2.5 rounded-[2px] bg-mustard-400" />Farmers, still open {quota ? tonnes(totals.open) : ""}</span>
        </figcaption>
      </figure>

      {quota && (
        <p className="mt-6 text-[18px] leading-relaxed text-slate-200">
          That leaves farmers {totals.farmerCells}%. {tonnes(totals.open)} of it is still open
          {district === "Rangpur" ? ", so Rahim's 400 kg would fit." : "."}
        </p>
      )}

      <div className="card mt-8 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="m-0 text-[17px] font-semibold text-slate-50">Chamber {chamber}</h3>
            <p className="m-0 text-[14px] text-slate-400">{t?.facility_name ?? facility.name}</p>
          </div>
          <span className={cn("rounded-full px-3 py-1 text-[13px] font-semibold", inBand ? "bg-emerald-600 text-slate-50" : "bg-red-500 text-slate-50")}>
            {inBand ? "In band" : "Out of band"}
          </span>
        </div>
        {t && (
          <div className="mt-3 flex flex-wrap items-center gap-6">
            <ArcGauge className="w-[220px] max-w-full" value={t.temperature_f} min={40} max={60} band={[48, 50]} unit="°F" alarm={!inBand}
              label={`Temperature ${t.temperature_f.toFixed(1)} degrees Fahrenheit, target 48 to 50`} />
            <div>
              <span className="num block text-[52px] leading-none text-slate-50">{t.temperature_f.toFixed(1)}°F</span>
              <span className="block text-[14px] text-slate-400">Target 48–50°F</span>
              <ul className="m-0 mt-3 list-none space-y-1 p-0 text-[15px] text-slate-400">
                <li>Humidity <b className="font-semibold text-slate-100">{t.relative_humidity_pct.toFixed(1)}%</b></li>
                <li>Power <b className="font-semibold text-slate-100">{POWER[t.power_source]}</b></li>
                <li>Rot risk <b className="font-semibold text-slate-100">{t.rot_risk_pct.toFixed(1)}%</b></li>
              </ul>
            </div>
          </div>
        )}
        {t && t.alerts.length > 0 && <p className="mt-3 mb-0 text-[14px] text-red-300">{t.alerts[0]}</p>}
        <StoryButton variant="ghost" className="mt-5" onClick={() => void toggleCut()} disabled={busy}>
          {cut ? "Restore power" : "Simulate a power cut"}
        </StoryButton>
        <p className="label mt-2 mb-0 text-[13px] text-slate-500">
          Simulation: the generator fails and the chamber warms for five hours. Restoring power clears every simulation.
        </p>
      </div>
      {quota && <SourceNote status={quota.status} label={quota.sample ? "Backend offline: a sample cold store is shown, not this district" : undefined} />}
    </>
  );
}
