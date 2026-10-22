"""MCP Server 3 — ``coldchain-iot-mcp`` (Streamable HTTP + stdio).

Bangladesh Cold Storage Association (BCSA) facility registry for the four main
potato storage districts, modelling the quota capture that locks smallholders
out (traders 45%, plant owners 32.32%, farmers 22.68%), the Tk 8.00-9.50/kg
seasonal tariff, simulated MQTT chamber telemetry (with grid load-shedding,
diesel backup and judge-injected power cuts), Q10 dynamic shelf life and
HMAC-signed digital warehouse receipts for pooled smallholder reservations.

Run standalone over stdio:  ``python -m mcp_servers.coldchain_iot_mcp``
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import math
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta

from config import now_bdt, settings
from mcp_servers import bd_geo
from mcp_servers.anomaly_state import ANOMALIES, ActiveAnomaly
from mcp_servers.base import McpServer, ToolExecutionError, run_stdio, stable_unit, standalone_dispatcher
from mcp_servers.dam_market_mcp import pooled_truck_leg
from schemas.mcp_models import (
    AllocationLeg,
    CalculateDynamicShelfLifeInput,
    CalculateDynamicShelfLifeOutput,
    ColdStorageFacilityQuota,
    Crop,
    DistrictStorageGap,
    GetChamberTelemetryInput,
    GetChamberTelemetryOutput,
    Grade,
    PowerSource,
    QueryColdStorageQuotaInput,
    QueryColdStorageQuotaOutput,
    QuotaCaptureBreakdown,
    ReservationStatus,
    ReserveCollectiveStorageSlotInput,
    ReserveCollectiveStorageSlotOutput,
)

server = McpServer(
    name="coldchain-iot-mcp",
    title="BCSA Cold-Chain Quota & IoT Telemetry MCP",
    version="1.0.0",
    description=(
        "BCSA cold-storage smallholder quota search, MQTT chamber telemetry (temperature, RH, CO2, power, "
        "rot risk), Q10 dynamic shelf-life with the lambda_rot spoilage coefficient, and pooled smallholder "
        "storage reservations backed by HMAC-signed digital warehouse receipts."
    ),
    transports=("streamable-http", "stdio"),
    module="mcp_servers.coldchain_iot_mcp",
)

# ---------------------------------------------------------------------------
# Seed data: BCSA facilities and district storage gap
# ---------------------------------------------------------------------------

TRADER_QUOTA_PCT = 45.00
OWNER_QUOTA_PCT = 32.32
FARMER_QUOTA_PCT = 22.68
CHAMBER_CAPACITY_MT = 1_800.0

# district -> (registered BCSA facilities, storage capacity MT, potato output MT)
DISTRICT_STORAGE_STATS: dict[str, tuple[int, float, float]] = {
    "Munshiganj": (68, 540_760.0, 1_000_738.0),
    "Rangpur": (39, 412_300.0, 1_086_500.0),
    "Bogura": (43, 368_900.0, 1_245_200.0),
    "Thakurgaon": (21, 214_700.0, 612_400.0),
}


@dataclass(frozen=True, slots=True)
class Facility:
    facility_id: str
    name: str
    district: str
    upazila: str
    lat: float
    lon: float
    capacity_mt: float
    chambers: int
    tariff_tk_per_kg: float
    handling_fee_tk_per_kg: float
    seed_farmer_booked_fraction: float

    @property
    def farmer_quota_mt(self) -> float:
        return self.capacity_mt * FARMER_QUOTA_PCT / 100.0


_FACILITY_SEED: tuple[tuple[str, str, str, str, float, float, float], ...] = (
    ("BCSA-MUN-01", "Mirkadim Riverside Himagar Ltd.", "Munshiganj", "Munshiganj Sadar", 23.5545, 90.5150, 12_000),
    ("BCSA-MUN-02", "Tongibari Krishi Himagar", "Munshiganj", "Tongibari", 23.5010, 90.4690, 9_500),
    ("BCSA-MUN-03", "Sirajdikhan Cold Storage Ltd.", "Munshiganj", "Sirajdikhan", 23.5840, 90.3850, 11_000),
    ("BCSA-MUN-04", "Sreenagar Agro Cold Storage", "Munshiganj", "Sreenagar", 23.5320, 90.2860, 8_500),
    ("BCSA-MUN-05", "Lohajang Padma Himagar", "Munshiganj", "Lohajang", 23.4680, 90.3480, 7_800),
    ("BCSA-RAN-01", "Rangpur Uttara Himagar Ltd.", "Rangpur", "Rangpur Sadar", 25.7520, 89.2600, 10_500),
    ("BCSA-RAN-02", "Mithapukur Cold Storage", "Rangpur", "Mithapukur", 25.5690, 89.2850, 9_000),
    ("BCSA-RAN-03", "Badarganj Agro Himagar", "Rangpur", "Badarganj", 25.6760, 89.0560, 8_200),
    ("BCSA-RAN-04", "Kaunia Teesta Cold Storage", "Rangpur", "Kaunia", 25.7850, 89.4150, 7_500),
    ("BCSA-BOG-01", "Shibganj Mahasthan Himagar", "Bogura", "Shibganj", 25.0150, 89.3200, 11_500),
    ("BCSA-BOG-02", "Sherpur Krishi Cold Storage", "Bogura", "Sherpur", 24.6690, 89.4150, 9_800),
    ("BCSA-BOG-03", "Kahaloo Agro Himagar", "Bogura", "Kahaloo", 24.8350, 89.2690, 8_700),
    ("BCSA-BOG-04", "Gabtali Cold Storage Ltd.", "Bogura", "Gabtali", 24.8820, 89.4480, 7_900),
    ("BCSA-BOG-05", "Shajahanpur Himagar", "Bogura", "Shajahanpur", 24.7850, 89.3850, 10_200),
    ("BCSA-THA-01", "Thakurgaon Sadar Himagar", "Thakurgaon", "Thakurgaon Sadar", 26.0350, 88.4640, 9_600),
    ("BCSA-THA-02", "Ranisankail Cold Storage", "Thakurgaon", "Ranisankail", 25.9340, 88.2350, 7_400),
    ("BCSA-THA-03", "Baliadangi Agro Himagar", "Thakurgaon", "Baliadangi", 26.1010, 88.2850, 6_800),
    ("BCSA-THA-04", "Haripur Krishi Himagar", "Thakurgaon", "Haripur", 25.8680, 88.1520, 6_200),
)


def _build_facility(row: tuple[str, str, str, str, float, float, float]) -> Facility:
    facility_id, name, district, upazila, lat, lon, capacity = row
    booked_draw = stable_unit("booked", facility_id)
    return Facility(
        facility_id=facility_id,
        name=name,
        district=district,
        upazila=upazila,
        lat=lat,
        lon=lon,
        capacity_mt=capacity,
        chambers=max(4, round(capacity / CHAMBER_CAPACITY_MT)),
        tariff_tk_per_kg=8.00 + 0.25 * math.floor(stable_unit("tariff", facility_id) * 7),
        handling_fee_tk_per_kg=round(0.45 + 0.35 * stable_unit("handling", facility_id), 2),
        seed_farmer_booked_fraction=1.0 if booked_draw > 0.85 else round(0.55 + 0.45 * booked_draw, 3),
    )


FACILITIES: dict[str, Facility] = {row[0]: _build_facility(row) for row in _FACILITY_SEED}

_LEDGER_LOCK = threading.Lock()
_FARMER_BOOKED_MT: dict[str, float] = {
    f.facility_id: round(f.farmer_quota_mt * f.seed_farmer_booked_fraction, 3) for f in FACILITIES.values()
}
_RECEIPT_SEQUENCE: dict[str, int] = {}


def get_facility(facility_id: str) -> Facility:
    facility = FACILITIES.get(facility_id.strip().upper())
    if facility is None:
        raise ToolExecutionError(f"Unknown BCSA facility '{facility_id}'. Known: {', '.join(FACILITIES)}.")
    return facility


def validate_chamber(facility: Facility, chamber_id: str) -> str:
    chamber = chamber_id.strip().upper()
    if not chamber.startswith("CH-") or not chamber[3:].isdigit() or not 1 <= int(chamber[3:]) <= facility.chambers:
        raise ToolExecutionError(
            f"{facility.facility_id} has chambers CH-01..CH-{facility.chambers:02d}; '{chamber_id}' does not exist."
        )
    return chamber


def open_farmer_quota_mt(facility: Facility) -> float:
    return max(0.0, round(facility.farmer_quota_mt - _FARMER_BOOKED_MT[facility.facility_id], 3))


# ---------------------------------------------------------------------------
# Simulated MQTT chamber telemetry
# ---------------------------------------------------------------------------

SETPOINT_C = 9.5
OPTIMAL_TEMP_C = (8.9, 10.0)  # 48-50 deg F
OPTIMAL_RH_PCT = (92.0, 95.0)
AMBIENT_C_BY_MONTH = (19.0, 22.0, 27.0, 30.0, 31.0, 30.0, 29.5, 29.5, 29.0, 28.0, 24.5, 20.5)
THERMAL_TIME_CONSTANT_H = 36.0
CO2_BUILDUP_PPM_PER_H = 380.0
CO2_CEILING_PPM = 6_000.0
LOAD_SHEDDING_PROBABILITY = 0.10


@dataclass(frozen=True, slots=True)
class PowerState:
    source: PowerSource
    outage_minutes: int
    anomaly: ActiveAnomaly | None
    generator_failed: bool


def power_state(facility: Facility, chamber_id: str | None, at: datetime) -> PowerState:
    """Grid / diesel / outage for a chamber, or for the whole facility when ``chamber_id`` is None
    (a cut injected on a single chamber does not take the facility's other chambers down)."""
    cut = ANOMALIES.latest(
        "cold_chamber_power_cut",
        lambda a: a.params.get("facility_id") == facility.facility_id
        and a.params.get("chamber_id") in (None, chamber_id),
    )
    if cut is not None:
        elapsed = int(cut.params.get("elapsed_minutes", 0) + cut.minutes_since_activation(at))
        failed = bool(cut.params.get("generator_failed", True))
        return PowerState(PowerSource.OUTAGE if failed else PowerSource.DIESEL_GENERATOR, elapsed, cut, failed)
    if stable_unit("loadshed", facility.facility_id, at.strftime("%Y%m%d%H")) < LOAD_SHEDDING_PROBABILITY:
        return PowerState(PowerSource.DIESEL_GENERATOR, at.minute, None, False)
    return PowerState(PowerSource.GRID, 0, None, False)


def rot_risk_pct(temp_c: float, rh_pct: float, co2_ppm: float, outage_hours: float) -> float:
    risk = (
        0.6
        + 1.8 * max(0.0, temp_c - OPTIMAL_TEMP_C[1]) ** 1.3
        + 2.5 * max(0.0, rh_pct - 96.0)
        + 0.002 * max(0.0, co2_ppm - 3_000.0)
        + 0.4 * outage_hours
    )
    return round(min(95.0, risk), 2)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@server.tool(
    title="Query BCSA cold-storage smallholder quota",
    input_model=QueryColdStorageQuotaInput,
    output_model=QueryColdStorageQuotaOutput,
)
async def query_cold_storage_quota(params: QueryColdStorageQuotaInput) -> QueryColdStorageQuotaOutput:
    """Find BCSA cold storages within ``radius_km`` road distance that still have open smallholder
    (22.68% farmer) quota, with tariff (Tk 8.00-9.50/kg), handling fee, pooled 5-ton truck freight
    and all-in Tk/kg. Returns a cheapest-first allocation plan across facilities (skipping chambers
    under power outage) and the district's storage-capacity gap."""
    origin = bd_geo.resolve_district(params.district)
    now = now_bdt()
    rows: list[ColdStorageFacilityQuota] = []
    for facility in FACILITIES.values():
        leg = pooled_truck_leg(origin, bd_geo.district_by_name(facility.district), facility.lat, facility.lon)
        if leg.road_km > params.radius_km:
            continue
        open_mt = open_farmer_quota_mt(facility)
        power = power_state(facility, None, now).source
        rows.append(
            ColdStorageFacilityQuota(
                facility_id=facility.facility_id,
                name=facility.name,
                district=facility.district,
                upazila=facility.upazila,
                road_distance_km=leg.road_km,
                total_capacity_mt=facility.capacity_mt,
                trader_quota_mt=round(facility.capacity_mt * TRADER_QUOTA_PCT / 100.0, 1),
                owner_quota_mt=round(facility.capacity_mt * OWNER_QUOTA_PCT / 100.0, 1),
                farmer_quota_mt=round(facility.farmer_quota_mt, 1),
                farmer_quota_booked_mt=round(_FARMER_BOOKED_MT[facility.facility_id], 1),
                open_smallholder_quota_mt=round(open_mt, 1),
                chambers=facility.chambers,
                tariff_tk_per_kg=facility.tariff_tk_per_kg,
                handling_fee_tk_per_kg=facility.handling_fee_tk_per_kg,
                transport_cost_tk_per_kg=leg.cost_per_kg,
                all_in_cost_tk_per_kg=round(facility.tariff_tk_per_kg + facility.handling_fee_tk_per_kg + leg.cost_per_kg, 2),
                can_fulfil_request=open_mt >= params.tons_needed and power is not PowerSource.OUTAGE,
                power_status=power,
            )
        )
    rows.sort(key=lambda r: (not r.can_fulfil_request, r.power_status is PowerSource.OUTAGE, r.all_in_cost_tk_per_kg))

    allocation: list[AllocationLeg] = []
    remaining = params.tons_needed
    for row in sorted(rows, key=lambda r: r.all_in_cost_tk_per_kg):
        if remaining <= 0:
            break
        if row.power_status is PowerSource.OUTAGE or row.open_smallholder_quota_mt <= 0:
            continue
        tons = round(min(remaining, row.open_smallholder_quota_mt), 3)
        allocation.append(
            AllocationLeg(facility_id=row.facility_id, tons=tons, all_in_cost_tk=round(tons * 1000 * row.all_in_cost_tk_per_kg, 2))
        )
        remaining = round(remaining - tons, 3)

    stats = DISTRICT_STORAGE_STATS.get(origin.name)
    gap = (
        DistrictStorageGap(
            district=origin.name,
            registered_facilities=stats[0],
            storage_capacity_mt=stats[1],
            potato_output_mt=stats[2],
            storage_coverage_pct=round(stats[1] / stats[2] * 100.0, 2),
            uncovered_output_mt=round(stats[2] - stats[1], 1),
        )
        if stats
        else None
    )
    return QueryColdStorageQuotaOutput(
        district=origin.name,
        radius_km=params.radius_km,
        tons_needed=params.tons_needed,
        facilities_found=len(rows),
        total_open_smallholder_quota_mt=round(sum(r.open_smallholder_quota_mt for r in rows), 1),
        single_facility_fulfilment=any(r.can_fulfil_request for r in rows),
        recommended_allocation=allocation,
        unallocated_tons=max(0.0, remaining),
        quota_capture=QuotaCaptureBreakdown(
            traders_pct=TRADER_QUOTA_PCT,
            plant_owners_pct=OWNER_QUOTA_PCT,
            farmers_pct=FARMER_QUOTA_PCT,
            non_farmer_capture_pct=round(TRADER_QUOTA_PCT + OWNER_QUOTA_PCT, 2),
        ),
        district_gap=gap,
        facilities=rows,
    )


@server.tool(
    title="Cold-chamber MQTT telemetry",
    input_model=GetChamberTelemetryInput,
    output_model=GetChamberTelemetryOutput,
)
async def get_chamber_telemetry(params: GetChamberTelemetryInput) -> GetChamberTelemetryOutput:
    """Latest simulated MQTT reading (topic krishinexus/bcsa/<facility>/<chamber>/telemetry) for a
    cold chamber: temperature in deg C and deg F (optimal 48-50 deg F / 9-10 deg C), RH (optimal
    92-95%), CO2 ppm, power source (Grid, Diesel Generator or Outage), compressor state, generator
    fuel and internal rot risk (%). Reflects grid load-shedding and judge-injected power cuts."""
    facility = get_facility(params.facility_id)
    chamber = validate_chamber(facility, params.chamber_id)
    now = now_bdt()
    at = now.replace(minute=now.minute - now.minute % 5, second=0, microsecond=0)
    bucket = at.strftime("%Y%m%d%H%M")
    minute_of_day = at.hour * 60 + at.minute
    cycle = 2 * math.pi * minute_of_day / 1_440

    stored_crop = Crop.DIAMANT_POTATO if stable_unit("crop", facility.facility_id, chamber) < 0.3 else Crop.CARDINAL_POTATO
    stored_tons = facility.capacity_mt / facility.chambers * (0.78 + 0.2 * stable_unit("fill", facility.facility_id, chamber))
    temp = SETPOINT_C + 0.35 * math.sin(cycle) + 0.3 * (stable_unit("t", facility.facility_id, chamber, bucket) - 0.5)
    rh = 93.5 + 0.8 * math.cos(cycle) + 0.8 * (stable_unit("rh", facility.facility_id, chamber, bucket) - 0.5)
    co2 = 900.0 + 900.0 * ((minute_of_day % 360) / 360) + 100.0 * (stable_unit("co2", facility.facility_id, chamber, bucket) - 0.5)
    fuel = round(55.0 + 40.0 * stable_unit("fuel", facility.facility_id, at.date().isoformat()), 1)

    power = power_state(facility, chamber, now)
    outage_hours = power.outage_minutes / 60.0
    compressor = True
    if power.anomaly is not None and power.generator_failed:
        compressor = False
        ambient = AMBIENT_C_BY_MONTH[at.month - 1]
        temp += (ambient - SETPOINT_C) * (1 - math.exp(-outage_hours / THERMAL_TIME_CONSTANT_H))
        rh = min(98.5, rh + 1.2 * outage_hours**0.6)
        co2 = min(CO2_CEILING_PPM, co2 + CO2_BUILDUP_PPM_PER_H * outage_hours)
    elif power.source is PowerSource.DIESEL_GENERATOR:
        temp += 0.4 if power.anomaly is not None else 0.25
        if power.anomaly is not None:
            fuel = round(max(5.0, fuel - 6.0 * outage_hours), 1)

    temp_f = temp * 9 / 5 + 32
    risk = rot_risk_pct(temp, rh, co2, outage_hours if not compressor else 0.0)
    alerts: list[str] = []
    if not compressor:
        alerts.append(f"POWER OUTAGE {power.outage_minutes} min: compressor stopped and generator failed; dispatch technician.")
    elif power.source is PowerSource.DIESEL_GENERATOR:
        alerts.append(f"Grid down: running on diesel generator ({fuel:.0f}% fuel).")
    if temp > OPTIMAL_TEMP_C[1]:
        alerts.append(f"Temperature {temp:.1f} C ({temp_f:.1f} F) above the 50 F ceiling.")
    elif temp < OPTIMAL_TEMP_C[0]:
        alerts.append(f"Temperature {temp:.1f} C ({temp_f:.1f} F) below 48 F: cold-sweetening risk.")
    if rh > OPTIMAL_RH_PCT[1]:
        alerts.append(f"RH {rh:.1f}% above 95%: condensation and soft-rot risk.")
    elif rh < OPTIMAL_RH_PCT[0]:
        alerts.append(f"RH {rh:.1f}% below 92%: shrinkage and weight loss.")
    if co2 > 3_000:
        alerts.append(f"CO2 {co2:.0f} ppm above 3,000 ppm: ventilate (black-heart risk above 5,000 ppm).")
    if risk >= 10:
        alerts.append(f"Rot risk {risk:.1f}%: inspect stacks and plan early release.")

    return GetChamberTelemetryOutput(
        facility_id=facility.facility_id,
        facility_name=facility.name,
        chamber_id=chamber,
        mqtt_topic=f"krishinexus/bcsa/{facility.facility_id}/{chamber}/telemetry",
        recorded_at=at,
        stored_crop=stored_crop,
        stored_tons=round(stored_tons, 1),
        setpoint_c=SETPOINT_C,
        temperature_c=round(temp, 2),
        temperature_f=round(temp_f, 2),
        relative_humidity_pct=round(rh, 2),
        co2_ppm=round(co2, 0),
        power_source=power.source,
        compressor_running=compressor,
        generator_fuel_pct=fuel,
        outage_minutes=power.outage_minutes,
        temperature_in_optimal_band=OPTIMAL_TEMP_C[0] <= temp <= OPTIMAL_TEMP_C[1],
        humidity_in_optimal_band=OPTIMAL_RH_PCT[0] <= rh <= OPTIMAL_RH_PCT[1],
        rot_risk_pct=risk,
        alerts=alerts,
        simulated_anomaly_active=power.anomaly is not None,
    )


@dataclass(frozen=True, slots=True)
class ShelfLifeParams:
    reference_temp_c: float
    reference_rh_band: tuple[float, float]
    reference_hours: float
    q10: float
    chilling_threshold_c: float | None
    rh_low_penalty_per_pct: float
    rh_high_penalty_per_pct: float


SHELF_LIFE_PARAMS: dict[Crop, ShelfLifeParams] = {
    Crop.CARDINAL_POTATO: ShelfLifeParams(9.5, (90.0, 96.0), 5_760.0, 2.3, 4.0, 0.012, 0.06),
    Crop.DIAMANT_POTATO: ShelfLifeParams(9.5, (90.0, 96.0), 6_240.0, 2.3, 4.0, 0.012, 0.06),
    Crop.GREEN_CHILI: ShelfLifeParams(8.0, (90.0, 95.0), 504.0, 3.0, 7.0, 0.025, 0.04),
    Crop.BRINJAL: ShelfLifeParams(10.0, (90.0, 95.0), 336.0, 2.6, 8.0, 0.025, 0.04),
    Crop.BORO_RICE: ShelfLifeParams(25.0, (55.0, 70.0), 8_760.0, 2.0, None, 0.005, 0.035),
}
GRADE_SHELF_FACTOR: dict[Grade, float] = {Grade.A: 1.00, Grade.B: 0.82, Grade.C: 0.60}
LAMBDA_ROT_MIN, LAMBDA_ROT_MAX = 0.012, 0.09


@server.tool(
    title="Dynamic shelf life and lambda_rot",
    input_model=CalculateDynamicShelfLifeInput,
    output_model=CalculateDynamicShelfLifeOutput,
)
async def calculate_dynamic_shelf_life(params: CalculateDynamicShelfLifeInput) -> CalculateDynamicShelfLifeOutput:
    """Remaining shelf life (hours) from a Q10 temperature model around each crop's reference
    storage condition, humidity-band penalties, chilling-injury limits and optical grade, plus the
    spoilage coefficient lambda_rot in [0.012, 0.09] used by the cold-storage arbitrage equation
    Q x (1 - lambda_rot) x E[P_future]."""
    p = SHELF_LIFE_PARAMS[params.crop]
    t, rh = params.transit_temp_c, params.rh_pct
    chilling = p.chilling_threshold_c is not None and t < p.chilling_threshold_c
    effective_t = max(t, p.chilling_threshold_c) if p.chilling_threshold_c is not None else t
    temperature_factor = p.q10 ** ((p.reference_temp_c - effective_t) / 10.0)
    chill_factor = max(0.35, 1 - 0.12 * (p.chilling_threshold_c - t)) if chilling and p.chilling_threshold_c else 1.0

    low, high = p.reference_rh_band
    if rh < low:
        humidity_factor = 1 - p.rh_low_penalty_per_pct * (low - rh)
    elif rh > high:
        humidity_factor = 1 - p.rh_high_penalty_per_pct * (rh - high)
    else:
        humidity_factor = 1.0
    humidity_factor = max(0.15, humidity_factor)
    grade_factor = GRADE_SHELF_FACTOR[params.grade]

    remaining = p.reference_hours * temperature_factor * humidity_factor * grade_factor * chill_factor
    stress = min(1.0, max(0.0, 1 - remaining / p.reference_hours))
    lambda_rot = round(min(LAMBDA_ROT_MAX, max(LAMBDA_ROT_MIN, LAMBDA_ROT_MIN + (LAMBDA_ROT_MAX - LAMBDA_ROT_MIN) * stress**0.85)), 4)
    max_safe_transit = remaining * 0.2

    advice: list[str] = []
    if temperature_factor < 0.5:
        advice.append(
            f"Cool to {p.reference_temp_c:.1f} C quickly: every 10 C above reference divides shelf life by {p.q10:.1f}."
        )
    if chilling:
        advice.append(
            f"Below {p.chilling_threshold_c:.0f} C: "
            + ("low-temperature sweetening of potato tubers." if params.crop in (Crop.CARDINAL_POTATO, Crop.DIAMANT_POTATO) else "chilling injury (pitting, browning).")
        )
    if rh < low:
        advice.append("Humidity below band: cover with wet hessian or perforated liners to limit moisture loss.")
    elif rh > high:
        advice.append("Humidity above band: ventilate and avoid sealed plastic to prevent condensation rot.")
    if params.grade is Grade.C:
        advice.append("Grade C lot: sell or process first; unsuitable for long-term storage.")
    if lambda_rot > 0.05:
        advice.append(f"lambda_rot {lambda_rot:.3f} > 0.05: sell spot or reach cold storage within {max_safe_transit:.0f} h.")
    if not advice:
        advice.append("Within safe holding parameters for this crop and grade.")

    return CalculateDynamicShelfLifeOutput(
        crop=params.crop,
        grade=params.grade,
        transit_temp_c=t,
        rh_pct=rh,
        reference_temp_c=p.reference_temp_c,
        reference_rh_band_pct=p.reference_rh_band,
        reference_shelf_life_hours=p.reference_hours,
        q10=p.q10,
        temperature_factor=round(temperature_factor, 4),
        humidity_factor=round(humidity_factor, 4),
        grade_factor=grade_factor,
        chilling_injury_risk=chilling,
        remaining_shelf_life_hours=round(remaining, 1),
        remaining_shelf_life_days=round(remaining / 24.0, 2),
        lambda_rot=lambda_rot,
        max_safe_transit_hours=round(max_safe_transit, 1),
        storage_advice=advice,
    )


STORAGE_TERM_DAYS = 210
BAG_KG = 50


@server.tool(
    title="Reserve pooled smallholder storage slot",
    input_model=ReserveCollectiveStorageSlotInput,
    output_model=ReserveCollectiveStorageSlotOutput,
    read_only=False,
    idempotent=False,
)
async def reserve_collective_storage_slot(
    params: ReserveCollectiveStorageSlotInput,
) -> ReserveCollectiveStorageSlotOutput:
    """Lock a pooled reservation against a facility's open smallholder quota (CONFIRMED, PARTIAL
    when quota runs short, REJECTED when none is left) and issue a digital warehouse receipt ID
    signed with HMAC-SHA256, usable as collateral for working-capital micro-credit."""
    facility = get_facility(params.facility_id)
    now = now_bdt()
    with _LEDGER_LOCK:
        open_mt = open_farmer_quota_mt(facility)
        reserved = round(min(params.tons, open_mt), 3)
        if reserved > 0:
            _FARMER_BOOKED_MT[facility.facility_id] = round(_FARMER_BOOKED_MT[facility.facility_id] + reserved, 3)
            sequence = _RECEIPT_SEQUENCE.get(facility.facility_id, 0) + 1
            _RECEIPT_SEQUENCE[facility.facility_id] = sequence
        remaining_open = open_farmer_quota_mt(facility)

    avg_tons = round(params.tons / params.farmer_count, 3)
    outage = power_state(facility, None, now).source is PowerSource.OUTAGE
    outage_note = " Facility is currently on power OUTAGE; loading will start after power is restored." if outage else ""
    if reserved <= 0:
        return ReserveCollectiveStorageSlotOutput(
            status=ReservationStatus.REJECTED,
            receipt_id=None,
            cluster_id=params.cluster_id,
            facility_id=facility.facility_id,
            facility_name=facility.name,
            requested_tons=params.tons,
            reserved_tons=0.0,
            waitlisted_tons=params.tons,
            farmer_count=params.farmer_count,
            avg_tons_per_farmer=avg_tons,
            bags_50kg=0,
            tariff_tk_per_kg=facility.tariff_tk_per_kg,
            handling_fee_tk_per_kg=facility.handling_fee_tk_per_kg,
            storage_charge_total_tk=0.0,
            handling_charge_total_tk=0.0,
            total_charge_tk=0.0,
            per_farmer_charge_tk=0.0,
            valid_from=None,
            valid_until=None,
            remaining_open_quota_mt=remaining_open,
            signature_algorithm="HMAC-SHA256",
            receipt_signature=None,
            reason=(
                f"No open smallholder quota at {facility.name}: the 22.68% farmer quota is fully booked. "
                "Call query_cold_storage_quota to find alternatives." + outage_note
            ),
        )

    status = ReservationStatus.CONFIRMED if reserved >= params.tons else ReservationStatus.PARTIAL
    receipt_id = f"KNX-WR-{facility.facility_id}-{now:%Y%m%d}-{sequence:04d}"
    valid_from = now.date()
    valid_until = valid_from + timedelta(days=STORAGE_TERM_DAYS)
    storage_charge = round(reserved * 1000 * facility.tariff_tk_per_kg, 2)
    handling_charge = round(reserved * 1000 * facility.handling_fee_tk_per_kg, 2)
    total_charge = round(storage_charge + handling_charge, 2)
    canonical = json.dumps(
        {
            "receipt_id": receipt_id,
            "cluster_id": params.cluster_id,
            "facility_id": facility.facility_id,
            "reserved_tons": reserved,
            "farmer_count": params.farmer_count,
            "tariff_tk_per_kg": facility.tariff_tk_per_kg,
            "valid_from": valid_from.isoformat(),
            "valid_until": valid_until.isoformat(),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    signature = hmac.new(settings.receipt_signing_key.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    reason = (
        f"Reserved {reserved:.3f} t for {params.farmer_count} smallholders at {facility.name}."
        if status is ReservationStatus.CONFIRMED
        else f"Only {reserved:.3f} t of {params.tons:.3f} t available; {params.tons - reserved:.3f} t waitlisted."
    ) + " The signed receipt can collateralise working-capital micro-credit." + outage_note

    return ReserveCollectiveStorageSlotOutput(
        status=status,
        receipt_id=receipt_id,
        cluster_id=params.cluster_id,
        facility_id=facility.facility_id,
        facility_name=facility.name,
        requested_tons=params.tons,
        reserved_tons=reserved,
        waitlisted_tons=round(params.tons - reserved, 3),
        farmer_count=params.farmer_count,
        avg_tons_per_farmer=avg_tons,
        bags_50kg=math.ceil(reserved * 1000 / BAG_KG),
        tariff_tk_per_kg=facility.tariff_tk_per_kg,
        handling_fee_tk_per_kg=facility.handling_fee_tk_per_kg,
        storage_charge_total_tk=storage_charge,
        handling_charge_total_tk=handling_charge,
        total_charge_tk=total_charge,
        per_farmer_charge_tk=round(total_charge / params.farmer_count, 2),
        valid_from=valid_from,
        valid_until=valid_until,
        remaining_open_quota_mt=remaining_open,
        signature_algorithm="HMAC-SHA256",
        receipt_signature=signature,
        reason=reason,
    )


if __name__ == "__main__":
    asyncio.run(run_stdio(standalone_dispatcher(server)))
