import { CircleCheck, CircleDashed, CloudRain, PlugZap, Power, RotateCcw, Siren, Zap, ZapOff } from "lucide-react";
import { useState, type ReactNode } from "react";

import { api, ApiError, type ChamberTelemetry, type QuotaFacility } from "../api/client";
import { Badge, Button, Panel, Spinner } from "../components/ui";
import { cn } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { getState, pushAlert, setState, useAppState } from "../state/store";

const COPY = {
  en: {
    title: "Incident control",
    calm: "All chambers on grid power. Run a drill below to see how the plant responds.",
    blackout: (n: number) => `EMERGENCY: ${n} chamber${n === 1 ? "" : "s"} without any power. Stock is warming.`,
    backup: (n: number) => `Grid lost: the backup generator is carrying ${n} chamber${n === 1 ? "" : "s"}.`,
    board: "Power", grid: "Grid", generator: "Backup generator", chambersOut: "Chambers without power", chambersGen: "On generator",
    hottest: "Hottest chamber", worstRot: "Worst rot risk",
    gridState: { ok: "Online", lost: "Lost" }, genState: { standby: "Standby", running: "Running", failed: "Failed" },
    drills: "Run a drill", target: "Where", whole: "Whole plant",
    gridFail: "Grid failure (generator starts)", total: "Total blackout (generator fails)", flood: "Haor flood upstream", restore: "Restore power",
    playbook: "Response playbook",
    steps: {
      alarm: "Alarm raised on the operator's phone",
      genOk: "Backup generator started on its own", genFailed: "Generator failed: technician called for a manual start", gen: "Backup generator on standby",
      seal: "Doors sealed, air on recirculation to hold the cold",
      notify: (ids: string) => `Bangla voice alert queued for farmers storing in ${ids}`,
      overflow: (name: string, t: string) => `Overflow ready: ${name} has ${t} open with grid power`,
      noOverflow: "No other cold store nearby has open space with power",
      restored: "Power restored; every chamber re-checked",
    },
    floodTitle: "Haor flood alert upstream",
    floodBody: (red: number, trucks: number, open: string) =>
      `${red} haor upazila${red === 1 ? "" : "s"} on RED; ${trucks} early-harvest truck${trucks === 1 ? "" : "s"} dispatched. Boro rice will arrive early: keep the ${open} of open farmer quota for it.`,
    done: "Drill started", restoredToast: "Power restored", failed: "Request failed",
    simulated: "Drills inject a simulated incident (BCSA telemetry is modelled); the response steps are what the operator does.",
  },
  bn: {
    title: "জরুরি নিয়ন্ত্রণ",
    calm: "সব চেম্বার গ্রিডের বিদ্যুতে চলছে। নিচে মহড়া চালিয়ে দেখুন হিমাগার কীভাবে সামলায়।",
    blackout: (n: number) => `জরুরি অবস্থা: ${n}টি চেম্বারে কোনো বিদ্যুৎ নেই। মাল গরম হচ্ছে।`,
    backup: (n: number) => `গ্রিড নেই: ব্যাকআপ জেনারেটর ${n}টি চেম্বার চালাচ্ছে।`,
    board: "বিদ্যুৎ", grid: "গ্রিড", generator: "ব্যাকআপ জেনারেটর", chambersOut: "বিদ্যুৎহীন চেম্বার", chambersGen: "জেনারেটরে",
    hottest: "সবচেয়ে গরম চেম্বার", worstRot: "সর্বোচ্চ পচনের ঝুঁকি",
    gridState: { ok: "চালু", lost: "বন্ধ" }, genState: { standby: "প্রস্তুত", running: "চলছে", failed: "বিকল" },
    drills: "মহড়া চালান", target: "কোথায়", whole: "পুরো হিমাগার",
    gridFail: "গ্রিড বন্ধ (জেনারেটর চালু)", total: "পুরো ব্ল্যাকআউট (জেনারেটর বিকল)", flood: "উজানে হাওর বন্যা", restore: "বিদ্যুৎ ফেরান",
    playbook: "করণীয় তালিকা",
    steps: {
      alarm: "অপারেটরের ফোনে অ্যালার্ম গেছে",
      genOk: "ব্যাকআপ জেনারেটর নিজে চালু হয়েছে", genFailed: "জেনারেটর বিকল: হাতে চালু করতে মেকানিক ডাকা হয়েছে", gen: "ব্যাকআপ জেনারেটর প্রস্তুত",
      seal: "দরজা বন্ধ, ঠান্ডা ধরে রাখতে বাতাস ভেতরেই ঘুরছে",
      notify: (ids: string) => `${ids}-এ মাল রাখা কৃষকদের বাংলায় ফোন-বার্তা পাঠানো হচ্ছে`,
      overflow: (name: string, t: string) => `বিকল্প প্রস্তুত: ${name}-এ বিদ্যুৎসহ ${t} খালি`,
      noOverflow: "কাছে বিদ্যুৎসহ খালি জায়গার অন্য হিমাগার নেই",
      restored: "বিদ্যুৎ ফিরেছে; প্রতিটি চেম্বার আবার পরীক্ষা হয়েছে",
    },
    floodTitle: "উজানে হাওর বন্যার সতর্কতা",
    floodBody: (red: number, trucks: number, open: string) =>
      `${red}টি হাওর উপজেলা লাল সতর্কতায়; ${trucks}টি আগাম ফসল কাটার ট্রাক পাঠানো হয়েছে। বোরো ধান আগে আসবে: কৃষকদের খালি ${open} জায়গা এর জন্য রাখুন।`,
    done: "মহড়া শুরু", restoredToast: "বিদ্যুৎ ফিরেছে", failed: "অনুরোধ ব্যর্থ",
    simulated: "মহড়া একটি সিমুলেটেড ঘটনা যোগ করে (BCSA টেলিমেট্রি মডেল করা); করণীয়গুলো অপারেটরের কাজ।",
  },
};

const mt = (t: number) => `${Math.round(t).toLocaleString("en-IN")} t`;
const FIELD = "min-h-10 w-full rounded-lg bg-white px-3 text-[14px] text-slate-900 ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-sky-600 focus:outline-none";

/**
 * The cold store's incident desk: what is wrong right now (grid, generator, warming chambers), the drills that cause it,
 * and the operator's playbook ticking itself off from the live chamber readings.
 */
export function IncidentControl({ facility, rows, facilities, onChanged }: {
  facility: QuotaFacility;
  rows: ChamberTelemetry[] | undefined;
  facilities: QuotaFacility[];
  onChanged: () => Promise<void>;
}) {
  const c = useCopy(COPY);
  const flood = useAppState((s) => s.floodReport);
  const [target, setTarget] = useState("ALL");
  const [busy, setBusy] = useState<string | null>(null);
  const list = rows ?? [];
  const out = list.filter((t) => t.power_source === "OUTAGE");
  const onGen = list.filter((t) => t.power_source === "DIESEL_GENERATOR" && t.simulated_anomaly_active);
  const incident = out.length > 0 || onGen.length > 0;
  const hottest = list.reduce<ChamberTelemetry | null>((h, t) => (!h || t.temperature_c > h.temperature_c ? t : h), null);
  const worst = list.reduce((m, t) => Math.max(m, t.rot_risk_pct), 0);
  const affected = [...out, ...onGen].map((t) => t.chamber_id);
  const overflow = facilities.filter((f) => f.facility_id !== facility.facility_id && f.power_status !== "OUTAGE" && f.open_smallholder_quota_mt > 0)
    .sort((a, b) => b.open_smallholder_quota_mt - a.open_smallholder_quota_mt)[0];

  const run = async (key: string, action: () => Promise<unknown>, toast: string) => {
    setBusy(key);
    try {
      await action();
      await onChanged();
      pushAlert(key === "restore" ? "success" : "warn", toast);
    } catch (error) {
      pushAlert("danger", c.failed, error instanceof ApiError ? error.message : String(error));
    } finally {
      setBusy(null);
    }
  };
  const cut = (generatorFailed: boolean) => run(generatorFailed ? "total" : "grid",
    () => api.simulatePowerCut(facility.facility_id, { chamberId: target === "ALL" ? undefined : target, generatorFailed }),
    `${c.done}: ${generatorFailed ? c.total : c.gridFail}`);
  const floodDrill = () => run("flood", async () => {
    await api.simulateFlashFlood("Tahirpur");
    setState({ floodReport: await api.sarFloodCheck() });
    void api.voiceInteract({ preset_id: "sunamganj_haor_flood", offline_mode: getState().offlineMode }).then((r) => setState({ lastVoice: r.data }));
  }, `${c.done}: ${c.flood}`);
  const restore = () => run("restore", async () => {
    await api.clearAnomalies();
    setState({ floodReport: null });
  }, c.restoredToast);

  const red = flood?.voice_alerts.filter((a) => a.alert_level === "RED").length ?? 0;
  const gen = out.length ? "failed" : onGen.length ? "running" : "standby";

  return (
    <Panel title={c.title} icon={<Siren className={cn("size-4", incident ? "text-rose-600" : "text-sky-700")} aria-hidden />}
      actions={incident ? <Badge tone={out.length ? "red" : "amber"}>{out.length ? c.genState.failed : c.genState.running}</Badge> : <Badge tone="emerald">{c.gridState.ok}</Badge>}>
      <div role="status" aria-live="polite" className={cn("flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-[14px] font-medium ring-1 ring-inset",
        out.length ? "bg-rose-50 text-rose-800 ring-rose-600/25" : onGen.length ? "bg-amber-50 text-amber-900 ring-amber-600/25" : "bg-emerald-50 text-emerald-900 ring-emerald-700/15")}>
        <span className={cn("size-2.5 shrink-0 rounded-full", out.length ? "animate-pulse-soft bg-rose-600" : onGen.length ? "animate-pulse-soft bg-amber-500" : "bg-emerald-600")} aria-hidden />
        {out.length ? c.blackout(out.length) : onGen.length ? c.backup(onGen.length) : c.calm}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <section aria-label={c.board} className="grid content-start gap-2">
          <h3 className="m-0 text-[13px] font-semibold text-slate-700">{c.board}</h3>
          <PowerRow icon={incident ? <ZapOff className="size-4" /> : <Zap className="size-4" />} label={c.grid}
            value={incident ? c.gridState.lost : c.gridState.ok} tone={incident ? "red" : "emerald"} />
          <PowerRow icon={<PlugZap className="size-4" />} label={c.generator} value={c.genState[gen]}
            tone={gen === "failed" ? "red" : gen === "running" ? "amber" : "slate"} />
          <PowerRow icon={<Power className="size-4" />} label={c.chambersOut} value={`${out.length} / ${list.length || facility.chambers}`} tone={out.length ? "red" : "slate"} />
          <PowerRow icon={<Power className="size-4" />} label={c.chambersGen} value={`${onGen.length}`} tone={onGen.length ? "amber" : "slate"} />
          {hottest && <PowerRow label={c.hottest} value={`${hottest.chamber_id} · ${hottest.temperature_c.toFixed(1)} °C`} tone={hottest.temperature_c > 10 ? "red" : "slate"} />}
          <PowerRow label={c.worstRot} value={`${worst.toFixed(1)}%`} tone={worst > 5 ? "red" : "slate"} />
        </section>

        <section aria-label={c.drills} className="grid content-start gap-2">
          <h3 className="m-0 text-[13px] font-semibold text-slate-700">{c.drills}</h3>
          <label className="grid gap-1 text-[12.5px] font-medium text-slate-700">{c.target}
            <select value={target} onChange={(e) => setTarget(e.target.value)} className={FIELD}>
              <option value="ALL">{c.whole}</option>
              {Array.from({ length: facility.chambers }, (_, i) => `CH-${String(i + 1).padStart(2, "0")}`).map((id) => <option key={id}>{id}</option>)}
            </select>
          </label>
          <Button variant="amber" className="min-h-10 justify-start" disabled={busy !== null} onClick={() => void cut(false)}>
            {busy === "grid" ? <Spinner /> : <ZapOff className="size-4" aria-hidden />} {c.gridFail}
          </Button>
          <Button variant="danger" className="min-h-10 justify-start" disabled={busy !== null} onClick={() => void cut(true)}>
            {busy === "total" ? <Spinner /> : <Siren className="size-4" aria-hidden />} {c.total}
          </Button>
          <Button variant="ghost" className="min-h-10 justify-start" disabled={busy !== null} onClick={() => void floodDrill()}>
            {busy === "flood" ? <Spinner /> : <CloudRain className="size-4 text-sky-700" aria-hidden />} {c.flood}
          </Button>
          <Button variant="primary" className="min-h-10 justify-start" disabled={busy !== null} onClick={() => void restore()}>
            {busy === "restore" ? <Spinner /> : <RotateCcw className="size-4" aria-hidden />} {c.restore}
          </Button>
        </section>

        <section aria-label={c.playbook} className="grid content-start gap-2">
          <h3 className="m-0 text-[13px] font-semibold text-slate-700">{c.playbook}</h3>
          <ol className="m-0 grid list-none gap-1.5 p-0 text-[13px]">
            <Step done={incident}>{c.steps.alarm}</Step>
            <Step done={incident} bad={out.length > 0}>{out.length ? c.steps.genFailed : onGen.length ? c.steps.genOk : c.steps.gen}</Step>
            <Step done={incident}>{c.steps.seal}</Step>
            <Step done={incident}>{c.steps.notify(affected.length ? affected.join(", ") : "-")}</Step>
            <Step done={incident && overflow !== undefined} bad={incident && overflow === undefined}>
              {overflow ? c.steps.overflow(overflow.name, mt(overflow.open_smallholder_quota_mt)) : c.steps.noOverflow}
            </Step>
            <Step done={!incident}>{c.steps.restored}</Step>
          </ol>
        </section>
      </div>

      {flood && (
        <div className="mt-4 flex gap-2.5 rounded-xl bg-sky-50 px-3 py-2.5 text-[13px] text-sky-900 ring-1 ring-inset ring-sky-600/20">
          <CloudRain className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span><span className="font-semibold">{c.floodTitle}.</span> {c.floodBody(red, flood.early_harvest_dispatches.length, mt(facility.open_smallholder_quota_mt))}</span>
        </div>
      )}
      <p className="m-0 mt-3 text-[12px] text-slate-500">{c.simulated}</p>
    </Panel>
  );
}

function PowerRow({ icon, label, value, tone }: { icon?: ReactNode; label: string; value: string; tone: "red" | "amber" | "emerald" | "slate" }) {
  return (
    <div className="flex items-center justify-between gap-2 rounded-lg bg-slate-50 px-3 py-2 ring-1 ring-inset ring-slate-200">
      <span className="flex min-w-0 items-center gap-2 text-[13px] text-slate-700">{icon && <span className="text-slate-500" aria-hidden>{icon}</span>}{label}</span>
      <Badge tone={tone === "red" ? "red" : tone}>{value}</Badge>
    </div>
  );
}

function Step({ done, bad, children }: { done: boolean; bad?: boolean; children: ReactNode }) {
  return (
    <li className={cn("flex gap-2 rounded-lg px-2 py-1.5", bad ? "bg-rose-50 text-rose-800" : done ? "text-slate-800" : "text-slate-500")}>
      {done && !bad ? <CircleCheck className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden />
        : <CircleDashed className={cn("mt-0.5 size-4 shrink-0", bad ? "text-rose-600" : "text-slate-400")} aria-hidden />}
      <span>{children}</span>
    </li>
  );
}
