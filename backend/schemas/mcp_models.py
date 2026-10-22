"""Strict Pydantic v2 contracts for the 13 KrishiNexus OS MCP tools.

Every tool has an ``*Input`` model (validated before execution, published as the
MCP ``inputSchema``) and an ``*Output`` model (published as ``outputSchema`` and
returned as ``structuredContent``). JSON-RPC 2.0 envelopes and the live-demo
anomaly injection contracts live at the bottom of the module.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from config import now_bdt

# ---------------------------------------------------------------------------
# Shared enums and annotated types
# ---------------------------------------------------------------------------


class Crop(StrEnum):
    CARDINAL_POTATO = "Cardinal Potato"
    DIAMANT_POTATO = "Diamant Potato"
    GREEN_CHILI = "Green Chili"
    BRINJAL = "Brinjal"
    BORO_RICE = "Boro Rice"


class Grade(StrEnum):
    A = "A"
    B = "B"
    C = "C"


_CROP_ALIASES: dict[str, Crop] = {
    "cardinal potato": Crop.CARDINAL_POTATO,
    "cardinal": Crop.CARDINAL_POTATO,
    "potato": Crop.CARDINAL_POTATO,
    "alu": Crop.CARDINAL_POTATO,
    "diamant potato": Crop.DIAMANT_POTATO,
    "diamant": Crop.DIAMANT_POTATO,
    "diamond potato": Crop.DIAMANT_POTATO,
    "green chili": Crop.GREEN_CHILI,
    "green chilli": Crop.GREEN_CHILI,
    "chili": Crop.GREEN_CHILI,
    "chilli": Crop.GREEN_CHILI,
    "kacha morich": Crop.GREEN_CHILI,
    "brinjal": Crop.BRINJAL,
    "eggplant": Crop.BRINJAL,
    "begun": Crop.BRINJAL,
    "boro rice": Crop.BORO_RICE,
    "boro": Crop.BORO_RICE,
    "boro paddy": Crop.BORO_RICE,
    "rice": Crop.BORO_RICE,
}


def _normalize_crop(value: Any) -> Any:
    if isinstance(value, str):
        key = re.sub(r"[\s_\-]+", " ", value.strip().lower())
        return _CROP_ALIASES.get(key, value)
    return value


def _normalize_grade(value: Any) -> Any:
    if isinstance(value, str):
        cleaned = value.strip().upper().removeprefix("GRADE").strip(" -_")
        return cleaned or value
    return value


CropField = Annotated[
    Crop,
    BeforeValidator(_normalize_crop),
    Field(description="Crop. Accepts canonical names or common aliases (e.g. 'green chilli', 'begun')."),
]
GradeField = Annotated[
    Grade,
    BeforeValidator(_normalize_grade),
    Field(description="Optical quality grade: A (premium), B (standard), C (bruised/undersized)."),
]
PlaceName = Annotated[
    str,
    Field(min_length=2, max_length=60, description="Bangladeshi district, upazila or market name."),
]
TkPerKg = Annotated[float, Field(ge=0, description="Price or cost in Bangladeshi Taka per kg.")]
Percent = Annotated[float, Field(description="Percentage value (0-100 unless noted).")]


class ToolInput(BaseModel):
    """Base for tool arguments: unknown keys are rejected, strings are trimmed."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ToolOutput(BaseModel):
    """Base for tool results: every payload is timestamped in BDT."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime = Field(default_factory=now_bdt, description="Result timestamp (BDT, UTC+06:00).")


# ---------------------------------------------------------------------------
# Server 1 — dam-market-mcp
# ---------------------------------------------------------------------------


class IntermediaryTier(StrEnum):
    FARIA = "Faria"
    BEPARI = "Bepari"
    ARATDAR = "Aratdar"
    PAIKER = "Paiker"
    RETAILER = "Retailer"


class AnomalySeverity(StrEnum):
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    SEVERE = "SEVERE"
    CRITICAL = "CRITICAL"


class HubType(StrEnum):
    URBAN_RETAIL_CHAIN = "URBAN_RETAIL_CHAIN"
    WHOLESALE_ARAT = "WHOLESALE_ARAT"
    WFP_AGGREGATION_CENTRE = "WFP_AGGREGATION_CENTRE"


class SeasonPhase(StrEnum):
    HARVEST_DISTRESS = "HARVEST_DISTRESS"
    APPRECIATION = "APPRECIATION"
    OFF_SEASON_PEAK = "OFF_SEASON_PEAK"
    CORRECTION = "CORRECTION"


class GetDailyCommoditySpreadInput(ToolInput):
    crop: CropField
    district: PlaceName = Field(description="Market district, e.g. 'Bogura', 'Munshiganj', 'Dhaka Karwan Bazar'.")


class DailyPricePoint(BaseModel):
    market_date: date
    grower_price_tk_per_kg: TkPerKg
    wholesale_price_tk_per_kg: TkPerKg
    retail_price_tk_per_kg: TkPerKg


class GetDailyCommoditySpreadOutput(ToolOutput):
    crop: Crop
    district: str
    division: str
    market_date: date
    unit: str
    grower_price_tk_per_kg: TkPerKg
    wholesale_price_tk_per_kg: TkPerKg
    retail_price_tk_per_kg: TkPerKg
    grower_to_wholesale_markup_pct: Percent
    wholesale_to_retail_markup_pct: Percent
    total_markup_spread_pct: Percent = Field(description="(retail - grower) / grower x 100.")
    farmer_share_of_retail_pct: Percent
    is_surplus_district: bool = Field(description="District is a net-surplus producer of this crop.")
    seven_day_series: list[DailyPricePoint]
    wholesale_trend_7d_pct: Percent
    source: str


class DetectSyndicateMarkupAnomalyInput(ToolInput):
    crop: CropField
    upazila: PlaceName = Field(description="Origin upazila (or district) where the grower sells.")
    retail_hub: PlaceName = Field(description="Consumer market, e.g. 'Dhaka Karwan Bazar', 'Dhaka Mirpur', 'Sylhet'.")


class TierValueCapture(BaseModel):
    tier: IntermediaryTier
    tier_order: int = Field(ge=1, le=5)
    role: str
    buy_price_tk_per_kg: TkPerKg
    sell_price_tk_per_kg: TkPerKg
    gross_margin_tk_per_kg: TkPerKg
    marketing_cost_tk_per_kg: TkPerKg
    net_profit_tk_per_kg: float
    share_of_total_margin_pct: Percent
    share_of_retail_price_pct: Percent


class MarketingCostLine(BaseModel):
    item: str
    paid_to: str
    tk_per_kg: TkPerKg
    share_of_bepari_marketing_cost_pct: Percent


class DetectSyndicateMarkupAnomalyOutput(ToolOutput):
    crop: Crop
    upazila: str
    origin_district: str
    retail_hub: str
    market_date: date
    grower_price_tk_per_kg: TkPerKg
    wholesale_price_tk_per_kg: TkPerKg
    retail_price_tk_per_kg: TkPerKg
    markup_pct: Percent = Field(description="Producer-to-retail markup (retail - grower) / grower x 100.")
    anomaly_threshold_pct: Percent
    is_anomaly: bool
    severity: AnomalySeverity
    fair_markup_pct: Percent = Field(description="Markup justified by logistics, handling and normal margins.")
    excess_extraction_tk_per_kg: TkPerKg
    farmer_share_of_retail_pct: Percent
    bepari_marketing_cost_tk_per_kg: TkPerKg = Field(
        description="Bepari's full marketing cost per kg (freight, labour, wastage, bags, tolls and Aratdar charges)."
    )
    aratdar_share_of_bepari_marketing_cost_pct: Percent = Field(
        description="Share of the Bepari's marketing cost extracted by the Aratdar as commission, khajna and arat "
        "charges (CPD July 2026 benchmark: 62.35%)."
    )
    aratdar_take_tk_per_kg: TkPerKg = Field(description="Aratdar commission, khajna and arat charges per kg.")
    aratdar_grading_spend_tk_per_kg: TkPerKg = Field(
        description="What the Aratdar spends on sorting and grading in return (Tk 0 per CPD July 2026)."
    )
    bepari_marketing_cost_breakdown: list[MarketingCostLine]
    aratdar_share_of_total_margin_pct: Percent
    tier_breakdown: list[TierValueCapture]
    pooled_transport_cost_tk_per_kg: TkPerKg
    bypass_uplift_tk_per_kg: float = Field(
        description="Extra Tk/kg the grower keeps by bypassing Faria + Bepari via a pooled 5-ton truck."
    )
    narrative: str


class FindOptimalSellingHubInput(ToolInput):
    crop: CropField
    weight_kg: float = Field(gt=0, le=100_000, description="Lot weight to sell, in kg.")
    origin_district: PlaceName = Field(description="District where the lot is loaded.")
    grade: GradeField


class SellingHubOption(BaseModel):
    rank: int = Field(ge=1)
    hub_id: str
    hub_name: str
    hub_type: HubType
    district: str
    road_distance_km: float = Field(ge=0)
    bridge_crossings: list[str]
    trucks_required: int = Field(ge=1)
    truck_trip_cost_tk: float = Field(ge=0)
    transport_cost_tk_per_kg: TkPerKg
    hub_price_tk_per_kg: TkPerKg
    fees_tk_per_kg: TkPerKg
    transit_hours: float = Field(ge=0)
    transit_loss_pct: Percent
    accepted_kg: float = Field(ge=0)
    capacity_limited: bool
    net_payout_tk_per_kg: float
    net_payout_total_tk: float
    uplift_vs_farmgate_pct: Percent


class FindOptimalSellingHubOutput(ToolOutput):
    crop: Crop
    origin_district: str
    grade: Grade
    weight_kg: float
    market_date: date
    truck_capacity_kg: int
    truck_rate_tk_per_km: float
    farmgate_baseline_tk_per_kg: TkPerKg = Field(description="Price a Faria pays at the farm gate today.")
    farmgate_baseline_total_tk: float
    hubs_evaluated: int
    hubs_rejected: int = Field(description="Hubs that do not buy this crop/grade.")
    best_option: SellingHubOption | None
    ranked_options: list[SellingHubOption]


class GetHistoricalSeasonalCurveInput(ToolInput):
    crop: CropField
    month_range: list[Annotated[int, Field(ge=1, le=12)]] = Field(
        min_length=1,
        max_length=12,
        description="Calendar months (1-12) in the order to report, e.g. [2, 3, 8, 9]. Wrap-around allowed.",
    )

    @field_validator("month_range")
    @classmethod
    def _unique_months(cls, months: list[int]) -> list[int]:
        if len(set(months)) != len(months):
            raise ValueError("month_range must not contain duplicate months")
        return months


class SeasonalMonthPoint(BaseModel):
    month: int = Field(ge=1, le=12)
    month_name: str
    season_phase: SeasonPhase
    grower_price_tk_per_kg: TkPerKg
    wholesale_price_tk_per_kg: TkPerKg
    retail_price_tk_per_kg: TkPerKg
    appreciation_vs_harvest_low_pct: Percent = Field(
        description="Wholesale price vs. the year's lowest farm-gate (harvest distress) price."
    )
    wholesale_mom_change_pct: Percent
    below_production_cost: bool


class GetHistoricalSeasonalCurveOutput(ToolOutput):
    crop: Crop
    unit: str
    basis: str
    production_cost_floor_tk_per_kg: TkPerKg
    harvest_distress_month: int
    harvest_distress_grower_price_tk_per_kg: TkPerKg
    off_season_peak_month: int
    off_season_peak_wholesale_tk_per_kg: TkPerKg
    peak_to_trough_appreciation_pct: Percent
    best_release_month_in_range: int
    months: list[SeasonalMonthPoint]


# ---------------------------------------------------------------------------
# Server 2 — agri-weather-sar-mcp
# ---------------------------------------------------------------------------

Latitude = Annotated[float, Field(ge=20.3, le=26.8, description="Latitude within Bangladesh (deg N).")]
Longitude = Annotated[float, Field(ge=87.9, le=92.8, description="Longitude within Bangladesh (deg E).")]


class WeatherDataSource(StrEnum):
    OPEN_METEO_LIVE = "OPEN_METEO_LIVE"
    CLIMATOLOGY_FALLBACK = "CLIMATOLOGY_FALLBACK"


class FloodAlertLevel(StrEnum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    RED = "RED"


class CropStage(StrEnum):
    SEEDLING = "seedling"
    VEGETATIVE = "vegetative"
    FLOWERING = "flowering"
    FRUITING_OR_TUBER_BULKING = "fruiting_or_tuber_bulking"
    MATURITY = "maturity"
    POST_HARVEST_STORAGE = "post_harvest_storage"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    SEVERE = "SEVERE"


class VpdStatus(StrEnum):
    TOO_LOW = "TOO_LOW"
    OPTIMAL = "OPTIMAL"
    ELEVATED = "ELEVATED"
    SEVERE = "SEVERE"


class UrgencyLevel(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


def _normalize_upper(value: Any) -> Any:
    return value.strip().upper() if isinstance(value, str) else value


def _normalize_stage(value: Any) -> Any:
    if isinstance(value, str):
        key = re.sub(r"[\s\-]+", "_", value.strip().lower())
        return {"fruiting": "fruiting_or_tuber_bulking", "tuber_bulking": "fruiting_or_tuber_bulking",
                "storage": "post_harvest_storage", "post_harvest": "post_harvest_storage"}.get(key, key)
    return value


class GetCurrentWeatherInput(ToolInput):
    latitude: Latitude
    longitude: Longitude


class GetCurrentWeatherOutput(ToolOutput):
    latitude: float
    longitude: float
    nearest_district: str
    observed_at: datetime
    temperature_c: float
    apparent_temperature_c: float
    relative_humidity_pct: Percent
    wind_speed_kmh: float = Field(ge=0)
    wind_direction_deg: float = Field(ge=0, le=360)
    precipitation_mm: float = Field(ge=0)
    surface_pressure_hpa: float
    weather_code: int
    weather_description: str
    data_source: WeatherDataSource


class GetWeatherByDatetimeRangeInput(ToolInput):
    latitude: Latitude
    longitude: Longitude
    start_date: date = Field(description="ISO date YYYY-MM-DD (inclusive).")
    end_date: date = Field(description="ISO date YYYY-MM-DD (inclusive); at most 6 days after start_date.")

    @model_validator(mode="after")
    def _check_window(self) -> GetWeatherByDatetimeRangeInput:
        span = (self.end_date - self.start_date).days
        if span < 0:
            raise ValueError("end_date must be on or after start_date")
        if span > 6:
            raise ValueError("date window must not exceed 7 days")
        return self


class HourlyWeatherPoint(BaseModel):
    time: datetime
    temperature_c: float
    relative_humidity_pct: Percent
    precipitation_mm: float = Field(ge=0)
    precipitation_probability_pct: Percent
    wind_speed_kmh: float = Field(ge=0)
    wind_gusts_kmh: float = Field(ge=0)
    weather_code: int
    is_storm_hour: bool


class DailyWeatherSummary(BaseModel):
    date: date
    total_precipitation_mm: float = Field(ge=0)
    max_temperature_c: float
    min_temperature_c: float
    mean_relative_humidity_pct: Percent
    max_wind_gust_kmh: float = Field(ge=0)
    heavy_rain_hours: int = Field(ge=0)
    storm_hours: int = Field(ge=0)


class GetWeatherByDatetimeRangeOutput(ToolOutput):
    latitude: float
    longitude: float
    nearest_district: str
    start_date: date
    end_date: date
    hours_count: int
    total_precipitation_mm: float = Field(ge=0)
    max_hourly_precipitation_mm: float = Field(ge=0)
    storm_risk: bool
    storm_warnings: list[str]
    daily: list[DailyWeatherSummary]
    hourly: list[HourlyWeatherPoint]
    data_source: WeatherDataSource


class CalculateHaorFlashFloodRiskInput(ToolInput):
    upazila: PlaceName = Field(description="Haor upazila in Sunamganj, Kishoreganj or Netrokona (e.g. 'Tahirpur').")
    sar_water_backscatter_db: float = Field(
        ge=-35.0,
        le=5.0,
        description="Sentinel-1 VV backscatter (dB). Open water is typically below -18 dB; dry land -12 to -6 dB.",
    )


class CalculateHaorFlashFloodRiskOutput(ToolOutput):
    upazila: str
    district: str
    sar_water_backscatter_db: float
    sar_water_fraction: float = Field(ge=0, le=1)
    upstream_catchment: str
    upstream_rainfall_72h_mm: float = Field(ge=0)
    rainfall_source: WeatherDataSource
    rainfall_trigger_threshold_mm: float
    embankment_vulnerability_index: float = Field(ge=0, le=1)
    seasonal_exposure_factor: float = Field(ge=0, le=1)
    embankment_breach_probability_pct: Percent
    alert_level: FloodAlertLevel
    historical_boro_loss_benchmark_pct: Percent
    expected_boro_loss_pct: Percent
    boro_area_ha: float = Field(ge=0)
    boro_at_risk_tons: float = Field(ge=0)
    flood_wave_lead_time_hours: float = Field(ge=0)
    recommended_harvest_within_hours: float = Field(ge=0)
    simulated_anomaly_active: bool
    recommended_actions: list[str]
    voice_alert_bn: str


class ComputeCropVpdStressInput(ToolInput):
    crop: CropField
    crop_stage: Annotated[CropStage, BeforeValidator(_normalize_stage)]
    temp_c: float = Field(ge=-5, le=50, description="Air temperature (deg C).")
    rh_pct: float = Field(ge=0, le=100, description="Relative humidity (%).")


class ComputeCropVpdStressOutput(ToolOutput):
    crop: Crop
    crop_stage: CropStage
    temp_c: float
    rh_pct: float
    saturation_vapor_pressure_kpa: float
    actual_vapor_pressure_kpa: float
    vpd_kpa: float
    dew_point_c: float
    optimal_vpd_band_kpa: tuple[float, float]
    vpd_status: VpdStatus
    transpiration_stress_index: float = Field(ge=0, le=1)
    pathogen: str
    fungal_risk_pct: Percent
    fungal_risk_level: RiskLevel
    recommendations: list[str]


class TriggerEarlyHarvestWindowInput(ToolInput):
    cluster_id: str = Field(pattern=r"^[A-Za-z0-9_\-]{3,40}$", description="Farmer cluster identifier.")
    upazila: PlaceName
    urgency_level: Annotated[UrgencyLevel, BeforeValidator(_normalize_upper)]


class TruckBooking(BaseModel):
    booking_id: str
    depot: str
    truck_capacity_kg: int
    phase: int = Field(ge=1, le=3)
    dispatch_at: datetime
    assigned_tons: float = Field(ge=0)
    status: Literal["PRE_BOOKED"]


class HarvestPhase(BaseModel):
    phase: int = Field(ge=1, le=3)
    start_at: datetime
    end_at: datetime
    priority: str
    target_area_ha: float = Field(ge=0)
    target_paddy_tons: float = Field(ge=0)
    combine_harvesters: int = Field(ge=0)
    manual_labourers: int = Field(ge=0)
    trucks: int = Field(ge=0)


class TriggerEarlyHarvestWindowOutput(ToolOutput):
    dispatch_id: str
    cluster_id: str
    upazila: str
    district: str
    urgency_level: UrgencyLevel
    plan_horizon_hours: int
    window_start: datetime
    harvest_complete_by: datetime
    farmer_count: int
    boro_area_ha: float
    harvestable_maturity_pct: Percent
    expected_paddy_tons: float
    combine_harvesters_required: int
    manual_labourers_required: int
    trucks_required: int
    truck_bookings: list[TruckBooking]
    phases: list[HarvestPhase]
    safe_storage_destination: str
    estimated_harvest_cost_tk: float
    estimated_transport_cost_tk: float
    idempotent_replay: bool = Field(description="True when an identical plan was already issued today.")
    voice_alert_bn: str


# ---------------------------------------------------------------------------
# Server 3 — coldchain-iot-mcp
# ---------------------------------------------------------------------------

FacilityId = Annotated[
    str,
    BeforeValidator(_normalize_upper),
    Field(pattern=r"^BCSA-[A-Z]{3}-\d{2}$", description="BCSA facility id, e.g. 'BCSA-MUN-01'."),
]
ChamberId = Annotated[
    str,
    BeforeValidator(_normalize_upper),
    Field(pattern=r"^CH-\d{2}$", description="Chamber id within the facility, e.g. 'CH-03'."),
]


class PowerSource(StrEnum):
    GRID = "GRID"
    DIESEL_GENERATOR = "DIESEL_GENERATOR"
    OUTAGE = "OUTAGE"


class ReservationStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"


class QueryColdStorageQuotaInput(ToolInput):
    district: PlaceName = Field(description="District of the farmer cluster, e.g. 'Munshiganj', 'Bogura'.")
    radius_km: int = Field(ge=5, le=400, description="Maximum road distance to a facility (km).")
    tons_needed: float = Field(gt=0, le=2_000, description="Metric tons the cluster needs to store.")


class ColdStorageFacilityQuota(BaseModel):
    facility_id: str
    name: str
    district: str
    upazila: str
    road_distance_km: float = Field(ge=0)
    total_capacity_mt: float = Field(ge=0)
    trader_quota_mt: float = Field(ge=0)
    owner_quota_mt: float = Field(ge=0)
    farmer_quota_mt: float = Field(ge=0)
    farmer_quota_booked_mt: float = Field(ge=0)
    open_smallholder_quota_mt: float = Field(ge=0)
    chambers: int = Field(ge=1)
    tariff_tk_per_kg: TkPerKg
    handling_fee_tk_per_kg: TkPerKg
    transport_cost_tk_per_kg: TkPerKg
    all_in_cost_tk_per_kg: TkPerKg
    can_fulfil_request: bool
    power_status: PowerSource


class QuotaCaptureBreakdown(BaseModel):
    traders_pct: Percent
    plant_owners_pct: Percent
    farmers_pct: Percent
    non_farmer_capture_pct: Percent


class DistrictStorageGap(BaseModel):
    district: str
    registered_facilities: int
    storage_capacity_mt: float
    potato_output_mt: float
    storage_coverage_pct: Percent
    uncovered_output_mt: float


class AllocationLeg(BaseModel):
    facility_id: str
    tons: float = Field(gt=0)
    all_in_cost_tk: float = Field(ge=0)


class QueryColdStorageQuotaOutput(ToolOutput):
    district: str
    radius_km: int
    tons_needed: float
    facilities_found: int
    total_open_smallholder_quota_mt: float
    single_facility_fulfilment: bool
    recommended_allocation: list[AllocationLeg]
    unallocated_tons: float = Field(ge=0)
    quota_capture: QuotaCaptureBreakdown
    district_gap: DistrictStorageGap | None
    facilities: list[ColdStorageFacilityQuota]


class GetChamberTelemetryInput(ToolInput):
    facility_id: FacilityId
    chamber_id: ChamberId


class GetChamberTelemetryOutput(ToolOutput):
    facility_id: str
    facility_name: str
    chamber_id: str
    mqtt_topic: str
    recorded_at: datetime
    stored_crop: Crop
    stored_tons: float = Field(ge=0)
    setpoint_c: float
    temperature_c: float
    temperature_f: float
    relative_humidity_pct: Percent
    co2_ppm: float = Field(ge=0)
    power_source: PowerSource
    compressor_running: bool
    generator_fuel_pct: Percent | None
    outage_minutes: int = Field(ge=0)
    temperature_in_optimal_band: bool = Field(description="Optimal band 48-50 deg F (8.9-10.0 deg C).")
    humidity_in_optimal_band: bool = Field(description="Optimal band 92-95% RH.")
    rot_risk_pct: Percent
    alerts: list[str]
    simulated_anomaly_active: bool


class CalculateDynamicShelfLifeInput(ToolInput):
    crop: CropField
    grade: GradeField
    transit_temp_c: float = Field(ge=-5, le=50, description="Pulp/air temperature during transit or storage (deg C).")
    rh_pct: float = Field(ge=10, le=100, description="Relative humidity (%).")


class CalculateDynamicShelfLifeOutput(ToolOutput):
    crop: Crop
    grade: Grade
    transit_temp_c: float
    rh_pct: float
    reference_temp_c: float
    reference_rh_band_pct: tuple[float, float]
    reference_shelf_life_hours: float
    q10: float
    temperature_factor: float
    humidity_factor: float
    grade_factor: float
    chilling_injury_risk: bool
    remaining_shelf_life_hours: float = Field(ge=0)
    remaining_shelf_life_days: float = Field(ge=0)
    lambda_rot: float = Field(ge=0.012, le=0.09, description="Expected fractional spoilage over the holding horizon.")
    max_safe_transit_hours: float = Field(ge=0)
    storage_advice: list[str]


class ReserveCollectiveStorageSlotInput(ToolInput):
    cluster_id: str = Field(pattern=r"^[A-Za-z0-9_\-]{3,40}$", description="Farmer cluster identifier.")
    facility_id: FacilityId
    tons: float = Field(gt=0, le=1_000, description="Pooled tonnage to reserve.")
    farmer_count: int = Field(ge=1, le=500, description="Number of smallholders in the pool.")

    @model_validator(mode="after")
    def _smallholder_pool(self) -> ReserveCollectiveStorageSlotInput:
        if self.tons / self.farmer_count > 10:
            raise ValueError("average holding exceeds 10 t per farmer; smallholder quota requires <= 10 t each")
        return self


class ReserveCollectiveStorageSlotOutput(ToolOutput):
    status: ReservationStatus
    receipt_id: str | None
    cluster_id: str
    facility_id: str
    facility_name: str
    requested_tons: float
    reserved_tons: float = Field(ge=0)
    waitlisted_tons: float = Field(ge=0)
    farmer_count: int
    avg_tons_per_farmer: float
    bags_50kg: int = Field(ge=0)
    tariff_tk_per_kg: TkPerKg
    handling_fee_tk_per_kg: TkPerKg
    storage_charge_total_tk: float = Field(ge=0)
    handling_charge_total_tk: float = Field(ge=0)
    total_charge_tk: float = Field(ge=0)
    per_farmer_charge_tk: float = Field(ge=0)
    valid_from: date | None
    valid_until: date | None
    remaining_open_quota_mt: float = Field(ge=0)
    signature_algorithm: Literal["HMAC-SHA256"]
    receipt_signature: str | None
    reason: str


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 / MCP envelopes
# ---------------------------------------------------------------------------

JsonRpcId = StrictInt | StrictStr | None


class JsonRpcRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jsonrpc: Literal["2.0"]
    id: JsonRpcId = None
    method: StrictStr = Field(min_length=1)
    params: dict[str, Any] | None = None


class JsonRpcErrorObject(BaseModel):
    code: int
    message: str
    data: Any | None = None


class JsonRpcResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: JsonRpcId
    result: Any | None = None
    error: JsonRpcErrorObject | None = None


class ToolCallParams(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: StrictStr = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class McpToolDescriptor(BaseModel):
    server: str
    name: str
    title: str
    description: str
    inputSchema: dict[str, Any]
    outputSchema: dict[str, Any]
    annotations: dict[str, Any]


class McpServerDescriptor(BaseModel):
    name: str
    title: str
    version: str
    description: str
    protocol_version: str
    transports: list[str]
    endpoint: str
    stdio_command: str
    tool_count: int
    tools: list[str]


class McpToolsListing(BaseModel):
    count: int
    servers: list[str]
    tools: list[McpToolDescriptor]


# ---------------------------------------------------------------------------
# Live-demo anomaly injection
# ---------------------------------------------------------------------------


class PowerCutAnomalyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anomaly_type: Literal["cold_chamber_power_cut"]
    facility_id: FacilityId = "BCSA-MUN-01"
    chamber_id: ChamberId | None = Field(default=None, description="Omit to cut power to every chamber.")
    generator_failed: bool = Field(default=True, description="False = grid lost but diesel backup starts.")
    elapsed_minutes: int = Field(default=120, ge=0, le=1_440, description="Minutes the outage has already lasted.")
    duration_minutes: int = Field(default=360, ge=5, le=4_320, description="How long the injection stays active.")


class FlashFloodAnomalyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anomaly_type: Literal["haor_flash_flood"]
    upazila: PlaceName = "Tahirpur"
    upstream_rainfall_72h_mm: float = Field(default=320.0, ge=0, le=1_500)
    sar_water_backscatter_db: float = Field(default=-19.5, ge=-35, le=5)
    scenario_month: int = Field(default=4, ge=1, le=12, description="Crop-calendar month to simulate (4 = April Boro).")
    duration_minutes: int = Field(default=720, ge=5, le=4_320)


SimulateAnomalyRequest = Annotated[
    PowerCutAnomalyRequest | FlashFloodAnomalyRequest,
    Field(discriminator="anomaly_type"),
]


class ActiveAnomalyView(BaseModel):
    anomaly_id: str
    anomaly_type: Literal["cold_chamber_power_cut", "haor_flash_flood"]
    target: str
    params: dict[str, Any]
    activated_at: datetime
    expires_at: datetime


class SimulateAnomalyResponse(BaseModel):
    anomaly: ActiveAnomalyView
    message: str
    impact_tool: str
    impact_preview: dict[str, Any]
