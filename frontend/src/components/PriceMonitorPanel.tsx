import { TrendingUp } from "lucide-react";
import { useEffect, useState } from "react";

import { api, ApiError, type PriceMonitorReport } from "../api/client";
import { cn, tk } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { Badge, Panel, Spinner } from "./ui";

const COPY = {
  en: {
    title: "Staple price monitor",
    division: "Division",
    th: { staple: "Staple", latest: "Latest", m1: "1 month", m12: "12 months", ahead: "Next 3 months (forecast)" },
    staples: { "Rice (coarse)": "Coarse rice", "Wheat flour": "Wheat flour", "Lentils (masur)": "Masur lentils", "Oil (palm)": "Palm oil" } as Record<string, string>,
    score: (model: string, chosen: number, naive: number) =>
      `Forecast model: ${model}, chosen on the validation year. On the held-out test year its error (sMAPE ${chosen}) was ` +
      (chosen < naive ? `lower than assuming no change (${naive}).` : `higher than assuming no change (${naive}), so treat it as indicative only.`),
    margins: "Dhaka retail margin over wholesale: latest flagged months",
    margin: "margin",
    source: "Data",
    through: "through",
    failed: "Price monitor unavailable",
  },
  bn: {
    title: "প্রধান খাদ্যপণ্যের দাম মনিটর",
    division: "বিভাগ",
    th: { staple: "পণ্য", latest: "সর্বশেষ", m1: "১ মাসে", m12: "১২ মাসে", ahead: "আগামী ৩ মাস (পূর্বাভাস)" },
    staples: { "Rice (coarse)": "মোটা চাল", "Wheat flour": "আটা", "Lentils (masur)": "মসুর ডাল", "Oil (palm)": "পাম তেল" } as Record<string, string>,
    score: (model: string, chosen: number, naive: number) =>
      `পূর্বাভাস মডেল: ${model}, যাচাই-বছরে বাছাই করা। পরীক্ষার বছরে এর ভুল (sMAPE ${chosen}) ` +
      (chosen < naive ? `"দাম বদলাবে না" ধরে নেওয়ার (${naive}) চেয়ে কম।` : `"দাম বদলাবে না" ধরে নেওয়ার (${naive}) চেয়ে বেশি, তাই এটি শুধু ইঙ্গিত হিসেবে দেখুন।`),
    margins: "ঢাকায় পাইকারির ওপর খুচরা মার্জিন: সর্বশেষ চিহ্নিত মাস",
    margin: "মার্জিন",
    source: "তথ্য",
    through: "পর্যন্ত",
    failed: "দাম মনিটর পাওয়া যাচ্ছে না",
  },
};

const pct = (value: number | null) => value === null ? "-" : `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;

/** WFP staple prices with the krishi-price-v1 forecast, shown beside its measured test score (backend/price_monitor.py). */
export function PriceMonitorPanel({ className }: { className?: string }) {
  const c = useCopy(COPY);
  const [division, setDivision] = useState("Dhaka");
  const [report, setReport] = useState<PriceMonitorReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setError(null);
    api.priceMonitor(division)
      .then((r) => { if (live) setReport(r); })
      .catch((e) => { if (live) setError(e instanceof ApiError ? e.message : String(e)); });
    return () => { live = false; };
  }, [division]);

  const select = report?.divisions.length ? (
    <label className="flex items-center gap-2 text-[13px] text-slate-600">
      {c.division}
      <select value={division} onChange={(e) => setDivision(e.target.value)}
        className="min-h-9 rounded-md bg-white px-2 text-[13px] text-slate-900 ring-1 ring-inset ring-slate-300">
        {report.divisions.map((d) => <option key={d} value={d}>{d}</option>)}
      </select>
    </label>
  ) : null;

  return (
    <Panel className={className} icon={<TrendingUp className="size-4 text-emerald-700" aria-hidden />} title={c.title} actions={select}
      bodyClassName="space-y-3">
      {error && <p className="m-0 text-[13px] text-rose-600">{c.failed}: {error}</p>}
      {!report && !error && <div className="py-6 text-center"><Spinner /></div>}
      {report?.status === "not_installed" && <p className="m-0 text-[13px] text-slate-600">{report.note}</p>}
      {report?.status === "installed" && (
        <>
          <div className="scroll-thin overflow-x-auto">
            <table className="w-full min-w-[620px] text-left text-[13px]">
              <thead className="text-[12px] text-slate-500">
                <tr><th className="py-2 pr-3 font-medium">{c.th.staple}</th><th className="pr-3 font-medium">{c.th.latest}</th>
                  <th className="pr-3 font-medium">{c.th.m1}</th><th className="pr-3 font-medium">{c.th.m12}</th><th className="font-medium">{c.th.ahead}</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {report.series.map((s) => (
                  <tr key={s.key}>
                    <td className="py-2 pr-3 text-slate-900">{c.staples[s.staple] ?? s.staple}</td>
                    <td className="num pr-3 text-slate-900">{tk(s.last_price_tk)}/{s.unit === "L" ? "L" : "kg"} <span className="text-[12px] text-slate-500">{s.last_month}</span></td>
                    <td className={cn("num pr-3", (s.change_1m_pct ?? 0) > 0 ? "text-rose-700" : "text-slate-700")}>{pct(s.change_1m_pct)}</td>
                    <td className={cn("num pr-3", (s.change_12m_pct ?? 0) > 0 ? "text-rose-700" : "text-slate-700")}>{pct(s.change_12m_pct)}</td>
                    <td className="num text-slate-700">{s.forecast.map((f) => `${f.month.slice(5)}: ${tk(f.price_tk)}`).join(" · ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {report.test_mean_smape && report.model_chosen_on_validation && (
            <p className={cn("m-0 rounded-md px-3 py-2 text-[12.5px]", report.test_mean_smape.chosen < report.test_mean_smape.naive
              ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-900")}>
              {c.score(report.model_chosen_on_validation, report.test_mean_smape.chosen, report.test_mean_smape.naive)}
            </p>
          )}
          {report.margin_flags.length > 0 && (
            <div>
              <div className="mb-1 text-[12px] font-medium text-slate-500">{c.margins}</div>
              <div className="flex flex-wrap gap-1.5">
                {report.margin_flags.map((f) => (
                  <Badge key={`${f.series}-${f.month}`} tone={f.reported_window ? "red" : "slate"}>
                    {f.month} · {f.series.replace("_", " ")} · {c.margin} {f.margin_pct}%{f.z !== null ? ` · z ${f.z}` : ""}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          {report.source && (
            <p className="m-0 text-[11.5px] text-slate-500">
              {c.source}: {report.source.name}, {report.source.licence}, {c.through} {report.data_through}
            </p>
          )}
        </>
      )}
    </Panel>
  );
}
