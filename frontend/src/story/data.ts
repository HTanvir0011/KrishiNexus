/**
 * Facts the story tells, taken from three live calls (Rahim's voice preset, his price ladder, Abdul's
 * voice preset). When the backend is unreachable the page falls back to a snapshot of a live run on
 * 24 Oct 2026 and says so; nothing on the page is typed in by hand.
 */

import { useEffect, useState } from "react";

import { api, mcpCall, withFallback, type QuotaResult, type VoiceInteractResponse } from "../api/client";
import { englishSummary } from "../lib/summary";

export type SourceStatus = "loading" | "live" | "cached";

export interface Sourced<T> {
  data: T;
  status: SourceStatus;
}

export interface Tier {
  tier: string;
  role: string;
  buy: number;
  sell: number;
  margin: number;
}

export interface Ladder {
  grower: number;
  wholesale: number;
  retail: number;
  markupPct: number;
  farmerSharePct: number;
  bepariCost: number;
  aratdarTake: number;
  aratdarSharePct: number;
  tiers: Tier[];
  marketDate: string;
}

export interface RahimFacts {
  dialect: string;
  scrubbed: string;
  piiHidden: number;
  quantityKg: number;
  quantityExpression: string | null;
  cropLocal: string | null;
  crop: string;
  offer: number;
  worriedAboutRot: boolean;
  spokenBn: string;
  english: string;
  grade: string | null;
  bestHub: string;
  freight: number;
  b2bNet: number;
  lotValueB2b: number;
  pool: { id: string; current: number; after: number; capacity: number; neighbours: number } | null;
  floor: number;
  spotValue: number;
  storageValue: number;
  horizonDays: number;
  futurePrice: number | null;
  lambdaRot: number | null;
  blocked: boolean;
  decision: string;
  facility: { name: string; tariff: number; tempF: number; rh: number; inBand: boolean } | null;
  credit: { score: number; band: string; eligible: boolean; amount: number; rate: number; tenor: number } | null;
}

export interface AbdulFacts {
  scrubbed: string;
  breachPct: number | null;
  alertLevel: string | null;
  sarDb: number | null;
  rain72h: number;
  advice: string;
  creditScore: number | null;
  loan: number | null;
}

export interface StoryFacts {
  rahim: Sourced<RahimFacts>;
  ladder: Sourced<Ladder>;
  abdul: Sourced<AbdulFacts>;
}

export const SNAPSHOT_DATE = "24 Oct 2026";

const TIER_ROLES: Record<string, string> = {
  Faria: "village trader at the farm gate",
  Bepari: "assembler who trucks lots to the city",
  Aratdar: "commission agent at the Karwan Bazar arat",
  Paiker: "wholesaler who buys from the arat",
  Retailer: "the Dhaka market stall",
};

const RAHIM_SPOKEN =
  "আপনার ৪০০ কেজি কার্ডিনাল আলু গ্রেড-এ (সুপারশপ/রপ্তানি মান) সনদ পেয়েছে। ফড়িয়ার ১২ টাকা দাম উৎপাদন খরচের (কেজি ১৫ টাকা) নিচে, তাই এই বিক্রি আটকে দেওয়া হয়েছে। " +
  "বাজারে খুচরা দাম কৃষকের দামের চেয়ে ১১৫% বেশি — এটা সিন্ডিকেটের মুনাফা। ৫ টনের যৌথ ট্রাকে সরাসরি Mirpur Supermarket Consolidation DC-এ বিক্রি করলে কেজিতে ৬১.৯১ টাকা পাবেন। " +
  "আপনার ইউনিয়নের ট্রাকে এখন ৩,১৫০ কেজি আছে; আপনার মাল যোগ হলে ৩,৫৫০ কেজি হবে। হিমাগারে ৩০ দিন রাখলে খামারে দাম প্রায় ৩০.৩৯ টাকায় নামতে পারে, তাই এখন যৌথ ট্রাকে বিক্রি করাই লাভজনক। " +
  "আগামী ৭২ ঘণ্টায় ঝড় বা বন্যার বড় ঝুঁকি নেই। আপনার কৃষি-ঋণ স্কোর ৭৭৫; ১৪,৫০০ টাকা পর্যন্ত ৬% সুদে চলতি মূলধন ঋণ প্রস্তুত। রাজি থাকলে 'হ্যাঁ' বলুন, আমরা ট্রাক ও ঋণের কাজ শুরু করব।";

export const RAHIM_SNAPSHOT: RahimFacts = {
  dialect: "Rangpuri",
  scrubbed: "বাহে, মুই মিঠাপুকুরের রহিম মিয়া, মোবাইল <BD_PHONE_REDACTED>। হামার ঘরত দশ মণ লাল পাকরি আলু আছে। ফড়িয়া কয় বারো টাকা কেজি দিবে। এলা বেচমু না হিমাগারত থুমু? আলু পচি যাইবে কিনা চিন্তাত আছোঁ।",
  piiHidden: 1,
  quantityKg: 400,
  quantityExpression: "10 মণ",
  cropLocal: "লাল পাকরি",
  crop: "Cardinal Potato",
  offer: 12,
  worriedAboutRot: true,
  spokenBn: RAHIM_SPOKEN,
  english:
    "Your 400 kilograms of Cardinal Potato are certified Grade-A Export/Supermarket. The middleman offer of 12 taka per kilo is below the 15 taka production cost, so that sale is blocked. " +
    "A pooled five-ton truck to Mirpur Supermarket Consolidation DC pays 61.91 taka per kilo. Your agri-credit score is 775; up to 14500 taka working capital is pre-approved.",
  grade: "Grade-A Export/Supermarket",
  bestHub: "Mirpur Supermarket Consolidation DC",
  freight: 5.07,
  b2bNet: 61.91,
  lotValueB2b: 24764,
  pool: { id: "POOL-RANGPUR-01", current: 3150, after: 3550, capacity: 5000, neighbours: 8 },
  floor: 15,
  spotValue: 4800,
  storageValue: 8298.13,
  horizonDays: 30,
  futurePrice: 30.39,
  lambdaRot: 0.012,
  blocked: true,
  decision: "SELL_POOLED_B2B",
  facility: { name: "Mithapukur Cold Storage", tariff: 8.25, tempF: 49.34, rh: 94.13, inBand: true },
  credit: { score: 775, band: "Excellent", eligible: true, amount: 14500, rate: 6, tenor: 4 },
};

export const LADDER_SNAPSHOT: Ladder = {
  grower: 36.18,
  wholesale: 59.2,
  retail: 77.67,
  markupPct: 114.68,
  farmerSharePct: 46.58,
  bepariCost: 12.89,
  aratdarTake: 8.04,
  aratdarSharePct: 62.35,
  marketDate: "2026-10-24",
  tiers: [
    { tier: "Faria", role: TIER_ROLES.Faria, buy: 36.18, sell: 40.78, margin: 4.6 },
    { tier: "Bepari", role: TIER_ROLES.Bepari, buy: 40.78, sell: 51.16, margin: 10.38 },
    { tier: "Aratdar", role: TIER_ROLES.Aratdar, buy: 51.16, sell: 59.2, margin: 8.04 },
    { tier: "Paiker", role: TIER_ROLES.Paiker, buy: 59.2, sell: 65.66, margin: 6.46 },
    { tier: "Retailer", role: TIER_ROLES.Retailer, buy: 65.66, sell: 77.67, margin: 12.01 },
  ],
};

/** `query_cold_storage_quota` for Rangpur, 60 km radius, from the same live run. */
export const RANGPUR_QUOTA_SNAPSHOT: QuotaResult = {
  district: "Rangpur",
  total_open_smallholder_quota_mt: 2045.5,
  facilities: [
    { facility_id: "BCSA-RAN-02", name: "Mithapukur Cold Storage", total_capacity_mt: 9000, trader_quota_mt: 4050, owner_quota_mt: 2908.8,
      farmer_quota_mt: 2041.2, farmer_quota_booked_mt: 1506.4, open_smallholder_quota_mt: 534.8, tariff_tk_per_kg: 8.25, power_status: "GRID" },
    { facility_id: "BCSA-RAN-03", name: "Badarganj Agro Himagar", total_capacity_mt: 8200, trader_quota_mt: 3690, owner_quota_mt: 2650.2,
      farmer_quota_mt: 1859.8, farmer_quota_booked_mt: 1171.6, open_smallholder_quota_mt: 688.1, tariff_tk_per_kg: 8.25, power_status: "GRID" },
    { facility_id: "BCSA-RAN-01", name: "Rangpur Uttara Himagar Ltd.", total_capacity_mt: 10500, trader_quota_mt: 4725, owner_quota_mt: 3393.6,
      farmer_quota_mt: 2381.4, farmer_quota_booked_mt: 1883.7, open_smallholder_quota_mt: 497.7, tariff_tk_per_kg: 9.25, power_status: "GRID" },
    { facility_id: "BCSA-RAN-04", name: "Kaunia Teesta Cold Storage", total_capacity_mt: 7500, trader_quota_mt: 3375, owner_quota_mt: 2424,
      farmer_quota_mt: 1701, farmer_quota_booked_mt: 1376.1, open_smallholder_quota_mt: 324.9, tariff_tk_per_kg: 9.25, power_status: "GRID" },
  ],
};

export const ABDUL_SNAPSHOT: AbdulFacts = {
  scrubbed: "আমি তাহিরপুরর কৃষক আব্দুল, আমার নম্বর <BD_PHONE_REDACTED>। হাওরো বোরো ধান পাকি গেছে, পাহাড়ি ঢল আইতাছে হুনছি। চাইর একর জমির ধান কিতা করমু? অখন কাটমু নি?",
  breachPct: 4.67,
  alertLevel: "GREEN",
  sarDb: -12.72,
  rain72h: 0,
  advice: "হাওরে বাঁধ ভাঙার সম্ভাবনা এখন ৫%; স্বাভাবিক সময়সূচিতে ধান কাটুন।",
  creditScore: 720,
  loan: 50000,
};

function firstSentence(text: string): string {
  const match = /^[^।!?]*[।!?]/.exec(text.trim());
  return match ? match[0] : text;
}

export function rahimFrom(r: VoiceInteractResponse): RahimFacts | null {
  const state = r.orchestration?.state;
  const syndicate = state?.syndicate_bypass_plan;
  const cold = state?.cold_storage_arbitrage_plan;
  if (!state || !syndicate || !cold) return null;
  const credit = state.climate_credit_report;
  const entities = r.transcription.entities;
  return {
    dialect: r.transcription.dialect,
    scrubbed: r.transcription.scrubbed_transcript,
    piiHidden: r.transcription.pii_entities.length,
    quantityKg: state.quantity_kg,
    quantityExpression: entities.quantity_expression ?? null,
    cropLocal: entities.crop_local_term,
    crop: state.crop,
    offer: state.farmer_offer_tk_per_kg ?? syndicate.farmer_offer_tk_per_kg ?? 0,
    worriedAboutRot: (entities.concepts ?? []).includes("rot"),
    spokenBn: r.spoken_response_bn,
    english: englishSummary(r),
    grade: state.optical_grade_cert?.grade ?? null,
    bestHub: syndicate.best_hub_name,
    freight: syndicate.pooled_transport_tk_per_kg,
    b2bNet: syndicate.b2b_net_tk_per_kg,
    lotValueB2b: syndicate.lot_value_b2b_tk,
    pool: syndicate.pool
      ? { id: syndicate.pool.pool_id, current: syndicate.pool.current_kg, after: syndicate.pool.after_join_kg,
          capacity: syndicate.pool.capacity_kg, neighbours: syndicate.pool.neighbor_farmers }
      : null,
    floor: cold.circuit_breaker?.production_cost_floor_bdt ?? 15,
    spotValue: cold.circuit_breaker?.spot_branch_value_bdt ?? state.quantity_kg * (state.farmer_offer_tk_per_kg ?? 0),
    storageValue: cold.circuit_breaker?.storage_branch_value_bdt ?? 0,
    horizonDays: cold.horizon_days,
    futurePrice: cold.expected_future_price_tk_per_kg,
    lambdaRot: cold.lambda_rot,
    blocked: cold.distress_sale_blocked,
    decision: cold.decision,
    facility: cold.facility
      ? { name: cold.facility.name, tariff: cold.facility.tariff_tk_per_kg, tempF: cold.facility.chamber_temperature_f,
          rh: cold.facility.chamber_rh_pct, inBand: cold.facility.chamber_in_optimal_band }
      : null,
    credit: credit
      ? { score: credit.credit_score, band: credit.score_band, eligible: credit.loan_eligible, amount: credit.loan_amount_tk,
          rate: credit.annual_rate_pct, tenor: credit.tenor_months }
      : null,
  };
}

export function abdulFrom(r: VoiceInteractResponse): AbdulFacts | null {
  const credit = r.orchestration?.state.climate_credit_report;
  if (!credit) return null;
  return {
    scrubbed: r.transcription.scrubbed_transcript,
    breachPct: credit.flood_breach_probability_pct,
    alertLevel: credit.flood_alert_level,
    sarDb: credit.sar_backscatter_db,
    rain72h: credit.rain_next_72h_mm,
    advice: firstSentence(r.spoken_response_bn),
    creditScore: credit.credit_score,
    loan: credit.loan_eligible ? credit.loan_amount_tk : null,
  };
}

interface DetectOutput {
  grower_price_tk_per_kg: number;
  wholesale_price_tk_per_kg: number;
  retail_price_tk_per_kg: number;
  markup_pct: number;
  farmer_share_of_retail_pct: number;
  bepari_marketing_cost_tk_per_kg: number;
  aratdar_take_tk_per_kg: number;
  aratdar_share_of_bepari_marketing_cost_pct: number;
  market_date: string;
  tier_breakdown: { tier: string; buy_price_tk_per_kg: number; sell_price_tk_per_kg: number; gross_margin_tk_per_kg: number }[];
}

function ladderFrom(d: DetectOutput): Ladder {
  return {
    grower: d.grower_price_tk_per_kg,
    wholesale: d.wholesale_price_tk_per_kg,
    retail: d.retail_price_tk_per_kg,
    markupPct: d.markup_pct,
    farmerSharePct: d.farmer_share_of_retail_pct,
    bepariCost: d.bepari_marketing_cost_tk_per_kg,
    aratdarTake: d.aratdar_take_tk_per_kg,
    aratdarSharePct: d.aratdar_share_of_bepari_marketing_cost_pct,
    marketDate: d.market_date,
    tiers: d.tier_breakdown.map((t) => ({
      tier: t.tier, role: TIER_ROLES[t.tier] ?? t.tier, buy: t.buy_price_tk_per_kg, sell: t.sell_price_tk_per_kg, margin: t.gross_margin_tk_per_kg,
    })),
  };
}

/** Live facts for the whole story, with per-source status for honest labelling. */
export function useStoryFacts(): StoryFacts {
  const [rahim, setRahim] = useState<Sourced<RahimFacts>>({ data: RAHIM_SNAPSHOT, status: "loading" });
  const [ladder, setLadder] = useState<Sourced<Ladder>>({ data: LADDER_SNAPSHOT, status: "loading" });
  const [abdul, setAbdul] = useState<Sourced<AbdulFacts>>({ data: ABDUL_SNAPSHOT, status: "loading" });

  useEffect(() => {
    let active = true;
    const cachedRahim = { data: RAHIM_SNAPSHOT, status: "cached" as const };
    const cachedAbdul = { data: ABDUL_SNAPSHOT, status: "cached" as const };

    api.voiceInteract({ preset_id: "rangpur_potato_distress" })
      .then((r) => {
        const facts = r.live ? rahimFrom(r.data) : null;
        if (active) setRahim(facts ? { data: facts, status: "live" } : cachedRahim);
      })
      .catch(() => active && setRahim(cachedRahim));

    withFallback(
      () => mcpCall<DetectOutput>("detect_syndicate_markup_anomaly", { crop: "Cardinal Potato", upazila: "Mithapukur", retail_hub: "Dhaka Karwan Bazar" }),
      () => null,
    )
      .then((r) => active && setLadder(r.live && r.data ? { data: ladderFrom(r.data), status: "live" } : { data: LADDER_SNAPSHOT, status: "cached" }))
      .catch(() => active && setLadder({ data: LADDER_SNAPSHOT, status: "cached" }));

    api.voiceInteract({ preset_id: "sunamganj_haor_flood" })
      .then((r) => {
        const facts = r.live ? abdulFrom(r.data) : null;
        if (active) setAbdul(facts ? { data: facts, status: "live" } : cachedAbdul);
      })
      .catch(() => active && setAbdul(cachedAbdul));

    return () => {
      active = false;
    };
  }, []);

  return { rahim, ladder, abdul };
}
