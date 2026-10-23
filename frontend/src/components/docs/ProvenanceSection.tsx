import { CloudRain, Landmark, ShoppingBasket, Snowflake, Sprout } from "lucide-react";
import type { ReactNode } from "react";

import { Badge, type Tone } from "../ui";

interface EvidenceCard {
  icon: ReactNode;
  tone: Tone;
  headline: string;
  label: string;
  points: string[];
  source: string;
  product: string;
}

const CARDS: EvidenceCard[] = [
  {
    icon: <ShoppingBasket className="size-5" />, tone: "amber", headline: "$2.4B / yr", label: "Post-harvest perishable spoilage",
    points: [
      "25–43.5% of fruit and vegetables lost between field and consumer",
      "Jackfruit 38% · banana 37% · pineapple 27% · mango 24%",
      "30.8% loss borne by banana traders alone",
      "Sorting, grading + MAP packaging: +32% seasonal income (+US$947)",
    ],
    source: "BAU post-harvest loss studies", product: "Optical grading + MAP packaging + cold-chain routing",
  },
  {
    icon: <Landmark className="size-5" />, tone: "red", headline: "116%", label: "Syndicate producer-to-retail markup",
    points: [
      "5 tiers: Faria → Bepari → Aratdar → Paiker → Retailer",
      "Aratdars extract 62.35% of the Bepari's marketing cost and spend Tk 0 on grading",
      "Food carries 59% of the CPI basket weight",
    ],
    source: "Centre for Policy Dialogue (CPD), July 2026 study", product: "Syndicate-bypass agent + 5-ton pooled trucks",
  },
  {
    icon: <Snowflake className="size-5" />, tone: "violet", headline: "77.32%", label: "Cold-storage quota held by non-farmers",
    points: [
      "12–13M MT potato output vs 2.7–3.27M MT storage in 300–393 plants ($430M lost a year)",
      "Traders 45% + plant owners 32.32%; farmers left with 22.68%",
      "Tariff doubled from Tk 4–5.50 to Tk 8.00–9.50/kg; Tk 19–20/kg all-in at Thakurgaon",
      "Distress farm-gate Tk 5–14/kg vs Tk 15–20/kg cost; off-season Tk 80–90/kg",
      "48–50°F and 92–95% RH prevent 2–9% internal rot",
    ],
    source: "Bangladesh Cold Storage Association (BCSA) / DAM", product: "Quota clearinghouse + ΔΠ circuit-breaker",
  },
  {
    icon: <CloudRain className="size-5" />, tone: "sky", headline: "65%", label: "Boro lost to the 2017 haor flash flood",
    points: [
      "Sunamganj 65% · Kishoreganj 44% · Netrokona 21%",
      "Sentinel-1 radar sees through monsoon cloud where optical Landsat fails, finding 2× the damage manual surveys record",
      "Partners: 66 WFP aggregation centres (62 Cox's Bazar, 4 Kurigram), iFarmer, UCB 6% collateral-free agri-credit",
    ],
    source: "FFWC / DAE haor loss records; WFP, iFarmer, UCB", product: "SAR flood shield + parametric credit",
  },
];

export function ProvenanceSection() {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-emerald-500/30 bg-gradient-to-br from-emerald-500/10 to-transparent p-4">
        <div className="flex items-center gap-2 label text-[13px] font-semibold text-emerald-300"><Sprout className="size-4" /> Executive summary</div>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-200">
          KrishiNexus OS is an edge-to-cloud multi-agent operating system for Bangladeshi smallholders. A farmer speaks in their own dialect;
          four agents grade the crop, expose the middleman markup, price cold storage against a pooled truck sale with the ΔΠ equation, clear
          72-hour flood risk and underwrite credit, then answer in spoken Bangla, online or offline at a union kiosk.
        </p>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {CARDS.map((card) => (
          <article key={card.label} className="panel p-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="num text-4xl leading-none text-slate-50">{card.headline}</div>
                <div className="text-sm font-medium text-slate-300">{card.label}</div>
              </div>
              <Badge tone={card.tone}>{card.icon}</Badge>
            </div>
            <ul className="mt-3 space-y-1 text-xs text-slate-300">
              {card.points.map((p) => <li key={p} className="flex gap-2"><span className="text-emerald-400">▸</span>{p}</li>)}
            </ul>
            <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-ink-700 pt-2 text-[10px]">
              <span className="text-slate-500">Source cited in brief:</span><span className="text-slate-300">{card.source}</span>
              <Badge tone="emerald" className="ml-auto">{card.product}</Badge>
            </div>
          </article>
        ))}
      </div>
      <p className="text-[11px] text-slate-500">
        Figures are as cited in the KrishiNexus project brief with the originating organisation named on each card.
        The live system below computes its own numbers from seeded DAM/BCSA data; it does not depend on these headline figures.
      </p>
    </div>
  );
}
