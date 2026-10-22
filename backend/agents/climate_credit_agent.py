"""Agent 4 — SAR-Weather Harvest Shield & Parametric Credit Underwriter.

Uses ``agri-weather-sar-mcp`` (live weather, 72-hour hourly forecast, haor flash-flood risk from
Sentinel-1 backscatter + upstream rain, crop VPD/fungal stress, early-harvest dispatch) to clear the
next 72 hours, then computes a verifiable Alternative Agri-Credit Score (300-850) from evidence the
other agents produced: the signed quality certificate, the pooled B2B contract, the cold-storage
warehouse receipt, climate risk and agronomic risk.

Score = 300 + grade (<=120) + market linkage (<=110) + collateral (<=100) + climate (<=120)
            + agronomic (<=60) + verified identity (<=40)
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from agents.state import ClimateCreditReport, KrishiAgentState, ScoreComponent, StepType
from agents.tracing import TraceRecorder
from config import now_bdt
from mcp_servers import bd_geo
from mcp_servers.agri_weather_sar_mcp import (
    HAOR_UPAZILAS,
    calculate_haor_flash_flood_risk,
    compute_crop_vpd_stress,
    get_current_weather,
    get_weather_by_datetime_range,
    trigger_early_harvest_window,
)
from mcp_servers.base import stable_unit
from prompts.prompt_registry import PROMPT_REGISTRY, alert_rule
from schemas.mcp_models import (
    CalculateHaorFlashFloodRiskInput,
    ComputeCropVpdStressInput,
    CropStage,
    FloodAlertLevel,
    GetCurrentWeatherInput,
    GetWeatherByDatetimeRangeInput,
    Grade,
    TriggerEarlyHarvestWindowInput,
    UrgencyLevel,
)

AGENT = "climate_credit"
LOAN_CAP_TK = 50_000.0
ANNUAL_RATE_PCT = 6.0
LENDER_MODEL = "Parametric micro-credit modelled on 6% collateral-free agri-loans (UCB-style) with iFarmer-style underwriting"


def _ltv_for(score: int) -> float:
    if score >= 750:
        return 0.60
    if score >= 700:
        return 0.50
    if score >= 650:
        return 0.40
    return 0.0


def _band(score: int) -> str:
    if score >= 750:
        return "Excellent"
    if score >= 680:
        return "Good"
    if score >= 600:
        return "Fair"
    return "Thin-file / high risk"


async def run(state: KrishiAgentState, trace: TraceRecorder) -> dict[str, Any]:
    prompt = PROMPT_REGISTRY.active(AGENT)
    upazila = bd_geo.resolve_upazila(state.upazila)
    today = now_bdt().date()
    await trace.emit(AGENT, StepType.THOUGHT, f"Clearing the next 72 h for {upazila.name} ({upazila.district}); "
                                               f"alert thresholds from {prompt.version} ({prompt.variant_id}).")

    weather = await trace.mcp(AGENT, "get_current_weather", get_current_weather,
                              GetCurrentWeatherInput(latitude=upazila.lat, longitude=upazila.lon),
                              lambda r: f"{r.temperature_c} C, RH {r.relative_humidity_pct}%, {r.weather_description} "
                                        f"({r.data_source.value}).")
    forecast = await trace.mcp(AGENT, "get_weather_by_datetime_range", get_weather_by_datetime_range,
                               GetWeatherByDatetimeRangeInput(latitude=upazila.lat, longitude=upazila.lon,
                                                              start_date=today, end_date=today + timedelta(days=2)),
                               lambda r: f"72 h: {r.total_precipitation_mm} mm rain, {len(r.storm_warnings)} storm warning(s) "
                                         f"({r.data_source.value}).")

    haor = upazila.name in HAOR_UPAZILAS
    alert: FloodAlertLevel | None = None
    probability = None
    benchmark = None
    sar = None
    sar_source = None
    dispatch_id = None
    if haor:
        if state.sar_backscatter_override_db is not None:
            sar, sar_source = state.sar_backscatter_override_db, "farmer/operator supplied Sentinel-1 scene"
        else:
            sar = round(-11.5 + 3.0 * (stable_unit("s1-pass", upazila.name, now_bdt().strftime("%Y%m%d%H")) - 0.5), 2)
            sar_source = "simulated Sentinel-1 IW GRD pass (no live Copernicus feed)"
        flood = await trace.mcp(AGENT, "calculate_haor_flash_flood_risk", calculate_haor_flash_flood_risk,
                                CalculateHaorFlashFloodRiskInput(upazila=upazila.name, sar_water_backscatter_db=sar),
                                lambda r: f"Breach probability {r.embankment_breach_probability_pct}% ({r.alert_level.value}); "
                                          f"2017 benchmark loss {r.historical_boro_loss_benchmark_pct:g}%.")
        probability = flood.embankment_breach_probability_pct
        benchmark = flood.historical_boro_loss_benchmark_pct
        alert = FloodAlertLevel(alert_rule(prompt.params, {"probability": probability / 100}))
        if alert in (FloodAlertLevel.ORANGE, FloodAlertLevel.RED):
            plan = await trace.mcp(AGENT, "trigger_early_harvest_window", trigger_early_harvest_window,
                                   TriggerEarlyHarvestWindowInput(cluster_id=state.farmer_id[:40], upazila=upazila.name,
                                                                  urgency_level=UrgencyLevel.CRITICAL if alert is FloodAlertLevel.RED else UrgencyLevel.HIGH),
                                   lambda r: f"Early-harvest {r.dispatch_id}: {r.trucks_required} trucks, "
                                             f"{r.combine_harvesters_required} combines, done by {r.harvest_complete_by:%d %b %H:%M}.")
            dispatch_id = plan.dispatch_id
    else:
        await trace.emit(AGENT, StepType.THOUGHT, f"{upazila.name} is outside the haor basin: flash-flood model not applicable; "
                                                   "using the 72 h storm and rain forecast.")

    storing = bool(state.cold_storage_arbitrage_plan and state.cold_storage_arbitrage_plan.decision.startswith("STORE"))
    stage = CropStage.POST_HARVEST_STORAGE if storing else CropStage.MATURITY
    vpd = await trace.mcp(AGENT, "compute_crop_vpd_stress", compute_crop_vpd_stress,
                          ComputeCropVpdStressInput(crop=state.crop, crop_stage=stage, temp_c=weather.temperature_c,
                                                    rh_pct=weather.relative_humidity_pct),
                          lambda r: f"VPD {r.vpd_kpa} kPa ({r.vpd_status.value}); {r.pathogen} risk {r.fungal_risk_pct:.0f}%.")

    clearance = not forecast.storm_warnings and (alert is None or alert in (FloodAlertLevel.GREEN, FloodAlertLevel.YELLOW))

    # --- Alternative agri-credit score -------------------------------------------------
    cert = state.optical_grade_cert
    pool_plan = state.syndicate_bypass_plan
    cold = state.cold_storage_arbitrage_plan
    components: list[ScoreComponent] = []
    grade_pts = {Grade.A: 120.0, Grade.B: 85.0, Grade.C: 45.0}[cert.market_grade] if cert else 30.0
    components.append(ScoreComponent(name="Verified quality grade", points=grade_pts, max_points=120,
                                     evidence=f"{cert.certificate_id} ({cert.grade.value})" if cert else "no certificate"))
    contract_value = pool_plan.lot_value_b2b_tk if pool_plan else 0.0
    linkage = 40.0 + 70.0 * min(1.0, contract_value / 50_000) if pool_plan else 10.0
    components.append(ScoreComponent(name="Market linkage", points=round(linkage, 1), max_points=110,
                                     evidence=f"pooled B2B contract Tk {contract_value:,.0f} via {pool_plan.best_hub_name}"
                                     if pool_plan else "no buyer linkage"))
    receipt = cold.reservation if cold and cold.reservation and cold.reservation.receipt_id else None
    if receipt:
        collateral_pts, collateral = 100.0, f"warehouse receipt {receipt.receipt_id}"
        collateral_value = state.quantity_kg * (1 - (cold.lambda_rot or 0.012)) * (cold.expected_future_price_tk_per_kg or 0.0)
    elif pool_plan and pool_plan.pool:
        collateral_pts, collateral = 70.0, f"escrow-backed receivable from pool {pool_plan.pool.pool_id}"
        collateral_value = contract_value
    else:
        collateral_pts, collateral, collateral_value = 20.0, "unsecured", contract_value
    components.append(ScoreComponent(name="Collateral evidence", points=collateral_pts, max_points=100, evidence=collateral))
    climate_risk = probability / 100 if probability is not None else (0.15 if forecast.storm_warnings else 0.03)
    components.append(ScoreComponent(name="Climate risk (72 h)", points=round((1 - climate_risk) * 120, 1), max_points=120,
                                     evidence=f"flood breach {probability}%" if probability is not None
                                     else f"{forecast.total_precipitation_mm} mm, {len(forecast.storm_warnings)} storm warnings"))
    components.append(ScoreComponent(name="Agronomic risk", points=round((1 - vpd.fungal_risk_pct / 100) * 60, 1), max_points=60,
                                     evidence=f"{vpd.pathogen} {vpd.fungal_risk_pct:.0f}%"))
    kyc = 40.0 if state.pii_vault_map.get("vault_id") else 20.0
    components.append(ScoreComponent(name="Verified identity", points=kyc, max_points=40,
                                     evidence="phone/NID held in local PII vault" if kyc == 40 else "self-declared"))
    score = int(max(300, min(850, round(300 + sum(c.points for c in components)))))

    ltv = _ltv_for(score)
    loan = min(LOAN_CAP_TK, ltv * collateral_value) // 500 * 500 if ltv else 0.0
    report = ClimateCreditReport(
        temperature_c=weather.temperature_c, relative_humidity_pct=weather.relative_humidity_pct,
        weather_source=weather.data_source.value, rain_next_72h_mm=forecast.total_precipitation_mm,
        storm_warnings=forecast.storm_warnings, flood_applicable=haor, flood_alert_level=alert,
        flood_breach_probability_pct=probability, boro_loss_benchmark_pct=benchmark, sar_backscatter_db=sar,
        sar_source=sar_source, seventy_two_hour_clearance=clearance, fungal_risk_pct=vpd.fungal_risk_pct,
        fungal_risk_level=vpd.fungal_risk_level, pathogen=vpd.pathogen, early_harvest_dispatch_id=dispatch_id,
        credit_score=score, score_band=_band(score), score_components=components, loan_eligible=loan > 0,
        loan_amount_tk=float(loan), annual_rate_pct=ANNUAL_RATE_PCT, tenor_months=6 if receipt else 4,
        collateral=collateral, lender_model=LENDER_MODEL, prompt_version=prompt.version,
    )
    await trace.emit(AGENT, StepType.DECISION,
                     f"72 h clearance {'OK' if clearance else 'NOT CLEAR'}; credit score {score}/850 ({report.score_band}); "
                     + (f"pre-approved Tk {loan:,.0f} at {ANNUAL_RATE_PCT:g}%." if loan else "not eligible for instant credit."),
                     data={"score": score, "loan_tk": loan})
    return {
        "climate_credit_report": report,
        "prompt_versions": {**state.prompt_versions, AGENT: prompt.version},
        "trace_events": trace.drain(),
    }
