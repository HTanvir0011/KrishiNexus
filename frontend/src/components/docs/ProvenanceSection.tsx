import { CloudRain, Landmark, ShoppingBasket, Sigma, Snowflake, Sprout } from "lucide-react";
import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "../../lib/format";
import { Badge, type Tone } from "../ui";

/** MathML Core, rendered natively by the browser; React DOM creates these in the MathML namespace. */
type MathProps = HTMLAttributes<Element> & { display?: "block" | "inline"; mathvariant?: "normal" };
declare module "react" {
  namespace JSX {
    interface IntrinsicElements {
      math: MathProps; mrow: MathProps; mi: MathProps; mo: MathProps; mn: MathProps; mfrac: MathProps; msub: MathProps; msup: MathProps;
    }
  }
}

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

const CHIP: Record<Tone, string> = {
  emerald: "bg-emerald-50 text-emerald-700", amber: "bg-amber-100 text-amber-700", red: "bg-rose-100 text-rose-600",
  sky: "bg-sky-50 text-sky-700", violet: "bg-violet-50 text-violet-700", slate: "bg-slate-100 text-slate-700",
};

/** One display line; `w-max min-w-full` keeps it centred when it fits and scrollable (not clipped) when it does not. */
function Formula({ children }: { children: ReactNode }) {
  return <math display="block" className="w-max min-w-full text-[17px] text-slate-900">{children}</math>;
}

const FORMULAS: { title: string; math: ReactNode; text: string; where: string }[] = [
  {
    title: "Net farmer surplus ΔΠ (circuit breaker, Agent 3)",
    math: (
      <Formula>
        <mi>ΔΠ</mi><mo>=</mo>
        <mrow>
          <mo>[</mo>
          <mi>Q</mi><mo>(</mo><mn>1</mn><mo>−</mo><msub><mi>λ</mi><mi>rot</mi></msub><mo>)</mo>
          <mo>⋅</mo><mi mathvariant="normal">E</mi><mo>[</mo><msub><mi>P</mi><mi>future</mi></msub><mo>]</mo>
          <mo>−</mo><mi>Q</mi><mo>(</mo><msub><mi>C</mi><mi>storage</mi></msub><mo>+</mo><msub><mi>C</mi><mi>handling</mi></msub><mo>)</mo>
          <mo>−</mo><msub><mi>C</mi><mi>transport,storage</mi></msub>
          <mo>]</mo>
        </mrow>
        <mo>−</mo>
        <mrow>
          <mo>[</mo><mi>Q</mi><mo>⋅</mo><msub><mi>P</mi><mi>spot</mi></msub><mo>−</mo><msub><mi>C</mi><mi>transport,market</mi></msub><mo>]</mo>
        </mrow>
      </Formula>
    ),
    text: "ΔΠ is what the farmer gains by storing the lot instead of selling it today; the breaker blocks the spot sale when the spot price is below the Tk 15/kg production floor, open smallholder quota covers Q and ΔΠ > 0.",
    where: "backend/guardrails/financial_circuit.py · FinancialCircuitBreaker.validate_arbitrage_recommendation",
  },
  {
    title: "Aratdar take",
    math: (
      <>
        <Formula><mi>M</mi><mo>=</mo><msub><mi>P</mi><mi>wholesale</mi></msub><mo>−</mo><msub><mi>P</mi><mi>grower</mi></msub></Formula>
        <Formula><msub><mi>C</mi><mi>Bepari</mi></msub><mo>=</mo><mn>0.8</mn><mo>×</mo><mi>M</mi><mo>×</mo><mn>0.70</mn></Formula>
        <Formula><msub><mi>take</mi><mi>Aratdar</mi></msub><mo>=</mo><mn>0.6235</mn><mo>×</mo><msub><mi>C</mi><mi>Bepari</mi></msub></Formula>
      </>
    ),
    text: "M is the primary margin between wholesale and grower prices; the Bepari spends 70% of his 80% share on marketing, and the Aratdar keeps 62.35% of that marketing cost while spending Tk 0 on grading.",
    where: "backend/mcp_servers/dam_market_mcp.py · detect_syndicate_markup_anomaly",
  },
  {
    title: "Haor embankment breach probability",
    math: (
      <>
        <Formula>
          <mi>w</mi><mo>=</mo>
          <mfrac><mn>1</mn><mrow><mn>1</mn><mo>+</mo><msup><mi>e</mi><mrow><mo>(</mo><mi>dB</mi><mo>+</mo><mn>16.5</mn><mo>)</mo><mo>/</mo><mn>1.6</mn></mrow></msup></mrow></mfrac>
        </Formula>
        <Formula><mi>r</mi><mo>=</mo><mfrac><msub><mi>R</mi><mn>72</mn></msub><msub><mi>R</mi><mi>trigger</mi></msub></mfrac></Formula>
        <Formula>
          <mi>z</mi><mo>=</mo><mrow><mo>−</mo><mn>5.0</mn></mrow><mo>+</mo><mn>3.2</mn><mi>r</mi><mo>+</mo><mn>2.6</mn><mi>w</mi>
          <mo>+</mo><mn>2.0</mn><mo>⋅</mo><mi>vulnerability</mi><mo>+</mo><mn>1.2</mn><mo>⋅</mo><mi>seasonal_exposure</mi>
        </Formula>
        <Formula><mi>p</mi><mo>=</mo><mfrac><mn>1</mn><mrow><mn>1</mn><mo>+</mo><msup><mi>e</mi><mrow><mo>−</mo><mi>z</mi></mrow></msup></mrow></mfrac></Formula>
      </>
    ),
    text: "Darker radar backscatter (more open water, w) and more upstream rain against the district trigger (r) raise the 72-hour breach probability p; alert bands are RED ≥ 70%, ORANGE ≥ 45% and YELLOW ≥ 20%.",
    where: "backend/mcp_servers/agri_weather_sar_mcp.py · breach_probability()",
  },
];

export function ProvenanceSection() {
  return (
    <div className="space-y-4">
      <div className="surface p-5 sm:p-6">
        <div className="flex items-center gap-3">
          <span className={cn("grid size-9 shrink-0 place-items-center rounded-lg", CHIP.emerald)}><Sprout className="size-5" /></span>
          <h3 className="text-[16px] font-semibold tracking-[-0.01em] text-slate-900">Executive summary</h3>
        </div>
        <p className="mt-3 max-w-[760px] text-[15px] leading-relaxed text-slate-700">
          KrishiNexus OS is an edge-to-cloud multi-agent operating system for Bangladeshi smallholders. A farmer speaks in their own dialect;
          four agents grade the crop, expose the middleman markup, price cold storage against a pooled truck sale with the ΔΠ equation, clear
          72-hour flood risk and underwrite credit, then answer in spoken Bangla, online or offline at a union kiosk.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {CARDS.map((card) => (
          <article key={card.label} className="surface flex min-w-0 flex-col p-5">
            <span className={cn("grid size-9 place-items-center rounded-lg", CHIP[card.tone])}>{card.icon}</span>
            <div className="num mt-4 text-[32px] leading-none text-slate-900">{card.headline}</div>
            <h3 className="mt-2 text-[14px] font-medium text-slate-700">{card.label}</h3>
            <ul className="mt-3 space-y-1.5 text-[13.5px] leading-snug text-slate-600">
              {card.points.map((p) => (
                <li key={p} className="flex gap-2.5"><span className="mt-[0.45em] size-1.5 shrink-0 rounded-full bg-slate-300" aria-hidden />{p}</li>
              ))}
            </ul>
            <div className="mt-auto space-y-2 pt-4">
              <div className="border-t border-slate-100 pt-3 text-[12px] text-slate-500">
                Source cited in brief: <span className="font-medium text-slate-700">{card.source}</span>
              </div>
              <Badge tone="emerald" className="whitespace-normal">{card.product}</Badge>
            </div>
          </article>
        ))}
      </div>
      <p className="text-[12px] text-slate-500">
        Figures are as cited in the KrishiNexus project brief with the originating organisation named on each card.
        The live system below computes its own numbers from seeded DAM/BCSA data; it does not depend on these headline figures.
      </p>

      <div className="surface">
        <div className="flex items-center gap-3 border-b border-slate-200 px-5 py-4">
          <span className={cn("grid size-9 shrink-0 place-items-center rounded-lg", CHIP.sky)}><Sigma className="size-5" /></span>
          <div className="min-w-0">
            <h3 className="text-[16px] font-semibold tracking-[-0.01em] text-slate-900">Formulas</h3>
            <p className="text-[13px] text-slate-500">The equations the agents evaluate, as written in the backend.</p>
          </div>
        </div>
        <div className="divide-y divide-slate-100">
          {FORMULAS.map((f) => (
            <figure key={f.title} className="min-w-0 px-5 py-5">
              <h4 className="text-[14px] font-semibold text-slate-900">{f.title}</h4>
              <div className="scroll-thin mt-3 space-y-3 overflow-x-auto rounded-lg bg-slate-50 px-4 py-3 ring-1 ring-slate-200 ring-inset">{f.math}</div>
              <figcaption className="mt-3">
                <p className="text-[14px] leading-relaxed text-slate-600">{f.text}</p>
                <code className="mt-1.5 block font-mono text-[12px] text-slate-500 wrap-anywhere">{f.where}</code>
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    </div>
  );
}
