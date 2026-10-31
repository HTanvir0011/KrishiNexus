import { Banknote, Building2, Fingerprint, Landmark, Lock, Satellite, ShieldCheck, Truck } from "lucide-react";
import { useMemo, useState } from "react";

import { api, ApiError, type PoolView } from "../api/client";
import { ScoreDial } from "../components/gauges";
import { Badge, Button, Panel, ProgressBar, Spinner } from "../components/ui";
import { cn, kg, shortHash, tk } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { pushAlert, refreshPools, setState, useAppState } from "../state/store";

const COPY = {
  en: {
    loadsTitle: "Pre-graded 5-ton truckloads for buyers",
    network: "7 arats · 3 retail DCs · 66 WFP centres (62 Cox's Bazar · 4 Kurigram)",
    th: { load: "Load", crop: "Crop and quality", fill: "Fill", buyer: "Buyer", contract: "Contract", escrow: "Escrow" },
    gradeA: "Grade-A",
    farmers: "farmers",
    forming: "Forming",
    eta: "ETA",
    open: "Open",
    creditTitle: "Agri-credit underwriting",
    underwrite: "Underwrite FARM-BOG-104",
    underwriteFailed: "Underwriting failed",
    verifyFailed: "Certificate check failed",
    empty: "Run a farmer question, or underwrite the sample farmer, to score a borrower.",
    notEligible: "Not eligible",
    perYear: "a year",
    months: "months",
    ltvLabel: "Loan-to-value",
    band: "band for scores ≥",
    collateral: "collateral =",
    cappedAt: "capped at",
    rounded: "and rounded down to Tk 500.",
    breach: "breach",
    clearance: "72 h clearance",
    mmRain: "mm rain",
    stormWarning: "72 h storm warning",
    cert: "Quality certificate",
    notIssued: "not issued",
    verifyHmac: "Verify HMAC",
    issuedBy: "issued by this edge node",
    unknownNode: "unknown to this node",
    payloadHash: "payload hash",
    signature: "signature",
    valid: "valid",
    invalid: "invalid",
    tampered: " · tampered",
    scanHint: "Scan a harvest on the farmer's phone, or underwrite the sample farmer, to issue a certificate.",
  },
  bn: {
    loadsTitle: "ক্রেতাদের জন্য প্রি-গ্রেডেড 5-টন ট্রাকলোড",
    network: "7 আড়ত · 3 রিটেইল ডিসি · 66 WFP কেন্দ্র (কক্সবাজার 62 · কুড়িগ্রাম 4)",
    th: { load: "লোড", crop: "ফসল ও মান", fill: "ভরাট", buyer: "ক্রেতা", contract: "চুক্তি", escrow: "এসক্রো" },
    gradeA: "গ্রেড-A",
    farmers: "জন কৃষক",
    forming: "গঠিত হচ্ছে",
    eta: "ইটিএ",
    open: "খোলা",
    creditTitle: "কৃষি-ঋণ আন্ডাররাইটিং",
    underwrite: "আন্ডাররাইট FARM-BOG-104",
    underwriteFailed: "আন্ডাররাইটিং ব্যর্থ হয়েছে",
    verifyFailed: "সার্টিফিকেট যাচাই ব্যর্থ হয়েছে",
    empty: "ঋণগ্রহীতার স্কোর দেখতে কৃষকের একটি প্রশ্ন চালান, বা নমুনা কৃষককে আন্ডাররাইট করুন।",
    notEligible: "ঋণের যোগ্য নয়",
    perYear: "বার্ষিক",
    months: "মাস",
    ltvLabel: "লোন-টু-ভ্যালু",
    band: "ব্যান্ড, স্কোর ≥",
    collateral: "জামানত =",
    cappedAt: "সর্বোচ্চ",
    rounded: "এবং ৳500-তে নামিয়ে রাউন্ড করা হয়।",
    breach: "ভাঙনের ঝুঁকি",
    clearance: "72 h ক্লিয়ারেন্স",
    mmRain: "mm বৃষ্টি",
    stormWarning: "72 h ঝড়ের সতর্কতা",
    cert: "কোয়ালিটি সার্টিফিকেট",
    notIssued: "ইস্যু হয়নি",
    verifyHmac: "HMAC যাচাই",
    issuedBy: "এই এজ নোড থেকেই ইস্যু করা",
    unknownNode: "এই নোডের অজানা",
    payloadHash: "পেলোড হ্যাশ",
    signature: "স্বাক্ষর",
    valid: "বৈধ",
    invalid: "অবৈধ",
    tampered: " · টেম্পার করা",
    scanHint: "সার্টিফিকেট পেতে কৃষকের ফোনে ফসল স্ক্যান করুন, বা নমুনা কৃষককে আন্ডাররাইট করুন।",
  },
};

/** Agent 4's loan-to-value bands (`backend/agents/climate_credit_agent._ltv_for`); shown here to explain the loan. */
const LTV_BANDS: { min: number; ltv: number }[] = [{ min: 750, ltv: 0.6 }, { min: 700, ltv: 0.5 }, { min: 650, ltv: 0.4 }];
const LOAN_CAP_TK = 50_000;

function gradeMix(pool: PoolView, gradeA: string): string {
  const a = pool.lots.filter((l) => l.grade === "A").reduce((s, l) => s + l.weight_kg, 0);
  return `${Math.round((a / Math.max(1, pool.loaded_kg)) * 100)}% ${gradeA}`;
}

type Verification = { cert_id: string; known: boolean; payload_hash_valid: boolean; signature_valid: boolean; tampered: boolean };

export function BuyerBankPortal({ className }: { className?: string }) {
  const c = useCopy(COPY);
  const pools = useAppState((s) => s.pools);
  const voice = useAppState((s) => s.lastVoice);
  const grade = useAppState((s) => s.lastGrade);
  const [busy, setBusy] = useState<"underwrite" | "verify" | null>(null);
  const [verification, setVerification] = useState<Verification | null>(null);
  const state = voice?.orchestration?.state;
  const credit = state?.climate_credit_report;
  const cert = state?.optical_grade_cert;
  const syn = state?.syndicate_bypass_plan;
  const cold = state?.cold_storage_arbitrage_plan;
  const loads = useMemo(() => [...pools].sort((a, b) => Number(b.status === "DISPATCHED") - Number(a.status === "DISPATCHED") || b.fill_pct - a.fill_pct), [pools]);
  const certId = cert?.edge_certificate_id ?? grade?.digital_certificate.cert_id ?? null;

  const ltv = credit ? LTV_BANDS.find((b) => credit.credit_score >= b.min)?.ltv ?? 0 : 0;
  const receipt = cold?.reservation?.receipt_id ? cold : null;
  const collateralValue = receipt && state
    ? state.quantity_kg * (1 - (receipt.lambda_rot ?? 0.012)) * (receipt.expected_future_price_tk_per_kg ?? 0)
    : syn?.lot_value_b2b_tk ?? null;

  const underwrite = async () => {
    setBusy("underwrite");
    setVerification(null);
    try {
      const result = await api.voiceInteract({
        text: "আমার কাছে ৪০০ কেজি কার্ডিনাল আলু আছে, ফড়িয়া ১১ টাকা কেজি বলছে। আমার ফোন 01711223344",
        district: "Bogura", upazila: "Shibganj", farmer_id: "FARM-BOG-104", grade_sample_preset: "high_grade_harvest",
      });
      setState({ lastVoice: result.data });
      await refreshPools();
    } catch (error) {
      pushAlert("danger", c.underwriteFailed, error instanceof ApiError ? error.message : String(error));
    } finally {
      setBusy(null);
    }
  };

  const verify = async () => {
    if (!certId) return;
    setBusy("verify");
    try {
      setVerification(await api.verifyCertificate(certId));
    } catch (error) {
      pushAlert("danger", c.verifyFailed, error instanceof ApiError ? error.message : String(error));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className={cn("grid min-w-0 gap-4 xl:grid-cols-5", className)}>
      <Panel className="xl:col-span-3" icon={<Truck className="size-4 text-amber-600" aria-hidden />} title={c.loadsTitle}
        actions={<Badge tone="slate" className="whitespace-normal"><Building2 className="size-3 shrink-0" aria-hidden /> {c.network}</Badge>}
        bodyClassName="scroll-thin overflow-x-auto p-0">
        <table className="w-full min-w-[640px] text-left text-[13px]">
          <thead className="bg-slate-50 text-[12px] text-slate-500">
            <tr>
              <th className="px-4 py-2.5 font-medium">{c.th.load}</th><th className="px-2 font-medium">{c.th.crop}</th><th className="px-2 font-medium">{c.th.fill}</th>
              <th className="px-2 font-medium">{c.th.buyer}</th><th className="px-2 font-medium">{c.th.contract}</th><th className="px-4 font-medium">{c.th.escrow}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {loads.map((p) => (
              <tr key={p.pool_id} className="align-top hover:bg-slate-50/70">
                <td className="px-4 py-3">
                  <div className="font-mono text-[12.5px] font-semibold text-slate-900">{p.pool_id}</div>
                  <div className="text-[12px] text-slate-500">{p.union}, {p.upazila}</div>
                </td>
                <td className="px-2 py-3"><div className="text-slate-900">{p.crop}</div><div className="text-[12px] text-emerald-700">{gradeMix(p, c.gradeA)} · {p.smallholders} {c.farmers}</div></td>
                <td className="w-32 px-2 py-3"><div className="num mb-1 text-[14px] text-slate-900">{kg(p.loaded_kg)}</div><ProgressBar value={p.loaded_kg} max={p.capacity_kg} tone={p.status === "DISPATCHED" ? "amber" : "emerald"} /></td>
                <td className="px-2 py-3">{p.dispatch ? <><div className="text-slate-900">{p.dispatch.buyer_name}</div><div className="text-[12px] text-slate-500">{p.dispatch.buyer_type} · {c.eta} {p.dispatch.eta_hours.toFixed(1)} h</div></> : <span className="text-slate-500">{c.forming}</span>}</td>
                <td className="num px-2 py-3 text-[14px] text-slate-900">{p.dispatch ? <>{tk(p.dispatch.contract_price_tk_per_kg)}/kg<div className="text-[12px] font-normal text-slate-500">{tk(p.dispatch.contract_value_tk, 0)}</div></> : "-"}</td>
                <td className="px-4 py-3">{p.dispatch ? <Badge tone="amber"><Lock className="size-3" aria-hidden /> {p.dispatch.escrow_id}</Badge> : <Badge tone="slate">{c.open}</Badge>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <Panel className="xl:col-span-2" icon={<Landmark className="size-4 text-violet-600" aria-hidden />} title={c.creditTitle}
        actions={<Button onClick={() => void underwrite()} disabled={busy !== null}>{busy === "underwrite" ? <Spinner /> : <Banknote className="size-4" aria-hidden />} {c.underwrite}</Button>}
        bodyClassName="space-y-4">
        {!credit ? (
          <p className="m-0 py-10 text-center text-[13px] text-slate-500">{c.empty}</p>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-4">
              <ScoreDial score={credit.credit_score} className="w-full max-w-[220px]" />
              <div className="min-w-0 space-y-1">
                <Badge tone={credit.loan_eligible ? "emerald" : "red"} className="text-[13px]">{credit.score_band}</Badge>
                <div className="num text-[28px] leading-tight text-slate-900">{credit.loan_eligible ? tk(credit.loan_amount_tk, 0) : c.notEligible}</div>
                <div className="text-[13px] text-slate-600">{credit.annual_rate_pct}% {c.perYear} · {credit.tenor_months} {c.months} · {state?.farmer_id}</div>
              </div>
            </div>

            {credit.loan_eligible && collateralValue !== null && (
              <div className="rounded-lg bg-slate-50 p-3 text-[13px] ring-1 ring-inset ring-slate-200">
                <div className="mb-1 text-[12px] font-medium text-slate-500">{c.ltvLabel}</div>
                <div className="num text-slate-900">
                  {Math.round(ltv * 100)}% × {tk(collateralValue, 0)} = {tk(ltv * collateralValue, 0)} → {tk(credit.loan_amount_tk, 0)}
                </div>
                <div className="mt-1 text-[12px] text-slate-500">
                  {ltv * 100}% {c.band} {LTV_BANDS.find((b) => b.ltv === ltv)?.min}, {c.collateral} {credit.collateral}; {c.cappedAt} {tk(LOAN_CAP_TK, 0)} {c.rounded}
                </div>
              </div>
            )}

            <div className="space-y-2">
              {credit.score_components.map((c) => (
                <div key={c.name}>
                  <div className="flex justify-between text-[12.5px]"><span className="text-slate-700">{c.name}</span><span className="num text-slate-900">{c.points.toFixed(0)}/{c.max_points}</span></div>
                  <ProgressBar value={c.points} max={c.max_points} tone="violet" className="h-1.5" />
                  <div className="truncate text-[11.5px] text-slate-500">{c.evidence}</div>
                </div>
              ))}
            </div>

            <div className="flex flex-wrap gap-2">
              <Badge tone={credit.seventy_two_hour_clearance ? "emerald" : "red"}>
                <Satellite className="size-3" aria-hidden />
                {credit.flood_applicable
                  ? `SAR ${credit.sar_backscatter_db} dB · ${c.breach} ${credit.flood_breach_probability_pct}% (${credit.flood_alert_level?.toLowerCase()})`
                  : credit.seventy_two_hour_clearance ? `${c.clearance} · ${credit.rain_next_72h_mm} ${c.mmRain}` : c.stormWarning}
              </Badge>
              <Badge tone="sky"><ShieldCheck className="size-3" aria-hidden /> {cold?.reservation?.receipt_id ?? credit.collateral}</Badge>
            </div>

            <div className="rounded-lg bg-white p-3 ring-1 ring-inset ring-slate-200">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-1.5 text-[13px] text-slate-700">
                  <Fingerprint className="size-4 text-emerald-700" aria-hidden />
                  <span className="truncate">{c.cert} {cert ? `${cert.grade} · sha256 ${shortHash(cert.sha256_digest, 10)}` : c.notIssued}</span>
                </div>
                <Button onClick={() => void verify()} disabled={!certId || busy !== null}>
                  {busy === "verify" ? <Spinner /> : <ShieldCheck className="size-4" aria-hidden />} {c.verifyHmac}
                </Button>
              </div>
              {verification && (
                <div className={cn("mt-2 rounded-md px-2.5 py-1.5 text-[12.5px]",
                  verification.signature_valid && verification.payload_hash_valid && !verification.tampered ? "bg-emerald-50 text-emerald-800" : "bg-rose-100/70 text-rose-700")}>
                  {verification.cert_id}: {verification.known ? c.issuedBy : c.unknownNode} · {c.payloadHash} {verification.payload_hash_valid ? c.valid : c.invalid} · {c.signature} {verification.signature_valid ? c.valid : c.invalid}{verification.tampered ? c.tampered : ""}
                </div>
              )}
              {!certId && <p className="m-0 mt-1 text-[12px] text-slate-500">{c.scanHint}</p>}
            </div>
            <p className="m-0 text-[11.5px] text-slate-500">{credit.lender_model}</p>
          </>
        )}
      </Panel>
    </div>
  );
}
