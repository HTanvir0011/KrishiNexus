"""MCP Server 1 — ``dam-market-mcp`` (Streamable HTTP + stdio).

Department of Agricultural Marketing (market.dam.gov.bd) modelled price engine for
Bangladesh's 5-tier produce chain (Faria -> Bepari -> Aratdar -> Paiker -> Retailer).

Daily grower / wholesale / retail prices are derived from 2021-2025 monthly
benchmark curves, interpolated between mid-month anchors, scaled by district
market factors (surplus belts sell cheaper at the farm gate, Dhaka and Sylhet
retail dearer) and perturbed by a deterministic +/-2.5% daily jitter, so every
call is reproducible for a given date.

Run standalone over stdio:  ``python -m mcp_servers.dam_market_mcp``
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from config import now_bdt
from mcp_servers import bd_geo
from mcp_servers.base import McpServer, run_stdio, stable_unit, standalone_dispatcher
from schemas.mcp_models import (
    AnomalySeverity,
    Crop,
    DailyPricePoint,
    DetectSyndicateMarkupAnomalyInput,
    DetectSyndicateMarkupAnomalyOutput,
    FindOptimalSellingHubInput,
    FindOptimalSellingHubOutput,
    GetDailyCommoditySpreadInput,
    GetDailyCommoditySpreadOutput,
    GetHistoricalSeasonalCurveInput,
    GetHistoricalSeasonalCurveOutput,
    Grade,
    HubType,
    IntermediaryTier,
    MarketingCostLine,
    SeasonalMonthPoint,
    SeasonPhase,
    SellingHubOption,
    TierValueCapture,
)

server = McpServer(
    name="dam-market-mcp",
    title="DAM Market & Syndicate Anomaly MCP",
    version="1.0.0",
    description=(
        "Bangladesh produce market intelligence: DAM-modelled daily grower/wholesale/retail spreads, "
        "5-tier intermediary syndicate markup detection, pooled 5-ton truck hub ranking and seasonal "
        "price appreciation curves for Cardinal/Diamant potato, green chili, brinjal and Boro rice."
    ),
    transports=("streamable-http", "stdio"),
    module="mcp_servers.dam_market_mcp",
)

MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

# ---------------------------------------------------------------------------
# Seed data: monthly benchmark curves (Tk/kg)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SeasonalCurve:
    grower: tuple[float, ...]
    wholesale: tuple[float, ...]
    retail: tuple[float, ...]
    unit: str
    production_cost_floor: float
    fair_markup_pct: float
    transit_loss_pct_per_hour: float


_FRESH_UNIT = "Tk/kg (fresh produce)"

SEASONAL_CURVES: dict[Crop, SeasonalCurve] = {
    Crop.CARDINAL_POTATO: SeasonalCurve(
        grower=(16, 12, 11, 14, 18, 24, 32, 38, 41, 39, 34, 24),
        wholesale=(20, 16, 15, 19, 24, 31, 42, 66, 70, 64, 52, 34),
        retail=(28, 24, 22, 27, 32, 40, 52, 82, 88, 80, 68, 46),
        unit=_FRESH_UNIT,
        production_cost_floor=15.0,
        fair_markup_pct=35.0,
        transit_loss_pct_per_hour=0.025,
    ),
    Crop.DIAMANT_POTATO: SeasonalCurve(
        grower=(17, 13, 12, 15, 19, 26, 34, 40, 43, 41, 36, 26),
        wholesale=(22, 17, 16, 20, 26, 33, 45, 70, 74, 68, 55, 36),
        retail=(30, 26, 24, 29, 34, 43, 56, 88, 92, 85, 72, 49),
        unit=_FRESH_UNIT,
        production_cost_floor=15.0,
        fair_markup_pct=35.0,
        transit_loss_pct_per_hour=0.022,
    ),
    Crop.GREEN_CHILI: SeasonalCurve(
        grower=(40, 35, 38, 45, 55, 75, 95, 88, 70, 62, 52, 42),
        wholesale=(60, 52, 56, 66, 80, 110, 140, 128, 104, 92, 76, 62),
        retail=(85, 76, 82, 96, 118, 162, 205, 190, 152, 128, 106, 90),
        unit=_FRESH_UNIT,
        production_cost_floor=30.0,
        fair_markup_pct=45.0,
        transit_loss_pct_per_hour=0.32,
    ),
    Crop.BRINJAL: SeasonalCurve(
        grower=(22, 20, 24, 28, 32, 38, 45, 48, 44, 40, 32, 25),
        wholesale=(32, 30, 34, 40, 46, 54, 64, 68, 62, 56, 45, 36),
        retail=(48, 45, 50, 58, 66, 78, 92, 96, 88, 80, 66, 52),
        unit=_FRESH_UNIT,
        production_cost_floor=14.0,
        fair_markup_pct=42.0,
        transit_loss_pct_per_hour=0.26,
    ),
    Crop.BORO_RICE: SeasonalCurve(
        grower=(44, 45, 45, 40, 38, 41, 43, 45, 46, 46, 45, 44),
        wholesale=(50, 51, 51, 47, 45, 48, 50, 52, 53, 53, 52, 50),
        retail=(58, 59, 60, 56, 54, 56, 58, 60, 61, 62, 60, 58),
        unit="Tk/kg (milled coarse-rice equivalent; paddy price / 0.67 outturn)",
        production_cost_floor=41.0,
        fair_markup_pct=22.0,
        transit_loss_pct_per_hour=0.004,
    ),
}

# (grower, wholesale, retail) multipliers relative to the national curves above.
DISTRICT_MARKET_FACTORS: dict[str, tuple[float, float, float]] = {
    "Dhaka Karwan Bazar": (1.04, 1.00, 1.00),
    "Dhaka Mirpur": (1.04, 1.03, 1.06),
    "Munshiganj": (1.00, 0.93, 0.90),
    "Kishoreganj": (1.02, 0.94, 0.92),
    "Netrokona": (1.02, 0.94, 0.92),
    "Sunamganj": (1.03, 0.96, 0.94),
    "Sylhet": (1.06, 1.04, 1.05),
    "Bogura": (0.99, 0.90, 0.86),
    "Rangpur": (0.98, 0.89, 0.85),
    "Thakurgaon": (0.97, 0.88, 0.84),
    "Kurigram": (0.96, 0.88, 0.85),
    "Jessore": (0.99, 0.91, 0.87),
    "Cox's Bazar": (1.06, 1.05, 1.07),
}

CROP_SURPLUS_DISTRICTS: dict[Crop, frozenset[str]] = {
    Crop.CARDINAL_POTATO: frozenset({"Munshiganj", "Bogura", "Rangpur", "Thakurgaon"}),
    Crop.DIAMANT_POTATO: frozenset({"Munshiganj", "Bogura", "Rangpur", "Thakurgaon"}),
    Crop.GREEN_CHILI: frozenset({"Bogura", "Kurigram", "Jessore"}),
    Crop.BRINJAL: frozenset({"Jessore", "Bogura", "Rangpur"}),
    Crop.BORO_RICE: frozenset({"Sunamganj", "Kishoreganj", "Netrokona", "Rangpur"}),
}

GRADE_PRICE_MULTIPLIER: dict[Grade, float] = {Grade.A: 1.00, Grade.B: 0.88, Grade.C: 0.72}

# 5-tier value-chain structure. Farm gate -> wholesale: the Faria keeps 20% of the margin and the
# Bepari grosses the rest, spending 70% of it on marketing. CPD (July 2026) finds the Aratdar extracts
# 62.35% of that Bepari marketing cost as commission, khajna and arat charges while spending Tk 0 on
# grading, so the Aratdar's slice of the ladder is derived from the Bepari's cost rather than set
# directly. Wholesale -> retail is split Paiker/Retailer.
FARIA_SHARE_OF_PRIMARY_MARGIN = 0.20
BEPARI_MARKETING_COST_RATIO = 0.70
ARATDAR_SHARE_OF_BEPARI_MARKETING_COST = 0.6235
ARATDAR_GRADING_SPEND_TK_PER_KG = 0.0
# The Bepari's own cost lines as shares of its total marketing cost; they add up to the 37.65%
# left after the Aratdar's take.
BEPARI_OWN_COST_LINES: tuple[tuple[str, str, float], ...] = (
    ("Truck freight to the terminal market", "Transporter", 0.1800),
    ("Loading, unloading and porter labour", "Labour", 0.0650),
    ("Transit shrinkage and wastage", "Lost produce", 0.0525),
    ("Jute bags and packing", "Packaging supplier", 0.0440),
    ("Road tolls and informal chanda", "Toll plazas and local collectors", 0.0350),
)
_BEPARI_COST_SHARE = (1 - FARIA_SHARE_OF_PRIMARY_MARGIN) * BEPARI_MARKETING_COST_RATIO
_ARATDAR_PRIMARY_SHARE = _BEPARI_COST_SHARE * ARATDAR_SHARE_OF_BEPARI_MARKETING_COST
PRIMARY_MARGIN_SPLIT = (
    (IntermediaryTier.FARIA, FARIA_SHARE_OF_PRIMARY_MARGIN),
    (IntermediaryTier.BEPARI, 1 - FARIA_SHARE_OF_PRIMARY_MARGIN - _ARATDAR_PRIMARY_SHARE),
    (IntermediaryTier.ARATDAR, _ARATDAR_PRIMARY_SHARE),
)
SECONDARY_MARGIN_SPLIT = ((IntermediaryTier.PAIKER, 0.35), (IntermediaryTier.RETAILER, 0.65))
TIER_COST_RATIO: dict[IntermediaryTier, float] = {
    IntermediaryTier.FARIA: 0.55,
    # The Bepari's ladder margin is already net of the Aratdar's take, so only its own cost lines remain.
    IntermediaryTier.BEPARI: _BEPARI_COST_SHARE * (1 - ARATDAR_SHARE_OF_BEPARI_MARKETING_COST) / PRIMARY_MARGIN_SPLIT[1][1],
    # Arat rent, weighing and staff; nothing is spent on grading.
    IntermediaryTier.ARATDAR: 0.12,
    IntermediaryTier.PAIKER: 0.45,
    IntermediaryTier.RETAILER: 0.55,
}
TIER_ROLES: dict[IntermediaryTier, str] = {
    IntermediaryTier.FARIA: "Village petty trader buying at the farm gate or local haat",
    IntermediaryTier.BEPARI: "Itinerant assembler who aggregates Faria lots and hires trucks to terminal markets",
    IntermediaryTier.ARATDAR: "Commission agent at the terminal arat who sets the auction price and levies commission + khajna",
    IntermediaryTier.PAIKER: "Bulk wholesaler buying arat lots for city retail markets",
    IntermediaryTier.RETAILER: "Kacha-bazar retailer selling to consumers",
}
ANOMALY_THRESHOLD_PCT = 40.0

# 5-ton pooled truck economics (2025 Bangladesh road-freight rates).
TRUCK_CAPACITY_KG = 5_000
TRUCK_RATE_TK_PER_KM = 68.0
TRUCK_FIXED_TK_PER_TRIP = 1_500.0
POOLING_FEE_TK_PER_KG = 0.10
AVG_TRUCK_SPEED_KMH = 35.0
LOADING_HOURS = 1.5
MIN_LOCAL_HAUL_KM = 8.0

# ---------------------------------------------------------------------------
# Selling hubs: wholesale arats, urban retail chain DCs and 66 WFP aggregation centres
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SellingHub:
    hub_id: str
    name: str
    hub_type: HubType
    district: str
    lat: float
    lon: float
    intake_cap_kg: float | None


_FIXED_HUBS: tuple[SellingHub, ...] = (
    SellingHub("ARAT-KWB", "Karwan Bazar Wholesale Arat", HubType.WHOLESALE_ARAT, "Dhaka Karwan Bazar", 23.7509, 90.3935, None),
    SellingHub("ARAT-MRP", "Mirpur-1 Wholesale Arat", HubType.WHOLESALE_ARAT, "Dhaka Mirpur", 23.7980, 90.3530, None),
    SellingHub("ARAT-BOG", "Mahasthangarh Haat Arat", HubType.WHOLESALE_ARAT, "Bogura", 24.9620, 89.3420, None),
    SellingHub("ARAT-RAN", "Rangpur City Bazar Arat", HubType.WHOLESALE_ARAT, "Rangpur", 25.7510, 89.2490, None),
    SellingHub("ARAT-JES", "Barinagar Haat Arat", HubType.WHOLESALE_ARAT, "Jessore", 23.1810, 89.1040, None),
    SellingHub("ARAT-MUN", "Mirkadim Potato Arat", HubType.WHOLESALE_ARAT, "Munshiganj", 23.5545, 90.5150, None),
    SellingHub("ARAT-SYL", "Kazir Bazar Arat", HubType.WHOLESALE_ARAT, "Sylhet", 24.8900, 91.8700, None),
    SellingHub("URC-TEJ", "Tejgaon Urban Retail Chain DC", HubType.URBAN_RETAIL_CHAIN, "Dhaka Karwan Bazar", 23.7600, 90.3950, None),
    SellingHub("URC-MRP", "Mirpur Supermarket Consolidation DC", HubType.URBAN_RETAIL_CHAIN, "Dhaka Mirpur", 23.8223, 90.3654, None),
    SellingHub("URC-SYL", "Sylhet Urban Retail Chain DC", HubType.URBAN_RETAIL_CHAIN, "Sylhet", 24.9000, 91.8600, None),
)


WFP_CENTRES_BY_DISTRICT: tuple[tuple[str, int], ...] = (("Cox's Bazar", 62), ("Kurigram", 4))


def _wfp_aggregation_centres() -> tuple[SellingHub, ...]:
    """66 WFP farmer aggregation centres: 62 in Cox's Bazar and 4 in Kurigram."""
    centres: list[SellingHub] = []
    for district_name, count in WFP_CENTRES_BY_DISTRICT:
        upazilas = bd_geo.upazilas_in(district_name)
        for k in range(count):
            upazila = upazilas[k % len(upazilas)]
            serial = len(centres) + 1
            lat = upazila.lat + (stable_unit("wfp-lat", serial) - 0.5) * 0.08
            lon = upazila.lon + (stable_unit("wfp-lon", serial) - 0.5) * 0.08
            cap = round(1_500 + stable_unit("wfp-cap", serial) * 4_500, -2)
            centres.append(
                SellingHub(
                    hub_id=f"WFP-AC-{serial:03d}",
                    name=f"WFP Farmer Aggregation Centre, {upazila.name} #{k // len(upazilas) + 1}",
                    hub_type=HubType.WFP_AGGREGATION_CENTRE,
                    district=district_name,
                    lat=round(lat, 4),
                    lon=round(lon, 4),
                    intake_cap_kg=cap,
                )
            )
    return tuple(centres)


SELLING_HUBS: tuple[SellingHub, ...] = _FIXED_HUBS + _wfp_aggregation_centres()

# ---------------------------------------------------------------------------
# Price engine
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MarketPrices:
    grower: float
    wholesale: float
    retail: float


def _mid_month(year: int, month: int) -> date:
    return date(year, month, 15)


def seasonal_value(series: tuple[float, ...], on: date) -> float:
    """Linear interpolation between mid-month (15th) anchors of a 12-month series."""
    anchor = _mid_month(on.year, on.month)
    if on >= anchor:
        nxt = _mid_month(on.year + (on.month == 12), on.month % 12 + 1)
        start, end, frac = series[on.month - 1], series[nxt.month - 1], (on - anchor).days / (nxt - anchor).days
    else:
        prev = _mid_month(on.year - (on.month == 1), 12 if on.month == 1 else on.month - 1)
        start, end, frac = series[prev.month - 1], series[on.month - 1], (on - prev).days / (anchor - prev).days
    return start + frac * (end - start)


def market_prices(crop: Crop, district: bd_geo.District, on: date) -> MarketPrices:
    curve = SEASONAL_CURVES[crop]
    grower_f, wholesale_f, retail_f = DISTRICT_MARKET_FACTORS[district.name]
    grower_f *= 0.97 if district.name in CROP_SURPLUS_DISTRICTS[crop] else 1.03

    def jitter(tier: str) -> float:
        return 1.0 + 0.025 * (2.0 * stable_unit("dam", on.isoformat(), crop.value, district.name, tier) - 1.0)

    grower = seasonal_value(curve.grower, on) * grower_f * jitter("grower")
    wholesale = max(seasonal_value(curve.wholesale, on) * wholesale_f * jitter("wholesale"), grower * 1.05)
    retail = max(seasonal_value(curve.retail, on) * retail_f * jitter("retail"), wholesale * 1.06)
    return MarketPrices(round(grower, 2), round(wholesale, 2), round(retail, 2))


def markup_pct(low: float, high: float) -> float:
    return round((high - low) / low * 100.0, 2) if low > 0 else 0.0


# ---------------------------------------------------------------------------
# Pooled 5-ton truck transport
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TruckLeg:
    road_km: float
    bridges: tuple[bd_geo.BridgeCrossing, ...]
    trip_cost_tk: float
    cost_per_kg: float
    transit_hours: float


def pooled_truck_leg(origin: bd_geo.District, destination: bd_geo.District, dest_lat: float, dest_lon: float) -> TruckLeg:
    road_km = max(bd_geo.road_distance_km(origin.lat, origin.lon, dest_lat, dest_lon), MIN_LOCAL_HAUL_KM)
    bridges = tuple(bd_geo.bridge_crossings(origin, destination))
    trip_cost = road_km * TRUCK_RATE_TK_PER_KM + TRUCK_FIXED_TK_PER_TRIP + sum(b.toll_tk_medium_truck for b in bridges)
    return TruckLeg(
        road_km=round(road_km, 1),
        bridges=bridges,
        trip_cost_tk=round(trip_cost, 2),
        cost_per_kg=round(trip_cost / TRUCK_CAPACITY_KG + POOLING_FEE_TK_PER_KG, 2),
        transit_hours=round(road_km / AVG_TRUCK_SPEED_KMH + LOADING_HOURS, 2),
    )


def hub_buying_price(hub: SellingHub, crop: Crop, grade: Grade, on: date) -> float | None:
    """Tk/kg the hub pays a grower delivering directly; ``None`` if the hub will not buy."""
    wholesale = market_prices(crop, bd_geo.district_by_name(hub.district), on).wholesale
    match hub.hub_type:
        case HubType.WHOLESALE_ARAT:
            return wholesale * GRADE_PRICE_MULTIPLIER[grade]
        case HubType.URBAN_RETAIL_CHAIN:
            if grade is Grade.C:
                return None
            return wholesale * 1.10 * (1.0 if grade is Grade.A else 0.90)
        case HubType.WFP_AGGREGATION_CENTRE:
            if crop is Crop.BORO_RICE or grade is Grade.C:
                return None
            return wholesale * 1.02 * GRADE_PRICE_MULTIPLIER[grade]


def hub_fees(hub: SellingHub, hub_price: float) -> float:
    match hub.hub_type:
        case HubType.WHOLESALE_ARAT:
            return 0.06 * hub_price + 0.40 + 0.35  # 6% arat commission + khajna + unloading labour
        case HubType.URBAN_RETAIL_CHAIN:
            return 0.03 * hub_price + 0.60  # QC rejection allowance + plastic crating
        case HubType.WFP_AGGREGATION_CENTRE:
            return 0.25  # weighing and handling


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@server.tool(
    title="Daily commodity price spread",
    input_model=GetDailyCommoditySpreadInput,
    output_model=GetDailyCommoditySpreadOutput,
)
async def get_daily_commodity_spread(params: GetDailyCommoditySpreadInput) -> GetDailyCommoditySpreadOutput:
    """Return today's grower (farm-gate), wholesale (arat) and retail prices in Tk/kg for a crop
    in a Bangladeshi district or Dhaka market, the % markup at each step, the farmer's share of the
    retail taka and the trailing 7-day DAM-modelled price series."""
    district = bd_geo.resolve_district(params.district)
    today = now_bdt().date()
    series = [
        (day, market_prices(params.crop, district, day))
        for day in (today - timedelta(days=offset) for offset in range(6, -1, -1))
    ]
    current = series[-1][1]
    first_wholesale = series[0][1].wholesale
    return GetDailyCommoditySpreadOutput(
        crop=params.crop,
        district=district.name,
        division=district.division,
        market_date=today,
        unit=SEASONAL_CURVES[params.crop].unit,
        grower_price_tk_per_kg=current.grower,
        wholesale_price_tk_per_kg=current.wholesale,
        retail_price_tk_per_kg=current.retail,
        grower_to_wholesale_markup_pct=markup_pct(current.grower, current.wholesale),
        wholesale_to_retail_markup_pct=markup_pct(current.wholesale, current.retail),
        total_markup_spread_pct=markup_pct(current.grower, current.retail),
        farmer_share_of_retail_pct=round(current.grower / current.retail * 100.0, 2),
        is_surplus_district=district.name in CROP_SURPLUS_DISTRICTS[params.crop],
        seven_day_series=[
            DailyPricePoint(
                market_date=day,
                grower_price_tk_per_kg=prices.grower,
                wholesale_price_tk_per_kg=prices.wholesale,
                retail_price_tk_per_kg=prices.retail,
            )
            for day, prices in series
        ],
        wholesale_trend_7d_pct=markup_pct(first_wholesale, current.wholesale),
        source="KrishiNexus DAM-modelled daily series calibrated to market.dam.gov.bd district bulletins",
    )


def _severity(markup: float) -> AnomalySeverity:
    if markup >= 100.0:
        return AnomalySeverity.CRITICAL
    if markup >= 75.0:
        return AnomalySeverity.SEVERE
    if markup >= ANOMALY_THRESHOLD_PCT:
        return AnomalySeverity.ELEVATED
    return AnomalySeverity.NORMAL


@server.tool(
    title="Detect syndicate markup anomaly",
    input_model=DetectSyndicateMarkupAnomalyInput,
    output_model=DetectSyndicateMarkupAnomalyOutput,
)
async def detect_syndicate_markup_anomaly(
    params: DetectSyndicateMarkupAnomalyInput,
) -> DetectSyndicateMarkupAnomalyOutput:
    """Compare the farm-gate price in the grower's upazila with the wholesale and retail price at a
    consumer hub. Flags producer-to-retail markups above 40% (e.g. 116% on green chili, 100%+ on
    potato) and decomposes the margin across Faria -> Bepari -> Aratdar -> Paiker -> Retailer,
    itemises the Bepari's marketing cost (62.35% of it taken by the Aratdar, who spends Tk 0 on
    grading) and reports the uplift from a pooled-truck bypass."""
    upazila = bd_geo.resolve_upazila(params.upazila)
    origin = bd_geo.district_by_name(upazila.district)
    hub = bd_geo.resolve_district(params.retail_hub)
    today = now_bdt().date()
    curve = SEASONAL_CURVES[params.crop]

    grower = market_prices(params.crop, origin, today).grower
    hub_prices = market_prices(params.crop, hub, today)
    wholesale = max(hub_prices.wholesale, grower)
    retail = max(hub_prices.retail, wholesale)
    primary_margin = wholesale - grower
    secondary_margin = retail - wholesale
    total_margin = retail - grower

    tiers: list[TierValueCapture] = []
    price = grower
    for order, (tier, share) in enumerate(
        [(t, s * primary_margin) for t, s in PRIMARY_MARGIN_SPLIT]
        + [(t, s * secondary_margin) for t, s in SECONDARY_MARGIN_SPLIT],
        start=1,
    ):
        cost = share * TIER_COST_RATIO[tier]
        tiers.append(
            TierValueCapture(
                tier=tier,
                tier_order=order,
                role=TIER_ROLES[tier],
                buy_price_tk_per_kg=round(price, 2),
                sell_price_tk_per_kg=round(price + share, 2),
                gross_margin_tk_per_kg=round(share, 2),
                marketing_cost_tk_per_kg=round(cost, 2),
                net_profit_tk_per_kg=round(share - cost, 2),
                share_of_total_margin_pct=round(share / total_margin * 100.0, 2) if total_margin > 0 else 0.0,
                share_of_retail_price_pct=round(share / retail * 100.0, 2),
            )
        )
        price += share

    markup = markup_pct(grower, retail)
    severity = _severity(markup)
    aratdar = next(t for t in tiers if t.tier is IntermediaryTier.ARATDAR)
    leg = pooled_truck_leg(origin, hub, hub.lat, hub.lon)
    bypassed = sum(t.gross_margin_tk_per_kg for t in tiers if t.tier in {IntermediaryTier.FARIA, IntermediaryTier.BEPARI})
    bypass_uplift = round(bypassed - leg.cost_per_kg, 2)
    farmer_share = round(grower / retail * 100.0, 2)

    bepari_cost = _BEPARI_COST_SHARE * primary_margin
    aratdar_take = bepari_cost * ARATDAR_SHARE_OF_BEPARI_MARKETING_COST
    cost_lines = [
        MarketingCostLine(
            item="Aratdar commission, khajna and arat charges",
            paid_to="Aratdar",
            tk_per_kg=round(aratdar_take, 2),
            share_of_bepari_marketing_cost_pct=round(ARATDAR_SHARE_OF_BEPARI_MARKETING_COST * 100.0, 2),
        )
    ] + [
        MarketingCostLine(item=item, paid_to=payee, tk_per_kg=round(bepari_cost * share, 2),
                          share_of_bepari_marketing_cost_pct=round(share * 100.0, 2))
        for item, payee, share in BEPARI_OWN_COST_LINES
    ]

    narrative = (
        f"{params.crop.value} from {upazila.name} ({origin.name}) fetches Tk {grower:.2f}/kg at the farm gate "
        f"but retails at Tk {retail:.2f}/kg in {hub.name}: a {markup:.1f}% markup ({severity.value}). "
        f"The grower keeps {farmer_share:.1f}% of the consumer taka while the Aratdar captures "
        f"{aratdar.share_of_total_margin_pct:.1f}% of the total margin"
        + (
            f", taking Tk {aratdar_take:.2f}/kg ({ARATDAR_SHARE_OF_BEPARI_MARKETING_COST:.2%} of the Bepari's "
            f"Tk {bepari_cost:.2f}/kg marketing cost) while spending Tk {ARATDAR_GRADING_SPEND_TK_PER_KG:.0f} on grading. "
            if bepari_cost > 0
            else ". "
        )
        + (
            f"Pooling into a 5-ton truck straight to the arat (Tk {leg.cost_per_kg:.2f}/kg freight) "
            f"bypasses the Faria and Bepari and adds Tk {bypass_uplift:.2f}/kg to the grower's payout."
            if bypass_uplift > 0
            else "Freight to this hub exceeds the Faria + Bepari margin, so a direct bypass is not profitable today."
        )
    )
    return DetectSyndicateMarkupAnomalyOutput(
        crop=params.crop,
        upazila=upazila.name,
        origin_district=origin.name,
        retail_hub=hub.name,
        market_date=today,
        grower_price_tk_per_kg=grower,
        wholesale_price_tk_per_kg=wholesale,
        retail_price_tk_per_kg=retail,
        markup_pct=markup,
        anomaly_threshold_pct=ANOMALY_THRESHOLD_PCT,
        is_anomaly=markup > ANOMALY_THRESHOLD_PCT,
        severity=severity,
        fair_markup_pct=curve.fair_markup_pct,
        excess_extraction_tk_per_kg=round(max(0.0, retail - grower * (1 + curve.fair_markup_pct / 100.0)), 2),
        farmer_share_of_retail_pct=farmer_share,
        bepari_marketing_cost_tk_per_kg=round(bepari_cost, 2),
        aratdar_share_of_bepari_marketing_cost_pct=(
            round(ARATDAR_SHARE_OF_BEPARI_MARKETING_COST * 100.0, 2) if bepari_cost > 0 else 0.0
        ),
        aratdar_take_tk_per_kg=round(aratdar_take, 2),
        aratdar_grading_spend_tk_per_kg=ARATDAR_GRADING_SPEND_TK_PER_KG,
        bepari_marketing_cost_breakdown=cost_lines,
        aratdar_share_of_total_margin_pct=aratdar.share_of_total_margin_pct,
        tier_breakdown=tiers,
        pooled_transport_cost_tk_per_kg=leg.cost_per_kg,
        bypass_uplift_tk_per_kg=bypass_uplift,
        narrative=narrative,
    )


MAX_WFP_OPTIONS_LISTED = 4
MAX_OPTIONS_LISTED = 10


@server.tool(
    title="Find optimal selling hub",
    input_model=FindOptimalSellingHubInput,
    output_model=FindOptimalSellingHubOutput,
)
async def find_optimal_selling_hub(params: FindOptimalSellingHubInput) -> FindOptimalSellingHubOutput:
    """Rank urban retail chain DCs, wholesale arats and the 66 WFP aggregation centres (Cox's Bazar,
    Kurigram) by net grower payout per kg after pooled 5-ton truck freight (Tk 68/km + loading +
    Jamuna/Padma bridge tolls), hub commissions and fees, perishable transit loss and hub intake caps.
    Any volume a capped hub cannot absorb is valued at today's farm-gate price."""
    origin = bd_geo.resolve_district(params.origin_district)
    today = now_bdt().date()
    curve = SEASONAL_CURVES[params.crop]
    farmgate = round(market_prices(params.crop, origin, today).grower * GRADE_PRICE_MULTIPLIER[params.grade], 2)

    candidates: list[SellingHubOption] = []
    rejected = 0
    for hub in SELLING_HUBS:
        hub_price = hub_buying_price(hub, params.crop, params.grade, today)
        if hub_price is None:
            rejected += 1
            continue
        leg = pooled_truck_leg(origin, bd_geo.district_by_name(hub.district), hub.lat, hub.lon)
        accepted_kg = min(params.weight_kg, hub.intake_cap_kg) if hub.intake_cap_kg else params.weight_kg
        fees = hub_fees(hub, hub_price)
        loss_pct = min(40.0, leg.transit_hours * curve.transit_loss_pct_per_hour)
        hub_net = hub_price * (1 - loss_pct / 100.0) - fees - leg.cost_per_kg
        total = accepted_kg * hub_net + (params.weight_kg - accepted_kg) * farmgate
        net_per_kg = total / params.weight_kg
        candidates.append(
            SellingHubOption(
                rank=1,
                hub_id=hub.hub_id,
                hub_name=hub.name,
                hub_type=hub.hub_type,
                district=hub.district,
                road_distance_km=leg.road_km,
                bridge_crossings=[b.name for b in leg.bridges],
                trucks_required=max(1, math.ceil(accepted_kg / TRUCK_CAPACITY_KG)),
                truck_trip_cost_tk=leg.trip_cost_tk,
                transport_cost_tk_per_kg=leg.cost_per_kg,
                hub_price_tk_per_kg=round(hub_price, 2),
                fees_tk_per_kg=round(fees, 2),
                transit_hours=leg.transit_hours,
                transit_loss_pct=round(loss_pct, 3),
                accepted_kg=round(accepted_kg, 1),
                capacity_limited=accepted_kg < params.weight_kg,
                net_payout_tk_per_kg=round(net_per_kg, 2),
                net_payout_total_tk=round(total, 2),
                uplift_vs_farmgate_pct=markup_pct(farmgate, net_per_kg),
            )
        )

    payouts = np.array([c.net_payout_tk_per_kg for c in candidates])
    ranked: list[SellingHubOption] = []
    wfp_listed = 0
    for index in np.argsort(-payouts, kind="stable"):
        option = candidates[int(index)]
        if option.hub_type is HubType.WFP_AGGREGATION_CENTRE:
            if wfp_listed >= MAX_WFP_OPTIONS_LISTED:
                continue
            wfp_listed += 1
        ranked.append(option.model_copy(update={"rank": len(ranked) + 1}))
        if len(ranked) == MAX_OPTIONS_LISTED:
            break

    return FindOptimalSellingHubOutput(
        crop=params.crop,
        origin_district=origin.name,
        grade=params.grade,
        weight_kg=params.weight_kg,
        market_date=today,
        truck_capacity_kg=TRUCK_CAPACITY_KG,
        truck_rate_tk_per_km=TRUCK_RATE_TK_PER_KM,
        farmgate_baseline_tk_per_kg=farmgate,
        farmgate_baseline_total_tk=round(farmgate * params.weight_kg, 2),
        hubs_evaluated=len(candidates),
        hubs_rejected=rejected,
        best_option=ranked[0] if ranked else None,
        ranked_options=ranked,
    )


def _season_phase(month_index: int, curve: SeasonalCurve) -> SeasonPhase:
    grower = np.asarray(curve.grower, dtype=float)
    wholesale = np.asarray(curve.wholesale, dtype=float)
    grower_pos = (grower[month_index] - grower.min()) / (grower.max() - grower.min())
    wholesale_pos = (wholesale[month_index] - wholesale.min()) / (wholesale.max() - wholesale.min())
    if grower_pos <= 0.15:
        return SeasonPhase.HARVEST_DISTRESS
    if wholesale_pos >= 0.80:
        return SeasonPhase.OFF_SEASON_PEAK
    if wholesale[month_index] >= wholesale[month_index - 1]:
        return SeasonPhase.APPRECIATION
    return SeasonPhase.CORRECTION


@server.tool(
    title="Historical seasonal price curve",
    input_model=GetHistoricalSeasonalCurveInput,
    output_model=GetHistoricalSeasonalCurveOutput,
)
async def get_historical_seasonal_curve(params: GetHistoricalSeasonalCurveInput) -> GetHistoricalSeasonalCurveOutput:
    """Return monthly grower/wholesale/retail benchmark prices for the requested months with the
    appreciation from the harvest-distress farm-gate low (potato Tk 5-14/kg in Feb-Mar) to the
    off-season wholesale release (Tk 80-90/kg retail in Aug-Sep), months below the production-cost
    floor and the best release month in range — the E[P_future] input for cold-storage arbitrage."""
    curve = SEASONAL_CURVES[params.crop]
    grower = np.asarray(curve.grower, dtype=float)
    wholesale = np.asarray(curve.wholesale, dtype=float)
    trough_index = int(np.argmin(grower))
    peak_index = int(np.argmax(wholesale))
    harvest_low = float(grower[trough_index])

    months = [
        SeasonalMonthPoint(
            month=month,
            month_name=MONTH_NAMES[month - 1],
            season_phase=_season_phase(month - 1, curve),
            grower_price_tk_per_kg=float(grower[month - 1]),
            wholesale_price_tk_per_kg=float(wholesale[month - 1]),
            retail_price_tk_per_kg=float(curve.retail[month - 1]),
            appreciation_vs_harvest_low_pct=markup_pct(harvest_low, float(wholesale[month - 1])),
            wholesale_mom_change_pct=markup_pct(float(wholesale[month - 2]), float(wholesale[month - 1])),
            below_production_cost=float(grower[month - 1]) < curve.production_cost_floor,
        )
        for month in params.month_range
    ]
    best_release = max(params.month_range, key=lambda m: wholesale[m - 1])
    return GetHistoricalSeasonalCurveOutput(
        crop=params.crop,
        unit=curve.unit,
        basis=(
            "2021-2025 monthly means modelled on market.dam.gov.bd: national farm-gate, "
            "Karwan Bazar wholesale and Karwan Bazar retail"
        ),
        production_cost_floor_tk_per_kg=curve.production_cost_floor,
        harvest_distress_month=trough_index + 1,
        harvest_distress_grower_price_tk_per_kg=harvest_low,
        off_season_peak_month=peak_index + 1,
        off_season_peak_wholesale_tk_per_kg=float(wholesale[peak_index]),
        peak_to_trough_appreciation_pct=markup_pct(harvest_low, float(wholesale[peak_index])),
        best_release_month_in_range=best_release,
        months=months,
    )


if __name__ == "__main__":
    asyncio.run(run_stdio(standalone_dispatcher(server)))
