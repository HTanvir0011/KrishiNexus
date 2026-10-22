"""Agent 3 — Cold-Storage Quota Clearinghouse & Arbitrage.

Compares selling the graded lot today through the pooled B2B truck with holding it in a BCSA cold
storage for up to 90 days. Uses ``coldchain-iot-mcp`` (open smallholder quota, chamber telemetry,
dynamic shelf life / lambda_rot, slot reservation) and ``dam-market-mcp`` (seasonal curve), evaluates

    dPi = [Q(1-lambda)E[P_future] - Q(C_storage + C_handling) - C_transport_storage] - [Q P_spot - C_transport_market]

at 30/60/90-day release dates, runs the Step 2 ``FinancialCircuitBreaker`` on the farmer's spot offer,
cross-checks it against the decision rule declared by the active prompt, and reserves a smallholder
slot only when storing beats the pooled sale.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from agents.state import ColdChainArbitragePlan, KrishiAgentState, StepType, StorageFacilityChoice
from agents.tracing import TraceRecorder
from config import now_bdt
from guardrails.financial_circuit import CIRCUIT_BREAKER, ArbitrageCheckInput
from mcp_servers import bd_geo
from mcp_servers.coldchain_iot_mcp import (
    OWNER_QUOTA_PCT,
    TRADER_QUOTA_PCT,
    calculate_dynamic_shelf_life,
    get_chamber_telemetry,
    query_cold_storage_quota,
    reserve_collective_storage_slot,
)
from mcp_servers.dam_market_mcp import SEASONAL_CURVES, get_historical_seasonal_curve, market_prices, pooled_truck_leg
from prompts.prompt_registry import PROMPT_REGISTRY, arbitrage_rule
from schemas.mcp_models import (
    CalculateDynamicShelfLifeInput,
    Crop,
    GetChamberTelemetryInput,
    GetHistoricalSeasonalCurveInput,
    Grade,
    PowerSource,
    QueryColdStorageQuotaInput,
    ReserveCollectiveStorageSlotInput,
)

AGENT = "coldchain_arbitrage"
STORABLE = frozenset({Crop.CARDINAL_POTATO, Crop.DIAMANT_POTATO})
HORIZONS_DAYS = (30, 60, 90)
STORAGE_RADIUS_KM = 60


async def run(state: KrishiAgentState, trace: TraceRecorder) -> dict[str, Any]:
    prompt = PROMPT_REGISTRY.active(AGENT)
    params = prompt.params
    q = state.quantity_kg
    floor = SEASONAL_CURVES[state.crop].production_cost_floor
    b2b = state.syndicate_bypass_plan
    b2b_net = b2b.b2b_net_tk_per_kg if b2b else 0.0
    spot = state.farmer_offer_tk_per_kg if state.farmer_offer_tk_per_kg is not None else (b2b.dam_grower_tk_per_kg if b2b else 0.0)
    grade = state.optical_grade_cert.market_grade if state.optical_grade_cert else Grade.B
    today = now_bdt().date()
    origin = bd_geo.resolve_district(state.district)
    quota_note = (f"Traders ({TRADER_QUOTA_PCT:g}%) and plant owners ({OWNER_QUOTA_PCT:g}%) hold "
                  f"{TRADER_QUOTA_PCT + OWNER_QUOTA_PCT:.2f}% of BCSA capacity; smallholders compete for the remaining 22.68%.")
    await trace.emit(AGENT, StepType.THOUGHT,
                     f"Q={q:g} kg, P_spot=Tk {spot:g}/kg (floor Tk {floor:g}), pooled B2B net Tk {b2b_net:g}/kg; "
                     f"rule '{prompt.variant_id}' ({prompt.version}).")

    months = [(today.month + k - 1) % 12 + 1 for k in range(4)]
    curve = await trace.mcp(AGENT, "get_historical_seasonal_curve", get_historical_seasonal_curve,
                            GetHistoricalSeasonalCurveInput(crop=state.crop, month_range=months),
                            lambda r: f"Seasonal curve {months}: best release month {r.best_release_month_in_range}; "
                                      f"harvest low Tk {r.harvest_distress_grower_price_tk_per_kg}/kg in month {r.harvest_distress_month}.")

    excluded = state.replan_reason.split(":", 1)[1] if state.replan_reason and state.replan_reason.startswith("exclude:") else None
    if state.crop not in STORABLE:
        await trace.emit(AGENT, StepType.THOUGHT, f"BCSA cold storages hold potatoes only; {state.crop.value} goes to the pooled sale.")
        plan = ColdChainArbitragePlan(
            decision="SELL_POOLED_B2B" if b2b else "SELL_SPOT", horizon_days=0, release_date=None,
            expected_future_price_tk_per_kg=None, best_release_month=curve.best_release_month_in_range, lambda_rot=None,
            facility=None, circuit_breaker=None, store_vs_b2b_delta_tk=None, b2b_net_tk_per_kg=b2b_net,
            distress_sale_blocked=bool(state.farmer_offer_tk_per_kg is not None and spot < floor and b2b_net > floor),
            block_reason=(f"Faria offer Tk {spot:g}/kg is below the Tk {floor:g}/kg cost floor while the pooled sale pays "
                          f"Tk {b2b_net:g}/kg." if spot < floor and b2b_net > floor else None),
            reservation=None, projected_net_tk_per_kg=b2b_net or spot, quota_capture_note=quota_note,
            math_trace=[f"{state.crop.value} is not cold-storable in BCSA facilities; dPi not applicable."],
            prompt_version=prompt.version,
        )
        return {"cold_storage_arbitrage_plan": plan, "prompt_versions": {**state.prompt_versions, AGENT: prompt.version},
                "trace_events": trace.drain()}

    quota = await trace.mcp(AGENT, "query_cold_storage_quota", query_cold_storage_quota,
                            QueryColdStorageQuotaInput(district=state.district, radius_km=STORAGE_RADIUS_KM, tons_needed=q / 1000),
                            lambda r: f"{r.facilities_found} BCSA facilities within {STORAGE_RADIUS_KM} km, "
                                      f"{r.total_open_smallholder_quota_mt:,.0f} t open smallholder quota.")
    candidates = [f for f in quota.facilities if f.can_fulfil_request and f.facility_id != excluded]
    row = candidates[0] if candidates else None
    facility: StorageFacilityChoice | None = None
    lambda_rot = 0.012
    if row is not None:
        telemetry = await trace.mcp(AGENT, "get_chamber_telemetry", get_chamber_telemetry,
                                    GetChamberTelemetryInput(facility_id=row.facility_id, chamber_id="CH-01"),
                                    lambda r: f"{r.facility_id}/CH-01: {r.temperature_f} F, {r.relative_humidity_pct}% RH, "
                                              f"{r.power_source.value}, rot risk {r.rot_risk_pct}%.")
        facility = StorageFacilityChoice(
            facility_id=row.facility_id, name=row.name, road_distance_km=row.road_distance_km,
            tariff_tk_per_kg=row.tariff_tk_per_kg, handling_fee_tk_per_kg=row.handling_fee_tk_per_kg,
            open_smallholder_quota_mt=row.open_smallholder_quota_mt, chamber_temperature_f=telemetry.temperature_f,
            chamber_rh_pct=telemetry.relative_humidity_pct,
            chamber_in_optimal_band=telemetry.temperature_in_optimal_band and telemetry.humidity_in_optimal_band,
            power_source=telemetry.power_source.value,
        )
        shelf = await trace.mcp(AGENT, "calculate_dynamic_shelf_life", calculate_dynamic_shelf_life,
                                CalculateDynamicShelfLifeInput(crop=state.crop, grade=grade, transit_temp_c=9.5, rh_pct=93.0),
                                lambda r: f"Grade {grade.value} at 9.5 C / 93% RH: {r.remaining_shelf_life_days:.0f} days, "
                                          f"lambda_rot {r.lambda_rot}.")
        lambda_rot = shelf.lambda_rot

    tariff = facility.tariff_tk_per_kg if facility else 9.0
    handling = facility.handling_fee_tk_per_kg if facility else 0.6
    transport_storage = 0.0
    if row is not None:
        storage_district = bd_geo.district_by_name(row.district)
        transport_storage = round(pooled_truck_leg(origin, storage_district, storage_district.lat, storage_district.lon).cost_per_kg * q, 2)

    math_trace = [f"Q={q:g} kg; lambda_rot={lambda_rot}; C_storage=Tk {tariff}/kg; C_handling=Tk {handling}/kg; "
                  f"C_transport_storage=Tk {transport_storage:,.2f}; C_transport_market=Tk 0 (Faria buys at farm gate)."]
    best_h, best_value, best_price = HORIZONS_DAYS[-1], float("-inf"), 0.0
    for h in HORIZONS_DAYS:
        price = market_prices(state.crop, origin, today + timedelta(days=h)).grower
        value = q * (1 - lambda_rot) * price - q * (tariff + handling) - transport_storage
        math_trace.append(f"release +{h} d: E[P]=Tk {price:.2f}/kg -> storage branch Tk {value:,.0f}")
        if value > best_value:
            best_h, best_value, best_price = h, value, price

    circuit = CIRCUIT_BREAKER.validate_arbitrage_recommendation(ArbitrageCheckInput(
        crop=state.crop, quantity_kg=q, spot_price_bdt=spot, expected_future_price_bdt=best_price,
        storage_tariff_bdt=tariff, handling_cost_bdt=handling, lambda_rot=lambda_rot,
        transport_to_storage_bdt=transport_storage, transport_to_market_bdt=0.0, district=state.district,
        holding_months=max(1, round(best_h / 30)),
    ))
    rule_label = arbitrage_rule(params, {"spot": spot, "dpi": circuit.delta_pi_bdt, "quota_ok": circuit.storage_can_absorb_lot})
    math_trace += [
        f"storage = Q(1-lambda)E - Q(Cs+Ch) - C_ts = Tk {circuit.storage_branch_value_bdt:,.2f}",
        f"spot = Q*P_spot - C_tm = Tk {circuit.spot_branch_value_bdt:,.2f}",
        f"dPi = Tk {circuit.delta_pi_bdt:,.2f} (Tk {circuit.delta_pi_per_kg_bdt}/kg); break-even E[P] = Tk "
        f"{circuit.break_even_future_price_bdt}/kg",
    ]
    await trace.emit(AGENT, StepType.GUARDRAIL,
                     f"FinancialCircuitBreaker {circuit.verdict.value}: dPi Tk {circuit.delta_pi_bdt:,.0f}; prompt rule says "
                     f"{rule_label}" + (" (agrees)." if (rule_label == "BLOCK") == circuit.circuit_tripped else " (DISAGREES)."),
                     tool="FinancialCircuitBreaker", data={"verdict": circuit.verdict.value, "delta_pi": circuit.delta_pi_bdt})

    b2b_value = q * b2b_net
    store_vs_b2b = round(circuit.storage_branch_value_bdt - b2b_value, 2)
    math_trace.append(f"pooled B2B now = Q*Tk {b2b_net:g} = Tk {b2b_value:,.2f}; storage - B2B = Tk {store_vs_b2b:,.2f}")
    if facility is not None and store_vs_b2b > 0:
        decision = "STORE_AND_FINANCE" if circuit.circuit_tripped else "STORE"
    elif b2b is not None:
        decision = "SELL_POOLED_B2B"
    else:
        decision = "STORE_AND_FINANCE" if circuit.circuit_tripped else "SELL_SPOT"

    blocked = state.farmer_offer_tk_per_kg is not None and spot < floor and (circuit.circuit_tripped or b2b_net > floor)
    reason = None
    if blocked:
        reason = (f"Faria offer Tk {spot:g}/kg is below the Tk {floor:g}/kg production-cost floor; "
                  + ("storing yields dPi Tk {:,.0f}".format(circuit.delta_pi_bdt) if circuit.circuit_tripped else "")
                  + (" and " if circuit.circuit_tripped and b2b_net > floor else "")
                  + (f"the pooled B2B truck pays Tk {b2b_net:g}/kg" if b2b_net > floor else "") + ".")

    reservation = None
    chamber_ok = facility is not None and facility.chamber_in_optimal_band and facility.power_source != PowerSource.OUTAGE.value
    if decision.startswith("STORE") and facility is not None and not chamber_ok:
        await trace.emit(AGENT, StepType.THOUGHT,
                         f"{facility.facility_id} chamber is out of the 48-50 F / 92-95% RH band or without power; "
                         "holding the reservation for supervisor re-planning.")
    if decision.startswith("STORE") and chamber_ok and facility is not None:
        reservation = await trace.mcp(AGENT, "reserve_collective_storage_slot", reserve_collective_storage_slot,
                                      ReserveCollectiveStorageSlotInput(cluster_id=f"SOLO-{state.farmer_id}"[:40],
                                                                        facility_id=facility.facility_id, tons=q / 1000, farmer_count=1),
                                      lambda r: f"{r.status.value}: receipt {r.receipt_id} for {r.reserved_tons} t at {r.facility_name}.")

    projected = round(circuit.storage_branch_value_bdt / q, 2) if decision.startswith("STORE") else b2b_net
    plan = ColdChainArbitragePlan(
        decision=decision, horizon_days=best_h, release_date=today + timedelta(days=best_h),
        expected_future_price_tk_per_kg=round(best_price, 2), best_release_month=curve.best_release_month_in_range,
        lambda_rot=lambda_rot, facility=facility, circuit_breaker=circuit, store_vs_b2b_delta_tk=store_vs_b2b,
        b2b_net_tk_per_kg=b2b_net, distress_sale_blocked=blocked, block_reason=reason, reservation=reservation,
        projected_net_tk_per_kg=projected, quota_capture_note=quota_note, math_trace=math_trace, prompt_version=prompt.version,
    )
    await trace.emit(AGENT, StepType.DECISION,
                     f"{decision}: projected net Tk {projected:g}/kg" + (f"; distress sale BLOCKED - {reason}" if blocked else "."),
                     data={"decision": decision, "store_vs_b2b": store_vs_b2b})
    return {
        "cold_storage_arbitrage_plan": plan,
        "replan_reason": None,
        "prompt_versions": {**state.prompt_versions, AGENT: prompt.version},
        "trace_events": trace.drain(),
    }


def needs_replan(plan: ColdChainArbitragePlan | None) -> str | None:
    """Supervisor review hook: a storing plan whose chamber is out of band or without power must re-plan."""
    if plan is None or not plan.decision.startswith("STORE") or plan.facility is None:
        return None
    if not plan.facility.chamber_in_optimal_band or plan.facility.power_source == PowerSource.OUTAGE.value:
        return f"exclude:{plan.facility.facility_id}"
    return None
