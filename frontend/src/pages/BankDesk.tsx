import { BadgeCheck, FileSearch, Landmark, MessageSquareWarning, ReceiptText, Scale, ShieldAlert, Vault } from "lucide-react";
import { useCallback, useState, type ReactNode } from "react";

import { api, ApiError, type Dispute, type LedgerRow, type Resolution } from "../api/client";
import { KIND_LABEL, RESOLUTION_LABEL } from "../components/DisputeBox";
import { Badge, Button, Panel, Spinner, Stat } from "../components/ui";
import { cn, tk } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { useFreshIds } from "../lib/motion";
import { Link } from "../lib/router";
import { useMarketRefresh } from "../state/marketStream";
import { pushAlert, useAppState } from "../state/store";

const COPY = {
  en: {
    dutiesTitle: "What the bank desk does",
    duties: [
      ["Holds every payment", "When a farmer accepts a bid, the buyer's money waits here in escrow, not with a middleman."],
      ["Releases it on delivery", "The weighbridge confirms the load; the payment goes to the farmer's bKash or Nagad."],
      ["Resolves disputes", "A farmer, buyer or driver reports a problem; the desk releases, refunds or keeps holding."],
      ["Lends without collateral", "Credit from the 300-850 score, backed by signed quality certificates and the escrowed sale."],
    ],
    creditLink: "Open credit underwriting and certificate checks",
    stats: { held: "Held in escrow", released: "Released to farmers", refunded: "Refunded to buyers", open: "Open disputes" },
    hints: { payments: (n: number) => `${n} payment${n === 1 ? "" : "s"}`, open: "need a decision" },
    queue: "Dispute queue",
    history: "Transaction history",
    none: "Nothing here.",
    raised: (who: string, role: string) => `Raised by ${who} (${role})`,
    release: "Release to farmer", refund: "Refund buyer", keep: "Keep holding", close: "Close, no change",
    notePlaceholder: "Note for both sides (optional)",
    done: "Dispute resolved", failed: "Request failed",
    readOnly: "Read-only for judges: only the bank account resolves disputes.",
    cols: { when: "Locked", sale: "Sale", parties: "Farmer → buyer", amount: "Amount", status: "Status" },
    status: { HELD: "Held", RELEASED: "Released", REFUNDED: "Refunded" },
    flags: { dispute: "dispute", risk: "load at risk", floor: "below cost" },
    simulated: "Escrows are simulated: no money moves and no bKash or Nagad API is called.",
  },
  bn: {
    dutiesTitle: "ব্যাংক ডেস্ক কী করে",
    duties: [
      ["সব টাকা আটকে রাখে", "কৃষক দর গ্রহণ করলে ক্রেতার টাকা এসক্রোতে থাকে, মধ্যস্বত্বভোগীর কাছে নয়।"],
      ["ডেলিভারিতে ছাড়ে", "ওজন মিললে টাকা কৃষকের বিকাশ বা নগদে যায়।"],
      ["অভিযোগের সমাধান", "কৃষক, ক্রেতা বা চালক সমস্যা জানালে ডেস্ক টাকা ছাড়ে, ফেরত দেয় বা আটকে রাখে।"],
      ["জামানত ছাড়া ঋণ", "৩০০-৮৫০ স্কোর, স্বাক্ষরিত মান সনদ আর এসক্রোর বিক্রির ভিত্তিতে ঋণ।"],
    ],
    creditLink: "ঋণ যাচাই ও সনদ পরীক্ষা খুলুন",
    stats: { held: "এসক্রোতে আটকে", released: "কৃষককে ছাড়া হয়েছে", refunded: "ক্রেতাকে ফেরত", open: "খোলা অভিযোগ" },
    hints: { payments: (n: number) => `${n}টি লেনদেন`, open: "সিদ্ধান্ত দরকার" },
    queue: "অভিযোগের তালিকা",
    history: "লেনদেনের ইতিহাস",
    none: "কিছু নেই।",
    raised: (who: string, role: string) => `${who} (${role}) জানিয়েছেন`,
    release: "কৃষককে ছাড়ুন", refund: "ক্রেতাকে ফেরত", keep: "আটকে রাখুন", close: "বন্ধ করুন",
    notePlaceholder: "দুই পক্ষের জন্য নোট (ঐচ্ছিক)",
    done: "অভিযোগের সমাধান হয়েছে", failed: "অনুরোধ ব্যর্থ",
    readOnly: "বিচারকের জন্য শুধু দেখা: কেবল ব্যাংক অ্যাকাউন্ট সমাধান করে।",
    cols: { when: "আটকানোর সময়", sale: "বিক্রি", parties: "কৃষক → ক্রেতা", amount: "টাকা", status: "অবস্থা" },
    status: { HELD: "আটকে", RELEASED: "ছাড়া হয়েছে", REFUNDED: "ফেরত" },
    flags: { dispute: "অভিযোগ", risk: "মাল ঝুঁকিতে", floor: "খরচের নিচে" },
    simulated: "এসক্রো সিমুলেটেড: কোনো টাকা লেনদেন হয় না।",
  },
};

const STATUS_TONE = { HELD: "amber", RELEASED: "emerald", REFUNDED: "slate" } as const;
const DUTY_ICON = [Vault, BadgeCheck, Scale, Landmark];
const when = (iso: string) => new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const message = (error: unknown) => (error instanceof ApiError ? error.message : String(error));

/** The bank's own seat: custody of every payment, the dispute queue, and the transaction history. */
export function BankDesk() {
  const c = useCopy(COPY);
  const user = useAppState((s) => s.user);
  const lang = useAppState((s) => s.lang);
  const [ledger, setLedger] = useState<LedgerRow[] | null>(null);
  const [disputes, setDisputes] = useState<Dispute[] | null>(null);

  const load = useCallback(async () => {
    try {
      const [rows, list] = await Promise.all([api.ledger(), api.disputes()]);
      setLedger(rows);
      setDisputes(list);
    } catch (error) {
      pushAlert("danger", c.failed, message(error));
    }
  }, [c.failed]);

  useMarketRefresh(load);

  const fresh = useFreshIds((disputes ?? []).map((d) => d.dispute_id));
  if (!user) return null;
  if (!ledger || !disputes) return <Spinner />;
  const canAct = user.role === "bank" || user.role === "admin";
  const sum = (status: LedgerRow["status"]) => ledger.filter((r) => r.status === status).reduce((t, r) => t + r.amount_tk, 0);
  const count = (status: LedgerRow["status"]) => ledger.filter((r) => r.status === status).length;
  const open = disputes.filter((d) => d.status === "OPEN");
  const byLot = new Map(ledger.filter((r) => r.lot_id).map((r) => [r.lot_id as string, r]));

  return (
    <div className="grid gap-4">
      <section className="surface p-4" aria-labelledby="duties-title">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id="duties-title" className="m-0 text-[15px] font-semibold text-slate-900">{c.dutiesTitle}</h2>
          <Link to="/os/market" className="inline-flex items-center gap-1.5 text-[13px] font-semibold text-emerald-700 no-underline hover:text-emerald-800">
            <FileSearch className="size-4" aria-hidden /> {c.creditLink}
          </Link>
        </div>
        <ul className="m-0 mt-3 grid list-none gap-3 p-0 sm:grid-cols-2 xl:grid-cols-4">
          {c.duties.map(([title, text], i) => {
            const Icon = DUTY_ICON[i];
            return (
              <li key={title} className="flex gap-2.5">
                <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-violet-50 text-violet-700 ring-1 ring-inset ring-violet-600/15"><Icon className="size-4" aria-hidden /></span>
                <span className="min-w-0">
                  <span className="block text-[13.5px] font-semibold text-slate-900">{title}</span>
                  <span className="block text-[12.5px] text-slate-600">{text}</span>
                </span>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="surface grid grid-cols-2 gap-4 p-4 sm:grid-cols-4" aria-label="Bank summary">
        <Stat label={c.stats.held} value={tk(sum("HELD"), 0)} hint={c.hints.payments(count("HELD"))} tone="amber" />
        <Stat label={c.stats.released} value={tk(sum("RELEASED"), 0)} hint={c.hints.payments(count("RELEASED"))} tone="emerald" />
        <Stat label={c.stats.refunded} value={tk(sum("REFUNDED"), 0)} hint={c.hints.payments(count("REFUNDED"))} tone="slate" />
        <Stat label={c.stats.open} value={open.length} hint={c.hints.open} tone={open.length ? "violet" : "slate"} />
      </section>

      {!canAct && <p className="m-0 text-[13px] text-slate-600">{c.readOnly}</p>}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <Panel title={`${c.queue} (${open.length})`} icon={<MessageSquareWarning className="size-4 text-violet-600" aria-hidden />}>
          {disputes.length === 0 ? <p className="m-0 text-[14px] text-slate-600">{c.none}</p> : (
            <div className="grid gap-3">
              {disputes.map((d) => <DisputeCard key={d.dispute_id} d={d} row={byLot.get(d.lot_id)} lang={lang} canAct={canAct} fresh={fresh.has(d.dispute_id)} onChange={load} />)}
            </div>
          )}
        </Panel>
        <Panel title={c.history} icon={<ReceiptText className="size-4 text-violet-600" aria-hidden />} bodyClassName="p-0">
          <div className="scroll-thin overflow-x-auto">
            <table className="w-full min-w-[620px] border-collapse text-[13px]">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/70 text-left text-[12px] text-slate-500">
                  <th className="px-4 py-2 font-medium">{c.cols.when}</th><th className="px-2 py-2 font-medium">{c.cols.sale}</th>
                  <th className="px-2 py-2 font-medium">{c.cols.parties}</th><th className="px-2 py-2 text-right font-medium">{c.cols.amount}</th>
                  <th className="px-4 py-2 font-medium">{c.cols.status}</th>
                </tr>
              </thead>
              <tbody>
                {ledger.map((r) => (
                  <tr key={r.escrow_id} className="border-b border-slate-100 align-top last:border-0">
                    <td className="num px-4 py-2.5 whitespace-nowrap text-slate-600">{when(r.locked_at)}</td>
                    <td className="px-2 py-2.5">
                      <div className="font-medium text-slate-900">{r.crop} · {Math.round(r.weight_kg).toLocaleString("en-IN")} kg</div>
                      <div className="font-mono text-[11px] text-slate-400">{r.lot_id ?? r.escrow_id} · {r.kind}</div>
                    </td>
                    <td className="px-2 py-2.5 text-slate-700">{r.farmer} → {r.buyer}<div className="text-[12px] text-slate-500">{r.wallet} {r.wallet_masked}</div></td>
                    <td className="num px-2 py-2.5 text-right font-semibold whitespace-nowrap text-slate-900">{tk(r.amount_tk, 0)}</td>
                    <td className="px-4 py-2.5">
                      <div className="flex flex-wrap gap-1">
                        <Badge tone={STATUS_TONE[r.status]}>{c.status[r.status]}</Badge>
                        {r.open_disputes > 0 && <Badge tone="violet">{c.flags.dispute}</Badge>}
                        {r.at_risk && <Badge tone="red">{c.flags.risk}</Badge>}
                        {r.below_floor && <Badge tone="red">{c.flags.floor}</Badge>}
                      </div>
                      {r.settled_at && <div className="num mt-0.5 text-[11.5px] text-slate-500">{when(r.settled_at)}</div>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="m-0 border-t border-slate-200 px-4 py-2.5 text-[12px] text-slate-500">{c.simulated}</p>
        </Panel>
      </div>
    </div>
  );
}

function DisputeCard({ d, row, lang, canAct, fresh, onChange }: {
  d: Dispute; row: LedgerRow | undefined; lang: "en" | "bn"; canAct: boolean; fresh: boolean; onChange: () => Promise<void>;
}) {
  const c = useCopy(COPY);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<Resolution | null>(null);
  const held = row?.status === "HELD";

  const resolve = async (resolution: Resolution) => {
    setBusy(resolution);
    try {
      await api.resolveDispute(d.dispute_id, resolution, note);
      pushAlert("success", c.done, RESOLUTION_LABEL[lang][resolution]);
      await onChange();
    } catch (error) {
      pushAlert("danger", c.failed, message(error));
    } finally {
      setBusy(null);
    }
  };

  const action = (resolution: Resolution, label: string, variant: "primary" | "ghost" | "danger", icon?: ReactNode) => (
    <Button variant={variant} className="min-h-9 px-3 text-[13px]" disabled={busy !== null} onClick={() => void resolve(resolution)}>
      {busy === resolution ? <Spinner /> : icon} {label}
    </Button>
  );

  return (
    <article className={cn("rounded-xl bg-white p-3 ring-1 ring-inset", d.status === "OPEN" ? "ring-violet-600/25" : "ring-slate-200", fresh && "animate-flash")}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-[14.5px] font-semibold text-slate-900">{KIND_LABEL[lang][d.kind]}</div>
          <div className="text-[12.5px] text-slate-600">{c.raised(d.raised_by_name, d.raised_by_role)} · {when(d.opened_at)}</div>
          {row && <div className="text-[12.5px] text-slate-600">{row.crop} · {Math.round(row.weight_kg).toLocaleString("en-IN")} kg · {row.farmer} → {row.buyer} · <span className="num font-semibold text-slate-800">{tk(row.amount_tk, 0)}</span> <Badge tone={STATUS_TONE[row.status]}>{c.status[row.status]}</Badge></div>}
        </div>
        <Badge tone={d.status === "OPEN" ? "violet" : "slate"}>{d.status === "OPEN" ? "Open" : "Resolved"}</Badge>
      </div>
      {d.note && <p className="m-0 mt-2 text-[13px] text-slate-700">“{d.note}”</p>}
      {d.status === "RESOLVED" && d.resolution && (
        <p className="m-0 mt-2 rounded-lg bg-slate-50 px-2.5 py-1.5 text-[12.5px] text-slate-700 ring-1 ring-inset ring-slate-200">
          <BadgeCheck className="mr-1 inline size-3.5 text-emerald-700" aria-hidden />
          {RESOLUTION_LABEL[lang][d.resolution]}{d.resolution_note ? `: ${d.resolution_note}` : ""}{d.resolved_at ? ` · ${when(d.resolved_at)}` : ""}
        </p>
      )}
      {d.status === "OPEN" && canAct && (
        <div className="mt-3 grid gap-2">
          <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} placeholder={c.notePlaceholder}
            className="min-h-9 w-full rounded-lg bg-white px-2.5 text-[13px] text-slate-900 ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-emerald-700 focus:outline-none" />
          <div className="flex flex-wrap gap-1.5">
            {held && action("RELEASE_TO_FARMER", c.release, "primary", <BadgeCheck className="size-4" aria-hidden />)}
            {held && action("KEEP_HOLDING", c.keep, "ghost", <Vault className="size-4" aria-hidden />)}
            {held && action("REFUND_TO_BUYER", c.refund, "danger", <ShieldAlert className="size-4" aria-hidden />)}
            {action("NO_CHANGE", c.close, "ghost")}
          </div>
        </div>
      )}
    </article>
  );
}

export default BankDesk;
