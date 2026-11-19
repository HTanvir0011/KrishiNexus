import { Truck } from "lucide-react";

import type { MarketLot } from "../api/client";
import { cn } from "../lib/format";
import { useCopy } from "../lib/i18n";
import { useNow } from "../lib/motion";

type Delivery = NonNullable<MarketLot["delivery"]>;

const COPY = {
  en: {
    route: (from: string, to: string, km: number, h: number) => `${from} → ${to} · ${km} km · about ${h} h`,
    trip: (km: number, h: number) => `${km} km · about ${h} h`,
    position: (km: number, to: string, eta: string) => `Truck is ${km} km from ${to} · ETA ${eta} h`,
    updated: (ago: string) => `updated ${ago}`,
    ago: (s: number) => (s < 60 ? `${s} s ago` : s < 3600 ? `${Math.round(s / 60)} min ago` : `${Math.round(s / 3600)} h ago`),
  },
  bn: {
    route: (from: string, to: string, km: number, h: number) => `${from} → ${to} · ${km} কিমি · প্রায় ${h} ঘণ্টা`,
    trip: (km: number, h: number) => `${km} কিমি · প্রায় ${h} ঘণ্টা`,
    position: (km: number, to: string, eta: string) => `ট্রাক ${to} থেকে ${km} কিমি দূরে · পৌঁছাতে প্রায় ${eta} ঘণ্টা`,
    updated: (ago: string) => `${ago} হালনাগাদ`,
    ago: (s: number) => (s < 60 ? `${s} সেকেন্ড আগে` : s < 3600 ? `${Math.round(s / 60)} মিনিট আগে` : `${Math.round(s / 3600)} ঘণ্টা আগে`),
  },
};

/** How far along the road the truck is: by distance covered once the driver shares a position, else by stage. */
export function routeProgress(d: Delivery): number {
  if (d.status === "DELIVERED") return 1;
  if (d.position && d.distance_km > 0) return Math.min(1, Math.max(0, 1 - d.position.km_to_destination / d.distance_km));
  return d.status === "PICKED_UP" ? 0.5 : 0;
}

/**
 * The road from the farm to the buyer, with the truck on it. With a shared position the truck sits at the distance
 * covered and the line reads "Truck is 42 km from Dhaka · ETA 1.2 h · updated 30 s ago"; without one, by stage.
 */
export function RouteBar({ lot, className }: { lot: MarketLot; className?: string }) {
  const c = useCopy(COPY);
  const now = useNow(10_000);
  const d = lot.delivery;
  if (!d) return null;
  const position = d.status === "DELIVERED" ? null : d.position ?? null;
  const pct = routeProgress(d) * 100;
  return (
    <div className={cn("rounded-lg bg-slate-50 px-3 py-2.5 ring-1 ring-inset ring-slate-200", className)}>
      <div className="flex items-center gap-3" role="img" aria-label={c.route(d.origin_district, d.destination_district, d.distance_km, d.eta_hours)}>
        <span className="max-w-[35%] truncate text-[12.5px] font-medium text-slate-800">{lot.upazila ? `${lot.upazila}, ` : ""}{d.origin_district}</span>
        <span className="relative h-1 flex-1 rounded-full bg-slate-200">
          <span className="absolute inset-y-0 left-0 rounded-full bg-emerald-500 transition-[width] duration-700 ease-(--ease-out-expo)" style={{ width: `${pct}%` }} />
          <span className="absolute top-1/2 grid size-6 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-md bg-amber-600 text-white shadow-sm transition-[left] duration-700 ease-(--ease-out-expo)"
            style={{ left: `${pct}%` }}>
            <Truck className="size-3.5" aria-hidden />
          </span>
        </span>
        <span className="max-w-[35%] truncate text-right text-[12.5px] font-medium text-slate-800">{d.destination_district}</span>
      </div>
      <div className="num mt-1.5 text-center text-[12px] text-slate-500">{c.trip(d.distance_km, d.eta_hours)}</div>
      {position && (
        <p className="m-0 mt-1 text-center text-[12.5px] font-medium text-balance text-slate-800">
          {c.position(Math.round(position.km_to_destination), d.destination_district, position.eta_hours_left.toFixed(1))}
          <span className="font-normal text-slate-500"> · {c.updated(c.ago(Math.max(0, Math.round((now - Date.parse(position.at)) / 1000))))}</span>
        </p>
      )}
    </div>
  );
}
