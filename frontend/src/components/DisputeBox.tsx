import { MessageSquareWarning, X } from "lucide-react";
import { useState, type FormEvent } from "react";

import { api, ApiError, type DisputeKind, type MarketLot, type Resolution } from "../api/client";
import { cn } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { pushAlert } from "../state/store";
import { Badge, Button, Spinner } from "./ui";

export const KIND_LABEL: Record<"en" | "bn", Record<DisputeKind, string>> = {
  en: { PAYMENT_NOT_RECEIVED: "Payment not received", WRONG_AMOUNT: "Wrong amount", DELIVERY_PROBLEM: "Delivery problem",
        QUALITY_MISMATCH: "Quality not as graded", OTHER: "Other problem" },
  bn: { PAYMENT_NOT_RECEIVED: "টাকা পাইনি", WRONG_AMOUNT: "ভুল পরিমাণ", DELIVERY_PROBLEM: "ডেলিভারিতে সমস্যা",
        QUALITY_MISMATCH: "মান গ্রেডের সাথে মেলেনি", OTHER: "অন্য সমস্যা" },
};

export const RESOLUTION_LABEL: Record<"en" | "bn", Record<Resolution, string>> = {
  en: { RELEASE_TO_FARMER: "Payment released to the farmer", REFUND_TO_BUYER: "Refunded to the buyer; sale cancelled",
        KEEP_HOLDING: "Payment kept in escrow", NO_CHANGE: "Closed, no change" },
  bn: { RELEASE_TO_FARMER: "টাকা কৃষককে ছাড়া হয়েছে", REFUND_TO_BUYER: "ক্রেতাকে ফেরত; বিক্রি বাতিল",
        KEEP_HOLDING: "টাকা এসক্রোতে রাখা হয়েছে", NO_CHANGE: "বন্ধ, কোনো পরিবর্তন নেই" },
};

const COPY = {
  en: { report: "Report a problem", send: "Send to the bank", kind: "What went wrong", note: "Details (optional)", sent: "Sent to the bank desk",
        failed: "Request failed", open: "Open with the bank", resolved: "Resolved", by: "by" },
  bn: { report: "সমস্যা জানান", send: "ব্যাংকে পাঠান", kind: "কী সমস্যা", note: "বিস্তারিত (ঐচ্ছিক)", sent: "ব্যাংক ডেস্কে পাঠানো হয়েছে",
        failed: "অনুরোধ ব্যর্থ", open: "ব্যাংকের কাছে খোলা", resolved: "সমাধান হয়েছে", by: "" },
};

const FIELD = "min-h-9 w-full rounded-lg bg-white px-2.5 text-[13px] text-slate-900 ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-emerald-700 focus:outline-none";

/** A sale's disputes, and (for its farmer, buyer or driver) a way to report one to the bank desk. */
export function DisputeBox({ lot, me, lang, onChange }: { lot: MarketLot; me: string; lang: "en" | "bn"; onChange?: () => Promise<void> }) {
  const c = useCopy(COPY);
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<DisputeKind>("PAYMENT_NOT_RECEIVED");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  if (!lot.escrow) return null;
  const buyer = lot.bids.find((b) => b.bid_id === lot.accepted_bid_id)?.buyer_id;
  const party = me === lot.farmer_id || me === buyer || me === lot.delivery?.driver_id;
  const disputes = lot.disputes ?? [];
  if (!party && disputes.length === 0) return null;

  const send = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      await api.raiseDispute(lot.lot_id, kind, note);
      pushAlert("success", c.sent, KIND_LABEL[lang][kind]);
      setOpen(false);
      setNote("");
      await onChange?.();
    } catch (error) {
      pushAlert("danger", c.failed, error instanceof ApiError ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-2 grid gap-1.5">
      {disputes.map((d) => (
        <div key={d.dispute_id} className={cn("rounded-lg px-2.5 py-1.5 text-[12.5px] ring-1 ring-inset",
          d.status === "OPEN" ? "bg-violet-50 text-violet-900 ring-violet-600/20" : "bg-slate-50 text-slate-700 ring-slate-200")}>
          <div className="flex flex-wrap items-center gap-1.5">
            <MessageSquareWarning className="size-3.5" aria-hidden />
            <span className="font-semibold">{KIND_LABEL[lang][d.kind]}</span>
            <Badge tone={d.status === "OPEN" ? "violet" : "slate"}>{d.status === "OPEN" ? c.open : c.resolved}</Badge>
            <span className="text-[12px] opacity-80">· {d.raised_by_name}</span>
          </div>
          {d.note && <div className="mt-0.5">“{d.note}”</div>}
          {d.resolution && <div className="mt-0.5 font-medium">{RESOLUTION_LABEL[lang][d.resolution]}{d.resolution_note ? `: ${d.resolution_note}` : ""}</div>}
        </div>
      ))}
      {party && !open && (
        <div>
          <Button variant="quiet" className="min-h-8 px-2 text-[12.5px] text-violet-800" onClick={() => setOpen(true)}>
            <MessageSquareWarning className="size-3.5" aria-hidden /> {c.report}
          </Button>
        </div>
      )}
      {party && open && (
        <form onSubmit={(e) => void send(e)} className="grid gap-2 rounded-lg bg-violet-50/60 p-2.5 ring-1 ring-inset ring-violet-600/15 sm:grid-cols-[180px_minmax(0,1fr)_auto]">
          <label className="grid gap-1 text-[12px] font-medium text-slate-700">{c.kind}
            <select value={kind} onChange={(e) => setKind(e.target.value as DisputeKind)} className={FIELD}>
              {(Object.keys(KIND_LABEL.en) as DisputeKind[]).map((k) => <option key={k} value={k}>{KIND_LABEL[lang][k]}</option>)}
            </select>
          </label>
          <label className="grid gap-1 text-[12px] font-medium text-slate-700">{c.note}
            <input maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} className={FIELD} />
          </label>
          <div className="flex items-end gap-1">
            <Button variant="primary" type="submit" className="min-h-9" disabled={busy}>{busy ? <Spinner /> : null} {c.send}</Button>
            <Button variant="quiet" className="min-h-9" onClick={() => setOpen(false)} aria-label="close"><X className="size-4" aria-hidden /></Button>
          </div>
        </form>
      )}
    </div>
  );
}
