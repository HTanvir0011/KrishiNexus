/**
 * Live market events for the signed-in account: GET /market/stream (server-sent events). Each event bumps a debounced
 * `marketTick`, so the seats on screen reload their lots, deliveries, ledger and disputes; events that concern this
 * account raise a toast. EventSource reconnects by itself and sends Last-Event-ID; when the node refuses the stream
 * outright (an HTTP error, a full feed's 503, an older node), it is reopened with ?since=<last seq> after a growing
 * pause. While the stream is down, GET /market/events is polled every 8 s for the same events, and the seats keep
 * their own 8-second polling (useMarketRefresh). Any reconnect reloads the seats once, so a gap never shows stale data.
 */

import { useEffect } from "react";

import { API_BASE, api, type AuthUser, type MarketEvent, type MarketLot } from "../api/client";
import { tk } from "../lib/format";
import { getState, pushAlert, setState, useAppState, type AlertTone, type Lang } from "./store";

const COPY = {
  en: {
    newBid: (crop: string) => `New bid on your ${crop} lot`,
    bidDetail: (price: number, buyer: string) => `Tk ${price}/kg from ${buyer}`,
    outbid: (crop: string) => `You were outbid on ${crop}`,
    outbidDetail: (price: number) => `The highest bid is now Tk ${price}/kg.`,
    won: (crop: string) => `Your bid won: ${crop}`,
    held: (amount: string) => `${amount} is held until delivery.`,
    job: "New delivery job",
    claimed: (crop: string) => `A driver took your ${crop} delivery`,
    pickedUp: (crop: string) => `Your ${crop} is on the road`,
    paid: (crop: string) => `Delivered: payment released for ${crop}`,
    delivered: (crop: string) => `Your ${crop} was delivered`,
    disputeOpened: (crop: string) => `A problem was reported on ${crop}`,
    disputeResolved: (crop: string) => `The problem on ${crop} was settled`,
    by: (name: string) => `Reported by ${name}`,
  },
  bn: {
    newBid: (crop: string) => `আপনার ${crop} লটে নতুন দর`,
    bidDetail: (price: number, buyer: string) => `${buyer}: কেজি ${price} টাকা`,
    outbid: (crop: string) => `${crop}-এ আপনার দর ছাড়িয়ে গেছে`,
    outbidDetail: (price: number) => `এখন সর্বোচ্চ দর কেজি ${price} টাকা।`,
    won: (crop: string) => `আপনার দর জিতেছে: ${crop}`,
    held: (amount: string) => `ডেলিভারি পর্যন্ত ${amount} আটকে থাকবে।`,
    job: "নতুন ডেলিভারির কাজ",
    claimed: (crop: string) => `একজন চালক আপনার ${crop} ডেলিভারির কাজ নিয়েছেন`,
    pickedUp: (crop: string) => `আপনার ${crop} পথে আছে`,
    paid: (crop: string) => `পৌঁছেছে: ${crop}-এর টাকা ছাড় হয়েছে`,
    delivered: (crop: string) => `আপনার ${crop} পৌঁছেছে`,
    disputeOpened: (crop: string) => `${crop}-এ সমস্যা জানানো হয়েছে`,
    disputeResolved: (crop: string) => `${crop}-এর সমস্যার মীমাংসা হয়েছে`,
    by: (name: string) => `জানিয়েছেন ${name}`,
  },
};

const TOAST_KINDS = new Set<MarketEvent["kind"]>(["bid_placed", "lot_sold", "job_claimed", "picked_up", "delivered", "dispute_opened", "dispute_resolved"]);
// Judges, admins, co-ops and cold stores are not a party to a sale, so they get the live refresh without toasts.
const PARTY_ROLES = new Set<AuthUser["role"]>(["farmer", "buyer", "driver", "bank"]);

const topBid = (lot: MarketLot) => lot.bids.filter((b) => b.status === "ACTIVE").sort((a, b) => b.price_tk_per_kg - a.price_tk_per_kg)[0];
const newest = <T,>(items: T[], at: (item: T) => string | null) => [...items].sort((a, b) => (at(b) ?? "").localeCompare(at(a) ?? ""))[0];

type Toast = [AlertTone, string, string?];

/** What an event means for this account, from the lot as it is now (and as it was, to tell "I was leading"). */
export function describe(kind: MarketEvent["kind"], lot: MarketLot, before: MarketLot | undefined, user: AuthUser, lang: Lang): Toast | null {
  const c = COPY[lang];
  const me = user.user_id;
  const farmer = lot.farmer_id === me;
  const buyer = lot.bids.some((b) => b.bid_id === lot.accepted_bid_id && b.buyer_id === me);
  const driver = lot.delivery?.driver_id === me;
  const d = lot.delivery;
  switch (kind) {
    case "bid_placed": {
      const top = topBid(lot);
      if (!top) return null;
      if (farmer) return ["info", c.newBid(lot.crop), c.bidDetail(top.price_tk_per_kg, top.buyer_name)];
      const wasLeading = before !== undefined && topBid(before)?.buyer_id === me;
      return wasLeading && top.buyer_id !== me ? ["warn", c.outbid(lot.crop), c.outbidDetail(top.price_tk_per_kg)] : null;
    }
    case "lot_sold":
      if (buyer) return ["success", c.won(lot.crop), lot.escrow ? c.held(tk(lot.escrow.amount_tk, 0)) : undefined];
      if (user.role === "driver" && d?.status === "AWAITING_DRIVER") {
        return ["info", c.job, `${lot.crop} · ${Math.round(lot.weight_kg).toLocaleString("en-IN")} kg · ${d.origin_district} → ${d.destination_district}`];
      }
      return null;
    case "job_claimed":
      return farmer || buyer ? ["info", c.claimed(lot.crop), d?.driver_name ?? undefined] : null;
    case "picked_up":
      return farmer || buyer ? ["info", c.pickedUp(lot.crop), d ? `${d.origin_district} → ${d.destination_district}` : undefined] : null;
    case "delivered":
      if (farmer) return ["success", c.paid(lot.crop), lot.escrow ? `${tk(lot.escrow.amount_tk, 0)} · ${lot.escrow.wallet} ${lot.escrow.wallet_masked}` : undefined];
      return buyer ? ["success", c.delivered(lot.crop)] : null;
    case "dispute_opened": {
      const dispute = newest(lot.disputes.filter((x) => x.status === "OPEN"), (x) => x.opened_at);
      if (!dispute || dispute.raised_by === me) return null;   // the one who reported it already knows
      return farmer || buyer || driver || user.role === "bank" ? ["warn", c.disputeOpened(lot.crop), c.by(dispute.raised_by_name)] : null;
    }
    case "dispute_resolved":
      return farmer || buyer || driver ? ["info", c.disputeResolved(lot.crop)] : null;
    default:
      return null;
  }
}

// The lots as of the last toast check: "was I the top bidder before this bid?" needs the state before the event.
let lastLots: Map<string, MarketLot> | null = null;
const lotsById = async () => new Map((await api.marketLots()).map((lot) => [lot.lot_id, lot]));

async function notify(events: MarketEvent[]): Promise<void> {
  const user = getState().user;
  if (!user || !PARTY_ROLES.has(user.role) || !events.some((e) => TOAST_KINDS.has(e.kind))) return;
  let now: Map<string, MarketLot>;
  try {
    now = await lotsById();
  } catch {
    return;
  }
  const before = lastLots;
  lastLots = now;
  const seen = new Set<string>();
  for (const event of events) {
    const key = `${event.kind}:${event.lot_id}`;
    const lot = event.lot_id ? now.get(event.lot_id) : undefined;
    if (!lot || seen.has(key)) continue;
    seen.add(key);
    const toast = describe(event.kind, lot, before?.get(lot.lot_id), user, getState().lang);
    if (toast) pushAlert(...toast);
  }
}

/** Open the stream; returns the function that closes it. */
export function connectMarketStream(): () => void {
  let source: EventSource | null = null;
  let lastSeq: number | null = null;
  let retry = 0;
  let dropped = false;
  let stopped = false;
  let reopen: number | undefined;
  let debounce: number | undefined;
  let poller: number | undefined;
  let pending: MarketEvent[] = [];

  const flush = () => {
    const events = pending;
    pending = [];
    setState((s) => ({ marketTick: s.marketTick + 1 }));
    void notify(events);
  };

  // Events come in seq order from the stream and from polling; one already seen (the two overlapped) is skipped.
  const take = (event: MarketEvent) => {
    if (lastSeq !== null && event.seq <= lastSeq) return;
    lastSeq = event.seq;
    pending.push(event);
    window.clearTimeout(debounce);
    debounce = window.setTimeout(flush, 400);
  };

  const poll = async () => {
    try {
      const page = await api.marketEvents(lastSeq ?? 0);
      if (lastSeq === null) lastSeq = page.seq;   // a first look starts from now, as the stream does (since=0 is the whole buffer)
      else page.events.forEach(take);
    } catch {
      // The seats' own polling still keeps the screen current.
    }
  };
  const startPolling = () => {
    if (poller !== undefined || stopped) return;
    void poll();
    poller = window.setInterval(() => void poll(), 8_000);
  };
  const stopPolling = () => {
    window.clearInterval(poller);
    poller = undefined;
  };

  const open = () => {
    if (stopped) return;
    source = new EventSource(`${API_BASE}/market/stream${lastSeq === null ? "" : `?since=${lastSeq}`}`);
    source.onopen = () => {
      retry = 0;
      stopPolling();
      // After a gap, reload once: anything missed is on the screen even if the node could not replay it.
      setState((s) => ({ marketLive: "open", marketTick: dropped ? s.marketTick + 1 : s.marketTick }));
      dropped = false;
      if (!lastLots && PARTY_ROLES.has(getState().user?.role ?? "judge")) lotsById().then((lots) => { lastLots ??= lots; }, () => undefined);
    };
    source.addEventListener("market", (message) => {
      try {
        take(JSON.parse((message as MessageEvent<string>).data) as MarketEvent);
      } catch {
        // Not a market event: ignore it.
      }
    });
    source.onerror = () => {
      if (stopped || !source) return;
      dropped = true;
      setState({ marketLive: "connecting" });
      startPolling();
      if (source.readyState !== EventSource.CLOSED) return;   // the browser retries by itself, with Last-Event-ID
      source.close();   // refused (an HTTP error or a full feed's 503): reopen it ourselves, after a growing pause
      reopen = window.setTimeout(open, Math.min(30_000, 1_000 * 2 ** retry++));
    };
  };

  setState({ marketLive: "connecting" });
  open();
  return () => {
    stopped = true;
    stopPolling();
    window.clearTimeout(reopen);
    window.clearTimeout(debounce);
    source?.close();
    lastLots = null;
    setState({ marketLive: "off" });
  };
}

/**
 * Load on mount and after every market event; poll every 8 s while the live stream is down. While it is up, a slow
 * 30-second poll stays on as insurance against a proxy that holds events back without closing the connection.
 */
export function useMarketRefresh(load: () => Promise<void>): void {
  const live = useAppState((s) => s.marketLive === "open");
  const tick = useAppState((s) => s.marketTick);
  useEffect(() => {
    void load();
  }, [load, tick]);
  useEffect(() => {
    const timer = window.setInterval(() => void load(), live ? 30_000 : 8_000);
    return () => window.clearInterval(timer);
  }, [load, live]);
}
