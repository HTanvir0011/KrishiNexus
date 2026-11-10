import { HandCoins, Lock } from "lucide-react";
import { useEffect, useState } from "react";

import { api, ApiError, type BidBoard, type Crop, type EscrowReceipt, type HubType, type LotGrade, type Wallet } from "../api/client";
import { cn, kg, tk } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { useAppState } from "../state/store";
import { Badge, Button, Panel, Segmented, Spinner } from "./ui";

const CROPS: Crop[] = ["Cardinal Potato", "Diamant Potato", "Green Chili", "Brinjal", "Boro Rice"];
const DISTRICTS = ["Bogura", "Munshiganj", "Rangpur", "Thakurgaon", "Jessore", "Kurigram", "Kishoreganj", "Sunamganj"];

const COPY = {
  en: {
    title: "Buyer bids for this lot",
    crop: "Crop",
    district: "From",
    weight: "kg",
    grade: "Grade",
    th: { rank: "#", buyer: "Buyer", bid: "Bid", transport: "Transport", net: "Net to farmer", total: "Lot total" },
    types: { URBAN_RETAIL_CHAIN: "Supermarket DC", WHOLESALE_ARAT: "Wholesale arat", WFP_AGGREGATION_CENTRE: "WFP centre", AGRO_PROCESSOR: "Agro-processor" } as Record<HubType, string>,
    best: "Best",
    belowFloor: "below cost",
    none: "No buyer bids on this crop and grade today.",
    wallet: "Pay into",
    number: "Wallet number",
    lock: (total: string) => `Lock best bid · ${total}`,
    held: "Held in escrow",
    simulated: "simulated",
    validUntil: "Bids valid until",
    failed: "Bids unavailable",
    lockFailed: "Could not lock the bid",
  },
  bn: {
    title: "এই লটের জন্য ক্রেতাদের দর",
    crop: "ফসল",
    district: "কোথা থেকে",
    weight: "কেজি",
    grade: "গ্রেড",
    th: { rank: "#", buyer: "ক্রেতা", bid: "দর", transport: "পরিবহন", net: "কৃষক পাবেন", total: "মোট" },
    types: { URBAN_RETAIL_CHAIN: "সুপারশপ ডিসি", WHOLESALE_ARAT: "পাইকারি আড়ত", WFP_AGGREGATION_CENTRE: "WFP কেন্দ্র", AGRO_PROCESSOR: "প্রক্রিয়াজাতকারী" } as Record<HubType, string>,
    best: "সেরা",
    belowFloor: "খরচের নিচে",
    none: "আজ এই ফসল ও গ্রেডে কোনো ক্রেতা দর দিচ্ছে না।",
    wallet: "টাকা যাবে",
    number: "ওয়ালেট নম্বর",
    lock: (total: string) => `সেরা দর লক করুন · ${total}`,
    held: "এসক্রোতে জমা",
    simulated: "সিমুলেটেড",
    validUntil: "দর বহাল থাকবে",
    failed: "দর পাওয়া যাচ্ছে না",
    lockFailed: "দর লক করা গেল না",
  },
};

const GRADES: { value: LotGrade; label: string }[] = [{ value: "A", label: "A" }, { value: "B", label: "B" }, { value: "C", label: "C" }];
const WALLETS: { value: Wallet; label: string }[] = [{ value: "bKash", label: "bKash" }, { value: "Nagad", label: "Nagad" }];

/** Modelled buyer bids ranked by net payout after transport, and a 1-tap lock into a simulated escrow (backend/market_bids.py). */
export function BuyerBidsPanel({ className }: { className?: string }) {
  const c = useCopy(COPY);
  const plan = useAppState((s) => s.lastVoice?.orchestration?.state);
  const [crop, setCrop] = useState<Crop>(plan?.crop ?? "Cardinal Potato");
  const [district, setDistrict] = useState(plan?.district && DISTRICTS.includes(plan.district) ? plan.district : "Bogura");
  const [weightKg, setWeightKg] = useState(plan?.quantity_kg ? Math.round(plan.quantity_kg) : 400);
  const [grade, setGrade] = useState<LotGrade>(plan?.optical_grade_cert?.market_grade ?? "B");
  const [wallet, setWallet] = useState<Wallet>("bKash");
  const [number, setNumber] = useState("01711223344");
  const [board, setBoard] = useState<BidBoard | null>(null);
  const [receipt, setReceipt] = useState<EscrowReceipt | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setError(null);
    setReceipt(null);
    api.marketBids(crop, district, weightKg, grade)
      .then((b) => { if (live) setBoard(b); })
      .catch((e) => { if (live) { setBoard(null); setError(e instanceof ApiError ? e.message : String(e)); } });
    return () => { live = false; };
  }, [crop, district, weightKg, grade]);

  const best = board?.bids[0];
  const lock = async () => {
    if (!best) return;
    setBusy(true);
    setError(null);
    try {
      setReceipt(await api.lockBid({ crop, origin_district: district, weight_kg: weightKg, grade, hub_id: best.hub_id, wallet,
                                     wallet_number: number.trim(), farmer_id: plan?.farmer_id ?? "FARM-BOG-104" }));
    } catch (e) {
      setError(`${c.lockFailed}: ${e instanceof ApiError ? e.message : String(e)}`);
    } finally {
      setBusy(false);
    }
  };

  const field = "rounded-md bg-white px-2 py-1 text-[13px] text-slate-900 ring-1 ring-inset ring-slate-300";
  return (
    <Panel className={className} icon={<HandCoins className="size-4 text-emerald-700" aria-hidden />} title={c.title}
      actions={
        <div className="flex flex-wrap items-center gap-2 text-[13px] text-slate-600">
          <label className="flex items-center gap-1.5">{c.crop}
            <select className={field} value={crop} onChange={(e) => setCrop(e.target.value as Crop)}>{CROPS.map((v) => <option key={v}>{v}</option>)}</select>
          </label>
          <label className="flex items-center gap-1.5">{c.district}
            <select className={field} value={district} onChange={(e) => setDistrict(e.target.value)}>{DISTRICTS.map((v) => <option key={v}>{v}</option>)}</select>
          </label>
          <label className="flex items-center gap-1.5">
            <input className={cn(field, "num w-20")} type="number" min={50} max={20000} step={50} value={weightKg}
              onChange={(e) => setWeightKg(Math.max(50, Number(e.target.value) || 50))} />{c.weight}
          </label>
          <Segmented label={c.grade} value={grade} options={GRADES} onChange={setGrade} />
        </div>}
      bodyClassName="space-y-3 p-0">
      {error && <p role="alert" className="m-0 px-4 pt-3 text-[13px] text-rose-600">{error}</p>}
      {!board && !error && <div className="grid place-items-center py-10"><Spinner /></div>}
      {board && board.bids.length === 0 && <p className="m-0 py-8 text-center text-[13px] text-slate-500">{c.none}</p>}
      {board && board.bids.length > 0 && (
        <div className="scroll-thin overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-[13px]">
            <thead className="bg-slate-50 text-[12px] text-slate-500">
              <tr>
                <th className="px-4 py-2.5 font-medium">{c.th.rank}</th><th className="px-2 font-medium">{c.th.buyer}</th>
                <th className="px-2 font-medium">{c.th.bid}</th><th className="px-2 font-medium">{c.th.transport}</th>
                <th className="px-2 font-medium">{c.th.net}</th><th className="px-4 font-medium">{c.th.total}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {board.bids.slice(0, 6).map((b) => (
                <tr key={b.bid_id} className={b.rank === 1 ? "bg-emerald-50/60" : undefined}>
                  <td className="num px-4 py-2.5 text-slate-500">{b.rank}</td>
                  <td className="px-2 py-2.5">
                    <div className="text-slate-900">{b.hub_name}</div>
                    <div className="flex flex-wrap items-center gap-1.5 text-[12px] text-slate-500">
                      <Badge tone={b.hub_type === "AGRO_PROCESSOR" ? "violet" : b.hub_type === "WFP_AGGREGATION_CENTRE" ? "sky" : "slate"}>{c.types[b.hub_type]}</Badge>
                      {b.district} · {b.road_distance_km.toFixed(0)} km
                      {b.rank === 1 && <Badge tone="emerald">{c.best}</Badge>}
                      {b.below_cost_floor && <Badge tone="red">{c.belowFloor}</Badge>}
                    </div>
                  </td>
                  <td className="num px-2 py-2.5 text-slate-700">{tk(b.hub_price_tk_per_kg)}</td>
                  <td className="num px-2 py-2.5 text-slate-700">−{tk(b.transport_cost_tk_per_kg)}</td>
                  <td className="num px-2 py-2.5 text-[14px] text-slate-900">{tk(b.net_payout_tk_per_kg)}/kg</td>
                  <td className="num px-4 py-2.5 text-slate-900">{tk(b.net_payout_total_tk, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {board && best && (
        <div className="flex flex-wrap items-center gap-3 px-4 pb-1">
          <span className="text-[13px] text-slate-600">{c.wallet}</span>
          <Segmented label={c.wallet} value={wallet} options={WALLETS} onChange={setWallet} />
          <label className="flex items-center gap-1.5 text-[13px] text-slate-600">{c.number}
            <input className={cn(field, "num w-36")} inputMode="tel" value={number} onChange={(e) => setNumber(e.target.value)} />
          </label>
          <Button variant="primary" onClick={() => void lock()} disabled={busy || receipt !== null}>
            {busy ? <Spinner /> : <Lock className="size-4" aria-hidden />} {c.lock(tk(best.net_payout_total_tk, 0))}
          </Button>
        </div>
      )}
      {receipt && (
        <div role="status" className="mx-4 rounded-lg bg-emerald-50 p-3 text-[13px] text-emerald-900 ring-1 ring-inset ring-emerald-700/25">
          <div className="flex flex-wrap items-center gap-2 font-semibold">
            <Lock className="size-4" aria-hidden /> {c.held}: {tk(receipt.amount_tk, 0)} · {receipt.wallet} {receipt.wallet_masked}
            <Badge tone="amber">{c.simulated}</Badge>
          </div>
          <div className="mt-1 text-[12.5px]">
            <span className="font-mono">{receipt.escrow_id}</span> · {receipt.buyer_name} · {kg(receipt.weight_kg)} · {receipt.release_condition}
          </div>
          <div className="mt-1 text-[12px] text-emerald-800/80">{receipt.note}</div>
        </div>
      )}
      {board && (
        <p className="m-0 px-4 pb-3 text-[11.5px] text-slate-500">
          {board.note} {c.validUntil} {new Date(board.valid_until).toLocaleString()}.
        </p>
      )}
    </Panel>
  );
}
