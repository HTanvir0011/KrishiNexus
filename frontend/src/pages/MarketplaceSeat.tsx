import { BadgeCheck, Gavel, HandCoins, PackagePlus, ShieldAlert, Truck, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";

import { api, ApiError, type Crop, type MarketBid, type MarketLot, type Wallet } from "../api/client";
import { DisputeBox } from "../components/DisputeBox";
import { RouteSteps } from "../components/RouteSteps";
import { Badge, Button, Panel, Spinner } from "../components/ui";
import { cn, tk } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { useBecame, useFreshIds } from "../lib/motion";
import { pushAlert, useAppState } from "../state/store";

const CROPS: Crop[] = ["Cardinal Potato", "Diamant Potato", "Green Chili", "Brinjal", "Boro Rice"];
const FIELD = "min-h-10 w-full rounded-lg bg-white px-3 text-[14px] text-slate-900 ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-emerald-700 focus:outline-none";
const STATUS_TONE = { OPEN: "emerald", SOLD: "amber", IN_TRANSIT: "sky", DELIVERED: "slate", CANCELLED: "red" } as const;

const COPY = {
  en: {
    sellTitle: "Sell your harvest directly", sellLede: "List a lot; buyers and traders bid against each other in the open. You choose, and the money is held in escrow until delivery.",
    crop: "Crop", grade: "Grade", kg: "Quantity (kg)", district: "District", upazila: "Upazila (optional)", asking: "Asking price, Tk/kg (optional)",
    note: "Note for buyers (optional)", list: "List for bids", listed: "Lot listed",
    myLots: "My lots", openLots: "Lots open for bids", myBuys: "My purchases", allLots: "All lots",
    none: "Nothing here yet.", bids: "Bids", noBids: "No bids yet.", asking2: "asking", floor: "cost floor",
    accept: "Accept", cancel: "Cancel lot", cancelled: "Lot cancelled", wallet: "Wallet", walletNo: "Wallet number",
    confirmAccept: "Accept and hold payment", belowFloor: (floor: number) => `This bid is below the Tk ${floor}/kg production cost. Sell at a loss anyway?`,
    sold: "Sold: payment held in escrow", yourBid: "Your bid", bidPrice: "Your price, Tk/kg", placeBid: "Place bid", raise: "Raise bid", bidPlaced: "Bid placed",
    highest: "Highest bid", escrowHeld: "Payment held", escrowRefunded: "Refunded to the buyer", you: "You", top: "Highest", earlier: (n: number) => `Earlier bids (${n})`,
    leading: (p: number) => `You lead at Tk ${p}/kg.`, outbid: (top: number, mine: number) => `Outbid: the highest is Tk ${top}/kg, yours Tk ${mine}/kg.`,
    first: "No bids yet: yours will be the first.", total: (tk: string, kg: number) => `= ${tk} for ${kg.toLocaleString("en-IN")} kg`,
    belowTop: "This is not above the highest bid.", escrowReleased: "Payment released to the farmer", delivery: "Delivery",
    route: (from: string, to: string, km: number, h: number) => `${from} → ${to} · ${km} km · about ${h} h`,
    states: { AWAITING_DRIVER: "Waiting for a driver", ASSIGNED: "Driver assigned", PICKED_UP: "On the road", DELIVERED: "Delivered" },
    readOnly: "Read-only view: farmers list and accept, buyers bid.", simulated: "Escrows are simulated: no money moves.",
    failed: "Request failed", steps: ["Listed", "Sold", "On the road", "Delivered"], stepsLabel: "Lot progress",
  },
  bn: {
    sellTitle: "সরাসরি ফসল বিক্রি", sellLede: "লট দিন; ক্রেতা ও ব্যবসায়ীরা খোলাখুলি দর দেবেন। আপনি বেছে নেবেন, আর ডেলিভারি পর্যন্ত টাকা এসক্রোতে থাকবে।",
    crop: "ফসল", grade: "গ্রেড", kg: "পরিমাণ (কেজি)", district: "জেলা", upazila: "উপজেলা (ঐচ্ছিক)", asking: "চাওয়া দাম, টাকা/কেজি (ঐচ্ছিক)",
    note: "ক্রেতাদের জন্য নোট (ঐচ্ছিক)", list: "দরের জন্য দিন", listed: "লট দেওয়া হয়েছে",
    myLots: "আমার লট", openLots: "দর দেওয়ার মতো লট", myBuys: "আমার কেনা", allLots: "সব লট",
    none: "এখনও কিছু নেই।", bids: "দর", noBids: "এখনও দর আসেনি।", asking2: "চাওয়া", floor: "উৎপাদন খরচ",
    accept: "গ্রহণ", cancel: "লট বাতিল", cancelled: "লট বাতিল হয়েছে", wallet: "ওয়ালেট", walletNo: "ওয়ালেট নম্বর",
    confirmAccept: "গ্রহণ করে টাকা আটকে রাখুন", belowFloor: (floor: number) => `এই দর উৎপাদন খরচ ${floor} টাকা/কেজির নিচে। তবু লোকসানে বেচবেন?`,
    sold: "বিক্রি হয়েছে: টাকা এসক্রোতে", yourBid: "আপনার দর", bidPrice: "আপনার দাম, টাকা/কেজি", placeBid: "দর দিন", raise: "দর বাড়ান", bidPlaced: "দর দেওয়া হয়েছে",
    highest: "সর্বোচ্চ দর", escrowHeld: "টাকা আটকে আছে", escrowRefunded: "ক্রেতাকে ফেরত দেওয়া হয়েছে", you: "আপনি", top: "সর্বোচ্চ", earlier: (n: number) => `আগের দর (${n})`,
    leading: (p: number) => `আপনিই এগিয়ে, কেজি ${p} টাকা।`, outbid: (top: number, mine: number) => `আপনার চেয়ে বেশি দর এসেছে: সর্বোচ্চ ${top}, আপনার ${mine} টাকা/কেজি।`,
    first: "এখনও দর নেই: আপনার দরই প্রথম হবে।", total: (tk: string, kg: number) => `= ${kg.toLocaleString("en-IN")} কেজিতে ${tk}`,
    belowTop: "এই দর সর্বোচ্চ দরের বেশি নয়।", escrowReleased: "টাকা কৃষককে ছাড় হয়েছে", delivery: "ডেলিভারি",
    route: (from: string, to: string, km: number, h: number) => `${from} → ${to} · ${km} কিমি · প্রায় ${h} ঘণ্টা`,
    states: { AWAITING_DRIVER: "চালকের অপেক্ষা", ASSIGNED: "চালক ঠিক হয়েছে", PICKED_UP: "পথে", DELIVERED: "পৌঁছেছে" },
    readOnly: "শুধু দেখা: কৃষক লট দেন ও গ্রহণ করেন, ক্রেতা দর দেন।", simulated: "এসক্রো সিমুলেটেড: কোনো টাকা লেনদেন হয় না।",
    failed: "অনুরোধ ব্যর্থ", steps: ["তালিকায়", "বিক্রি", "পথে", "পৌঁছেছে"], stepsLabel: "লটের অগ্রগতি",
  },
};

const message = (error: unknown) => (error instanceof ApiError ? error.message : String(error));
const STAGE: Record<MarketLot["status"], number> = { OPEN: 0, SOLD: 1, IN_TRANSIT: 2, DELIVERED: 3, CANCELLED: -1 };
const activeBids = (lot: MarketLot) => lot.bids.filter((b) => b.status === "ACTIVE").sort((a, b) => b.price_tk_per_kg - a.price_tk_per_kg);

/** Direct marketplace: farmers list lots and accept bids, buyers bid in the open; judges and admins watch. */
export function MarketplaceSeat() {
  const c = useCopy(COPY);
  const user = useAppState((s) => s.user);
  const [lots, setLots] = useState<MarketLot[] | null>(null);

  const load = useCallback(async () => {
    try {
      setLots(await api.marketLots());
    } catch (error) {
      pushAlert("danger", c.failed, message(error));
    }
  }, [c.failed]);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 8_000);  // new bids show up without a reload
    return () => window.clearInterval(timer);
  }, [load]);

  if (!user) return null;
  if (!lots) return <Spinner />;
  const role = user.role;
  const mine = lots.filter((l) => l.farmer_id === user.user_id);

  return (
    <div className="grid gap-4">
      <p className="m-0 text-[12.5px] text-slate-500">{c.simulated}</p>
      {role === "farmer" && (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
          <SellForm onListed={load} />
          <LotList title={c.myLots} lots={mine} render={(lot) => <FarmerLot lot={lot} me={user.user_id} onChange={load} />} />
        </div>
      )}
      {role === "buyer" && (
        <div className="grid gap-4 xl:grid-cols-2">
          <LotList title={c.openLots} lots={lots.filter((l) => l.status === "OPEN")} render={(lot) => <BuyerLot lot={lot} me={user.user_id} onChange={load} />} />
          <LotList title={c.myBuys} lots={lots.filter((l) => l.bids.some((b) => b.buyer_id === user.user_id && b.status === "ACCEPTED"))}
            render={(lot) => <LotCard lot={lot} me={user.user_id} onChange={load} />} />
        </div>
      )}
      {role !== "farmer" && role !== "buyer" && (
        <>
          <p className="m-0 text-[13px] text-slate-600">{c.readOnly}</p>
          <LotList title={c.allLots} lots={lots} render={(lot) => <LotCard lot={lot} />} />
        </>
      )}
    </div>
  );
}

function LotList({ title, lots, render }: { title: string; lots: MarketLot[]; render: (lot: MarketLot) => ReactNode }) {
  const c = useCopy(COPY);
  return (
    <Panel title={`${title} (${lots.length})`} icon={<Gavel className="size-4 text-emerald-700" aria-hidden />}>
      {lots.length === 0 ? <p className="m-0 text-[14px] text-slate-600">{c.none}</p> : <div className="grid gap-3">{lots.map((lot) => <div key={lot.lot_id}>{render(lot)}</div>)}</div>}
    </Panel>
  );
}

/** A lot with its bids (best first), escrow and delivery progress. */
function LotCard({ lot, bidAction, footer, me, onChange }: {
  lot: MarketLot; bidAction?: (bid: MarketBid) => ReactNode; footer?: ReactNode; me?: string; onChange?: () => Promise<void>;
}) {
  const c = useCopy(COPY);
  const lang = useAppState((s) => s.lang);
  // Live bids (and the accepted one) are ranked best first; withdrawn and rejected ones fold away under "Earlier bids".
  const live = lot.bids.filter((b) => b.status === "ACTIVE" || b.status === "ACCEPTED").sort((a, b) => b.price_tk_per_kg - a.price_tk_per_kg);
  const earlier = lot.bids.filter((b) => b.status === "WITHDRAWN" || b.status === "REJECTED").sort((a, b) => b.placed_at.localeCompare(a.placed_at));
  // A bid that arrives on the 8 s poll warms its row; a payment released while you watch is acknowledged once.
  const fresh = useFreshIds(lot.bids.map((b) => b.bid_id));
  const released = useBecame(lot.escrow?.status, "RELEASED");
  return (
    <article className="rounded-xl bg-white p-3 ring-1 ring-inset ring-slate-200">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-[15px] font-semibold text-slate-900">{lot.crop} · Grade {lot.grade} · {Math.round(lot.weight_kg).toLocaleString("en-IN")} kg</div>
          <div className="text-[12.5px] text-slate-600">
            {lot.farmer_name} · {lot.district}{lot.upazila ? `, ${lot.upazila}` : ""}
            {lot.asking_price_tk_per_kg ? ` · ${c.asking2} Tk ${lot.asking_price_tk_per_kg}/kg` : ""} · {c.floor} Tk {lot.floor_tk_per_kg}/kg
          </div>
          <div className="font-mono text-[11px] text-slate-400">{lot.lot_id}</div>
        </div>
        <Badge tone={STATUS_TONE[lot.status]}>{lot.status.replace("_", " ")}</Badge>
      </div>
      {lot.status !== "CANCELLED" && (
        <RouteSteps className="mt-3" steps={c.steps} at={STAGE[lot.status]} label={c.stepsLabel}
          icon={lot.status === "IN_TRANSIT" ? <Truck className="size-3" aria-hidden /> : undefined} />
      )}
      {lot.note && <p className="m-0 mt-2 text-[13px] text-slate-700">“{lot.note}”</p>}
      <div className="mt-2 text-[12px] font-medium text-slate-500">{c.bids}</div>
      {live.length === 0 ? <p className="m-0 text-[13px] text-slate-500">{c.noBids}</p> : (
        <ol className="m-0 mt-1 grid list-none gap-1 p-0">
          {live.map((b, i) => (
            <li key={b.bid_id} className={cn("flex flex-wrap items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-[13px]", fresh.has(b.bid_id) && "animate-flash",
              b.status === "ACCEPTED" ? "bg-emerald-50 ring-1 ring-inset ring-emerald-700/20" : b.buyer_id === me ? "bg-amber-50 ring-1 ring-inset ring-amber-600/25" : "bg-slate-50")}>
              <span className="flex min-w-0 items-start gap-2">
                <span className="num mt-px w-5 shrink-0 text-right text-[12px] text-slate-400">{i + 1}</span>
                <span className="min-w-0">
                  <span className="num font-semibold">Tk {b.price_tk_per_kg}/kg</span> · {b.buyer_name}, {b.buyer_district}
                  {i === 0 && b.status === "ACTIVE" && <Badge tone="emerald" className="ml-1.5">{c.top}</Badge>}
                  {b.buyer_id === me && <Badge tone="amber" className="ml-1.5">{c.you}</Badge>}
                  {b.price_tk_per_kg < lot.floor_tk_per_kg && b.status === "ACTIVE" && <Badge tone="red" className="ml-1.5">{c.floor}</Badge>}
                  {b.note && <span className="block text-[12px] text-slate-500">“{b.note}”</span>}
                </span>
              </span>
              {b.status === "ACTIVE" && bidAction?.(b)}
              {b.status === "ACCEPTED" && <BadgeCheck className="size-4 text-emerald-700" aria-label="accepted" />}
            </li>
          ))}
        </ol>
      )}
      {earlier.length > 0 && (
        <details className="mt-1 text-[12.5px] text-slate-500">
          <summary className="cursor-pointer select-none py-0.5 hover:text-slate-700">{c.earlier(earlier.length)}</summary>
          <ul className="m-0 mt-1 grid list-none gap-0.5 p-0 pl-7">
            {earlier.map((b) => (
              <li key={b.bid_id} className="text-slate-400"><span className="num line-through">Tk {b.price_tk_per_kg}/kg</span> · {b.buyer_name}</li>
            ))}
          </ul>
        </details>
      )}
      {lot.escrow && (
        <div className={cn("mt-2 rounded-lg px-2 py-1.5 text-[12.5px] ring-1 ring-inset", released && "animate-flash",
          lot.escrow.status === "RELEASED" ? "bg-emerald-50 text-emerald-900 ring-emerald-700/20"
            : lot.escrow.status === "REFUNDED" ? "bg-slate-50 text-slate-700 ring-slate-300" : "bg-amber-50/70 text-amber-900 ring-amber-600/20")}>
          {lot.escrow.status === "RELEASED"
            ? <BadgeCheck className={cn("mr-1 inline size-3.5 text-emerald-700", released && "animate-pop")} aria-hidden />
            : <HandCoins className="mr-1 inline size-3.5" aria-hidden />}
          {lot.escrow.status === "RELEASED" ? c.escrowReleased : lot.escrow.status === "REFUNDED" ? c.escrowRefunded : c.escrowHeld}: <span className="num font-semibold">{tk(lot.escrow.amount_tk, 0)}</span> · {lot.escrow.wallet} {lot.escrow.wallet_masked}
        </div>
      )}
      {me && <DisputeBox lot={lot} me={me} lang={lang} onChange={onChange} />}
      {lot.delivery && lot.status !== "CANCELLED" && (
        <div className="mt-2 text-[12.5px] text-slate-700">
          <Truck className="mr-1 inline size-3.5 text-amber-600" aria-hidden />
          <span className="font-medium">{c.states[lot.delivery.status]}</span>
          {lot.delivery.driver_name ? ` · ${lot.delivery.driver_name}` : ""} · {c.route(lot.delivery.origin_district, lot.delivery.destination_district, lot.delivery.distance_km, lot.delivery.eta_hours)}
          {lot.delivery.at_risk && <span className="ml-1 font-semibold text-rose-700"><ShieldAlert className="mr-0.5 inline size-3.5" aria-hidden />at risk</span>}
        </div>
      )}
      {footer}
    </article>
  );
}

function SellForm({ onListed }: { onListed: () => Promise<void> }) {
  const c = useCopy(COPY);
  const user = useAppState((s) => s.user);
  const voice = useAppState((s) => s.lastVoice);
  const grade = useAppState((s) => s.lastGrade);
  const plan = voice?.orchestration?.state;
  // Start from the farmer's last decision and photo grade when there is one.
  const [form, setForm] = useState(() => ({
    crop: (plan?.crop as Crop | undefined) ?? "Cardinal Potato",
    grade: grade?.grade_letter ?? "A",
    weight_kg: plan?.quantity_kg ? Math.round(plan.quantity_kg) : 400,
    district: plan?.district ?? user?.district ?? "Bogura",
    upazila: plan?.upazila ?? "",
    asking: "",
    note: "",
  }));
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      await api.listLot({ crop: form.crop, grade: form.grade, weight_kg: form.weight_kg, district: form.district, upazila: form.upazila || undefined,
                          asking_price_tk_per_kg: form.asking ? Number(form.asking) : undefined, note: form.note || undefined });
      pushAlert("success", c.listed);
      setForm((f) => ({ ...f, note: "" }));
      await onListed();
    } catch (error) {
      pushAlert("danger", c.failed, message(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title={c.sellTitle} icon={<PackagePlus className="size-4 text-emerald-700" aria-hidden />} className="content-start">
      <p className="m-0 mb-3 text-[13px] text-slate-600">{c.sellLede}</p>
      <form onSubmit={(e) => void submit(e)} className="grid grid-cols-2 gap-3">
        <label className="col-span-2 grid gap-1 text-[13px] font-medium text-slate-700">{c.crop}
          <select value={form.crop} onChange={(e) => setForm({ ...form, crop: e.target.value as Crop })} className={FIELD}>
            {CROPS.map((crop) => <option key={crop}>{crop}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-[13px] font-medium text-slate-700">{c.grade}
          <select value={form.grade} onChange={(e) => setForm({ ...form, grade: e.target.value as "A" | "B" | "C" })} className={FIELD}>
            {(["A", "B", "C"] as const).map((g) => <option key={g}>{g}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-[13px] font-medium text-slate-700">{c.kg}
          <input required type="number" min={50} max={20000} step={10} value={form.weight_kg} onChange={(e) => setForm({ ...form, weight_kg: Number(e.target.value) })} className={FIELD} />
        </label>
        <label className="grid gap-1 text-[13px] font-medium text-slate-700">{c.district}
          <input required minLength={2} maxLength={40} value={form.district} onChange={(e) => setForm({ ...form, district: e.target.value })} className={FIELD} />
        </label>
        <label className="grid gap-1 text-[13px] font-medium text-slate-700">{c.upazila}
          <input maxLength={40} value={form.upazila} onChange={(e) => setForm({ ...form, upazila: e.target.value })} className={FIELD} />
        </label>
        <label className="col-span-2 grid gap-1 text-[13px] font-medium text-slate-700">{c.asking}
          <input type="number" min={1} max={500} step={0.25} value={form.asking} onChange={(e) => setForm({ ...form, asking: e.target.value })} className={FIELD} />
        </label>
        <label className="col-span-2 grid gap-1 text-[13px] font-medium text-slate-700">{c.note}
          <input maxLength={200} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} className={FIELD} />
        </label>
        <Button variant="primary" type="submit" className="col-span-2 min-h-11" disabled={busy}>{busy ? <Spinner /> : <PackagePlus className="size-4" aria-hidden />} {c.list}</Button>
      </form>
    </Panel>
  );
}

function FarmerLot({ lot, me, onChange }: { lot: MarketLot; me: string; onChange: () => Promise<void> }) {
  const c = useCopy(COPY);
  const [choosing, setChoosing] = useState<MarketBid | null>(null);
  const [wallet, setWallet] = useState<Wallet>("bKash");
  const [walletNumber, setWalletNumber] = useState("");
  const [busy, setBusy] = useState(false);

  const accept = async (event: FormEvent) => {
    event.preventDefault();
    if (!choosing) return;
    const below = choosing.price_tk_per_kg < lot.floor_tk_per_kg;
    if (below && !window.confirm(c.belowFloor(lot.floor_tk_per_kg))) return;
    setBusy(true);
    try {
      await api.acceptBid(lot.lot_id, { bid_id: choosing.bid_id, wallet, wallet_number: walletNumber, accept_below_floor: below });
      pushAlert("success", c.sold);
      setChoosing(null);
      setWalletNumber("");
      await onChange();
    } catch (error) {
      pushAlert("danger", c.failed, message(error));
    } finally {
      setBusy(false);
    }
  };

  const cancel = async () => {
    try {
      await api.cancelLot(lot.lot_id);
      pushAlert("info", c.cancelled);
      await onChange();
    } catch (error) {
      pushAlert("danger", c.failed, message(error));
    }
  };

  return (
    <LotCard lot={lot} me={me} onChange={onChange}
      bidAction={lot.status === "OPEN" ? (bid) => <Button variant="primary" className="min-h-8 px-3 text-[13px]" onClick={() => setChoosing(bid)}>{c.accept}</Button> : undefined}
      footer={lot.status === "OPEN" && (
        <>
          {choosing && (
            <form onSubmit={(e) => void accept(e)} className="mt-3 grid gap-2 rounded-lg bg-emerald-50/60 p-3 ring-1 ring-inset ring-emerald-700/15 sm:grid-cols-[120px_minmax(0,1fr)_auto]">
              <div className="text-[13px] text-slate-700 sm:col-span-3">
                {c.accept}: <span className="num font-semibold">Tk {choosing.price_tk_per_kg}/kg</span> × {lot.weight_kg} kg = <span className="num font-semibold">{tk(choosing.price_tk_per_kg * lot.weight_kg, 0)}</span> · {choosing.buyer_name}
              </div>
              <label className="grid gap-1 text-[12.5px] font-medium text-slate-700">{c.wallet}
                <select value={wallet} onChange={(e) => setWallet(e.target.value as Wallet)} className={FIELD}><option>bKash</option><option>Nagad</option></select>
              </label>
              <label className="grid gap-1 text-[12.5px] font-medium text-slate-700">{c.walletNo}
                <input required inputMode="numeric" pattern="01[3-9][0-9]{8}" placeholder="01XXXXXXXXX" value={walletNumber}
                  onChange={(e) => setWalletNumber(e.target.value.trim())} className={FIELD} />
              </label>
              <div className="flex items-end gap-1">
                <Button variant="primary" type="submit" className="min-h-10" disabled={busy}>{busy ? <Spinner /> : null} {c.confirmAccept}</Button>
                <Button variant="quiet" type="button" className="min-h-10" onClick={() => setChoosing(null)} aria-label="close"><X className="size-4" aria-hidden /></Button>
              </div>
            </form>
          )}
          <div className="mt-2 text-right">
            <Button variant="quiet" className="min-h-8 text-[12.5px] text-rose-700" onClick={() => void cancel()}>{c.cancel}</Button>
          </div>
        </>
      )} />
  );
}

function BuyerLot({ lot, me, onChange }: { lot: MarketLot; me: string; onChange: () => Promise<void> }) {
  const c = useCopy(COPY);
  const active = activeBids(lot);
  const myBid = active.find((b) => b.buyer_id === me);
  const highest = active[0];
  const suggested = useMemo(() => (highest ? highest.price_tk_per_kg + 0.25 : lot.asking_price_tk_per_kg ?? lot.floor_tk_per_kg + 2), [highest, lot]);
  // The box follows the market (highest + 0.25) until the buyer types a price.
  const [typed, setTyped] = useState<string | null>(null);
  const price = typed ?? String(suggested);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const leading = myBid !== undefined && highest?.bid_id === myBid.bid_id;
  const notAbove = highest !== undefined && Number(price) <= highest.price_tk_per_kg && !leading;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      await api.placeBid(lot.lot_id, Number(price), note || undefined);
      pushAlert("success", c.bidPlaced, `Tk ${price}/kg · ${lot.crop}`);
      setNote("");
      setTyped(null);
      await onChange();
    } catch (error) {
      pushAlert("danger", c.failed, message(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <LotCard lot={lot} me={me} footer={
      <form onSubmit={(e) => void submit(e)} className="mt-3 grid gap-2 sm:grid-cols-[150px_minmax(0,1fr)_auto]">
        <p className={cn("m-0 rounded-lg px-2.5 py-1.5 text-[12.5px] font-medium sm:col-span-3",
          leading ? "bg-emerald-50 text-emerald-800" : myBid ? "bg-amber-50 text-amber-900" : "bg-slate-50 text-slate-700")} role="status">
          {leading && myBid ? c.leading(myBid.price_tk_per_kg) : myBid && highest ? c.outbid(highest.price_tk_per_kg, myBid.price_tk_per_kg) : highest ? `${c.highest}: Tk ${highest.price_tk_per_kg}/kg` : c.first}
        </p>
        <label className="grid gap-1 text-[12.5px] font-medium text-slate-700">{c.bidPrice}
          <input required type="number" min={0.25} max={500} step={0.25} value={price} onChange={(e) => setTyped(e.target.value)} className={FIELD} />
        </label>
        <label className="grid gap-1 text-[12.5px] font-medium text-slate-700">{c.note}
          <input maxLength={200} value={note} onChange={(e) => setNote(e.target.value)} className={FIELD} />
        </label>
        <div className="flex items-end">
          <Button variant="amber" type="submit" className="min-h-10 w-full" disabled={busy}>{busy ? <Spinner /> : null} {myBid ? c.raise : c.placeBid}</Button>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 text-[12px] text-slate-500 sm:col-span-3">
          {highest && [0.25, 0.5, 1].map((step) => (
            <button key={step} type="button" onClick={() => setTyped(String(highest.price_tk_per_kg + step))}
              className="rounded-full bg-white px-2 py-0.5 font-medium text-amber-800 ring-1 ring-inset ring-amber-600/30 transition-colors hover:bg-amber-50">
              +{step.toFixed(2)}
            </button>
          ))}
          <span className="num">{Number(price) > 0 ? c.total(tk(Number(price) * lot.weight_kg, 0), lot.weight_kg) : ""}</span>
          {notAbove && <span className="font-medium text-amber-800">· {c.belowTop}</span>}
        </div>
      </form>
    } />
  );
}

export default MarketplaceSeat;
