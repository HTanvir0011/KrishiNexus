import type { VoiceInteractResponse } from "../api/client";

/** Plain-English version of the agents' decision, built from the same numbers as the Bangla answer. */
export function englishSummary(response: VoiceInteractResponse): string {
  const state = response.orchestration?.state;
  if (!state) return response.follow_up_question_bn ?? "";
  const syndicate = state.syndicate_bypass_plan;
  const cold = state.cold_storage_arbitrage_plan;
  const credit = state.climate_credit_report;
  return [
    state.optical_grade_cert && `Your ${state.quantity_kg} kilograms of ${state.crop} are certified ${state.optical_grade_cert.grade}.`,
    cold?.distress_sale_blocked &&
      `The middleman offer of ${state.farmer_offer_tk_per_kg} taka per kilo is below the 15 taka production cost, so that sale is blocked.`,
    syndicate && `A pooled five-ton truck to ${syndicate.best_hub_name} pays ${syndicate.b2b_net_tk_per_kg.toFixed(2)} taka per kilo.`,
    credit?.flood_applicable && credit.flood_breach_probability_pct !== null &&
      `The chance of an embankment breach in the next 72 hours is ${credit.flood_breach_probability_pct.toFixed(1)} percent.`,
    credit?.loan_eligible && `Your agri-credit score is ${credit.credit_score}; up to ${credit.loan_amount_tk} taka working capital is pre-approved.`,
  ].filter(Boolean).join(" ");
}
