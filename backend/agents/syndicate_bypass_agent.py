"""Agent 2 — Syndicate-Bypass & 5-Ton Truck-Pooling.

Exposes the 5-tier intermediary markup with ``dam-market-mcp`` (daily spread, syndicate anomaly,
optimal hub ranking for a full pooled truckload), compares it with the Faria's offer, and matches the
farmer's graded micro-lot to the open union truck pool within a 5 km radius. The pool match is a
proposal: the lot is only committed when the farmer approves (``POST /automation/truck-pools/join``).
"""

from __future__ import annotations

from typing import Any

from agents.state import KrishiAgentState, PoolMatch, StepType, SyndicateBypassPlan, TierCapture
from agents.tracing import TraceRecorder
from automation.workflows import TRUCK_POOLS, UNION_RADIUS_KM
from mcp_servers.dam_market_mcp import (
    TRUCK_CAPACITY_KG,
    detect_syndicate_markup_anomaly,
    find_optimal_selling_hub,
    get_daily_commodity_spread,
)
from prompts.prompt_registry import PROMPT_REGISTRY
from schemas.mcp_models import (
    DetectSyndicateMarkupAnomalyInput,
    FindOptimalSellingHubInput,
    GetDailyCommoditySpreadInput,
    Grade,
)

AGENT = "syndicate_bypass"
RETAIL_HUB = "Dhaka Karwan Bazar"


async def run(state: KrishiAgentState, trace: TraceRecorder) -> dict[str, Any]:
    prompt = PROMPT_REGISTRY.active(AGENT)
    threshold = float(prompt.params["anomaly_threshold_pct"])
    grade = state.optical_grade_cert.market_grade if state.optical_grade_cert else Grade.B
    await trace.emit(AGENT, StepType.THOUGHT,
                     f"Pricing {state.quantity_kg:g} kg {grade.value}-grade {state.crop.value} from {state.upazila}; "
                     f"anomaly threshold {threshold:g}% ({prompt.version}).")

    spread = await trace.mcp(AGENT, "get_daily_commodity_spread", get_daily_commodity_spread,
                             GetDailyCommoditySpreadInput(crop=state.crop, district=state.district),
                             lambda r: f"DAM {r.district}: grower Tk {r.grower_price_tk_per_kg}, wholesale Tk "
                                       f"{r.wholesale_price_tk_per_kg}, retail Tk {r.retail_price_tk_per_kg}/kg.")
    anomaly = await trace.mcp(AGENT, "detect_syndicate_markup_anomaly", detect_syndicate_markup_anomaly,
                              DetectSyndicateMarkupAnomalyInput(crop=state.crop, upazila=state.upazila, retail_hub=RETAIL_HUB),
                              lambda r: f"{r.markup_pct:.1f}% producer-to-retail markup ({r.severity.value}); Aratdar "
                                        f"takes Tk {r.aratdar_take_tk_per_kg}/kg = {r.aratdar_share_of_bepari_marketing_cost_pct:.2f}% "
                                        f"of Bepari marketing cost, Tk {r.aratdar_grading_spend_tk_per_kg:g} on grading.")
    hubs = await trace.mcp(AGENT, "find_optimal_selling_hub", find_optimal_selling_hub,
                           FindOptimalSellingHubInput(crop=state.crop, weight_kg=TRUCK_CAPACITY_KG,
                                                      origin_district=state.district, grade=grade),
                           lambda r: (f"Best pooled buyer: {r.best_option.hub_name} at net Tk {r.best_option.net_payout_tk_per_kg}/kg "
                                      f"({r.hubs_evaluated} hubs ranked).") if r.best_option else "No hub buys this grade.")
    best = hubs.best_option
    if best is None:
        return {"errors": [f"{AGENT}: no buyer accepts {grade.value}-grade {state.crop.value}"], "trace_events": trace.drain()}

    pool = TRUCK_POOLS.open_pool_for(state.district, state.upazila, state.crop)
    match: PoolMatch | None = None
    if pool is not None:
        after = min(pool.capacity_kg, pool.loaded_kg + state.quantity_kg)
        match = PoolMatch(pool_id=pool.pool_id, upazila=pool.upazila, union_radius_km=UNION_RADIUS_KM,
                          current_kg=pool.loaded_kg, after_join_kg=after, capacity_kg=pool.capacity_kg,
                          fill_pct_after_join=round(after / pool.capacity_kg * 100, 1), neighbor_farmers=len(pool.lots),
                          will_trigger_dispatch=after >= pool.capacity_kg, status=pool.status.value)
        await trace.emit(AGENT, StepType.THOUGHT,
                         f"Matched to {pool.pool_id} ({pool.union}, {pool.upazila}): {pool.loaded_kg:g} -> {after:g} kg of "
                         f"{pool.capacity_kg:g} kg with {len(pool.lots)} neighbours"
                         + (" - this lot completes the truck." if match.will_trigger_dispatch else "."))
    else:
        await trace.emit(AGENT, StepType.THOUGHT, f"No open {state.crop.value} pool in {state.district}; a new union pool would open.")

    offer = state.farmer_offer_tk_per_kg
    is_anomaly = anomaly.markup_pct > threshold
    shortfall = round(best.net_payout_tk_per_kg - offer, 2) if offer is not None else None
    offer_text = (f"Faria offers Tk {offer:g}/kg, Tk {shortfall:.2f}/kg below the pooled direct sale. " if offer is not None else "")
    alert = (
        f"{'SYNDICATE ALERT' if is_anomaly else 'Market check'}: {offer_text}DAM farm-gate today is Tk "
        f"{spread.grower_price_tk_per_kg}/kg while {RETAIL_HUB} retail is Tk {anomaly.retail_price_tk_per_kg}/kg "
        f"({anomaly.markup_pct:.0f}% markup, {anomaly.severity.value}). A pooled 5-ton truck to {best.hub_name} nets "
        f"Tk {best.net_payout_tk_per_kg}/kg after Tk {best.transport_cost_tk_per_kg}/kg freight."
    )
    plan = SyndicateBypassPlan(
        farmer_offer_tk_per_kg=offer,
        dam_grower_tk_per_kg=spread.grower_price_tk_per_kg,
        dam_wholesale_tk_per_kg=spread.wholesale_price_tk_per_kg,
        dam_retail_tk_per_kg=spread.retail_price_tk_per_kg,
        markup_pct=anomaly.markup_pct,
        severity=anomaly.severity,
        anomaly_threshold_pct=threshold,
        is_anomaly=is_anomaly,
        aratdar_share_of_bepari_marketing_cost_pct=anomaly.aratdar_share_of_bepari_marketing_cost_pct,
        aratdar_take_tk_per_kg=anomaly.aratdar_take_tk_per_kg,
        aratdar_grading_spend_tk_per_kg=anomaly.aratdar_grading_spend_tk_per_kg,
        tier_breakdown=[TierCapture(tier=t.tier.value, gross_margin_tk_per_kg=t.gross_margin_tk_per_kg,
                                    share_of_total_margin_pct=t.share_of_total_margin_pct) for t in anomaly.tier_breakdown],
        best_hub_id=best.hub_id,
        best_hub_name=best.hub_name,
        best_hub_type=best.hub_type,
        best_hub_district=best.district,
        pooled_transport_tk_per_kg=best.transport_cost_tk_per_kg,
        b2b_net_tk_per_kg=best.net_payout_tk_per_kg,
        offer_shortfall_tk_per_kg=shortfall,
        lot_value_offer_tk=round(offer * state.quantity_kg, 2) if offer is not None else None,
        lot_value_b2b_tk=round(best.net_payout_tk_per_kg * state.quantity_kg, 2),
        pool=match,
        anomaly_alert=alert,
        prompt_version=prompt.version,
    )
    await trace.emit(AGENT, StepType.DECISION, alert, data={"is_anomaly": is_anomaly, "pool_id": match.pool_id if match else None})
    return {
        "syndicate_bypass_plan": plan,
        "prompt_versions": {**state.prompt_versions, AGENT: prompt.version},
        "trace_events": trace.drain(),
    }
