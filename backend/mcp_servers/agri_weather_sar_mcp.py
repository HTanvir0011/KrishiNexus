"""MCP Server 2 — ``agri-weather-sar-mcp`` (Streamable HTTP / SSE + stdio).

Live weather comes from the free, keyless Open-Meteo forecast API via async
``httpx``. When the API is unreachable (rural edge nodes, demo halls without
internet) every tool degrades to a deterministic climatology generator built from
Bangladesh Meteorological Department monthly normals with regional adjustments
(Sylhet/haor orographic rain, northern winter cold, coastal Cox's Bazar), so
results stay reproducible for a given place and hour.

Haor flash-flood risk fuses Sentinel-1 VV backscatter (open water < -18 dB) with
72-hour rainfall over the upstream Meghalaya / Barak catchments that drive
pre-monsoon flash floods into Sunamganj, Kishoreganj and Netrokona.

Run standalone over stdio:  ``python -m mcp_servers.agri_weather_sar_mcp``
"""

from __future__ import annotations

import asyncio
import calendar
import hashlib
import logging
import math
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import httpx
import numpy as np

from config import BDT, now_bdt, settings
from mcp_servers import bd_geo
from mcp_servers.anomaly_state import ANOMALIES
from mcp_servers.base import McpServer, ToolExecutionError, run_stdio, stable_unit, standalone_dispatcher
from schemas.mcp_models import (
    CalculateHaorFlashFloodRiskInput,
    CalculateHaorFlashFloodRiskOutput,
    ComputeCropVpdStressInput,
    ComputeCropVpdStressOutput,
    Crop,
    CropStage,
    DailyWeatherSummary,
    FloodAlertLevel,
    GetCurrentWeatherInput,
    GetCurrentWeatherOutput,
    GetWeatherByDatetimeRangeInput,
    GetWeatherByDatetimeRangeOutput,
    HarvestPhase,
    HourlyWeatherPoint,
    RiskLevel,
    TriggerEarlyHarvestWindowInput,
    TriggerEarlyHarvestWindowOutput,
    TruckBooking,
    UrgencyLevel,
    VpdStatus,
    WeatherDataSource,
)

logger = logging.getLogger("krishinexus.mcp.weather")

server = McpServer(
    name="agri-weather-sar-mcp",
    title="Agri Weather & Sentinel-1 SAR Flood MCP",
    version="1.0.0",
    description=(
        "Open-Meteo live weather for Bangladeshi farm coordinates, 7-day hourly storm arrays, "
        "Sentinel-1 SAR + upstream-rainfall haor flash-flood breach probability, crop VPD and fungal "
        "blight risk, and 72-hour emergency Boro harvest dispatch with pre-booked 5-ton trucks."
    ),
    transports=("streamable-http", "sse", "stdio"),
    module="mcp_servers.agri_weather_sar_mcp",
)

# ---------------------------------------------------------------------------
# Open-Meteo client
# ---------------------------------------------------------------------------

_client: httpx.AsyncClient | None = None

NETWORK_BLACKOUT: ContextVar[bool] = ContextVar("knx_network_blackout", default=False)
"""Set True within a request to simulate a rural internet outage (forces the climatology fallback)."""


def _http_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=settings.http_timeout_seconds,
            headers={"User-Agent": f"KrishiNexusOS/{settings.app_version} (agri-weather-sar-mcp)"},
        )
    return _client


async def aclose_http_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def _open_meteo(params: dict[str, Any]) -> dict[str, Any] | None:
    """GET the Open-Meteo forecast endpoint; ``None`` signals the caller to fall back."""
    if settings.force_offline_weather or NETWORK_BLACKOUT.get():
        return None
    try:
        response = await _http_client().get(settings.open_meteo_forecast_url, params={**params, "timezone": "Asia/Dhaka"})
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Open-Meteo unavailable (%s); using climatology fallback", exc)
        return None
    if not isinstance(payload, dict) or payload.get("error"):
        return None
    return payload


def _local_time(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=BDT)


def _num(value: Any, default: float) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else default


WMO_WEATHER_CODES: dict[int, str] = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snowfall", 73: "Moderate snowfall", 75: "Heavy snowfall", 77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}

# ---------------------------------------------------------------------------
# Climatology fallback (BMD 1991-2020 normals, Dhaka reference)
# ---------------------------------------------------------------------------

CLIMATE_MEAN_TEMP_C = (19.0, 22.3, 26.5, 28.7, 29.0, 28.9, 28.7, 28.9, 28.6, 27.3, 23.9, 20.3)
CLIMATE_DIURNAL_AMPLITUDE_C = (5.5, 5.8, 5.6, 4.6, 3.8, 2.8, 2.4, 2.6, 2.8, 3.4, 4.6, 5.4)
CLIMATE_MEAN_RH_PCT = (70, 64, 62, 71, 77, 83, 85, 84, 83, 79, 74, 73)
CLIMATE_RAIN_MM = (8, 21, 56, 151, 300, 348, 395, 314, 312, 172, 33, 13)
CLIMATE_WIND_KMH = (6.5, 7.5, 9.5, 12.0, 11.5, 10.5, 10.0, 9.0, 8.0, 6.5, 5.5, 5.5)
CLIMATE_WIND_DIR_DEG = (320, 300, 230, 200, 190, 170, 165, 170, 175, 60, 340, 330)
CLIMATE_PRESSURE_HPA = (1015.5, 1013.4, 1010.0, 1006.6, 1003.6, 999.8, 999.0, 1000.3, 1004.0, 1009.0, 1013.0, 1015.4)
RAIN_INTENSITY_MM_PER_HOUR = 3.5
HEAVY_RAIN_MM_PER_HOUR = 7.6
STORM_GUST_KMH = 62.0


@dataclass(frozen=True, slots=True)
class HourSample:
    time: datetime
    temperature_c: float
    relative_humidity_pct: float
    precipitation_mm: float
    precipitation_probability_pct: float
    wind_speed_kmh: float
    wind_gusts_kmh: float
    wind_direction_deg: float
    weather_code: int
    surface_pressure_hpa: float


def _regional_adjustment(lat: float, lon: float, month: int) -> tuple[float, float]:
    """(temperature offset deg C, rainfall multiplier) relative to Dhaka normals."""
    if lon >= 90.9 and lat >= 24.2:
        return 0.0, 1.65  # Sylhet and haor basin: Meghalaya orographic rain
    if lat <= 22.5:
        return 0.4, 1.45  # Cox's Bazar coast
    if lat >= 25.3:
        return (-1.6 if month in (11, 12, 1, 2) else -0.3), 1.10  # Rangpur / Thakurgaon / Kurigram
    if lon < 89.6 and lat < 24.0:
        return (0.6 if month in (4, 5) else 0.2), 0.85  # Jessore heat belt
    return 0.0, 1.0


def _weather_code(precip: float, rh: float, storm: bool) -> int:
    if storm:
        return 95
    if precip >= HEAVY_RAIN_MM_PER_HOUR:
        return 65
    if precip >= 2.5:
        return 63
    if precip > 0:
        return 61
    if rh >= 85:
        return 3
    if rh >= 70:
        return 2
    return 1


def climatology_hour(lat: float, lon: float, at: datetime) -> HourSample:
    """Deterministic synthetic hour from monthly normals for a coordinate."""
    m = at.month - 1
    temp_offset, rain_factor = _regional_adjustment(lat, lon, at.month)
    key = (round(lat, 2), round(lon, 2), at.strftime("%Y-%m-%dT%H"))
    mean = CLIMATE_MEAN_TEMP_C[m] + temp_offset
    temp = mean + CLIMATE_DIURNAL_AMPLITUDE_C[m] * math.cos(2 * math.pi * (at.hour - 15) / 24)

    days = calendar.monthrange(at.year, at.month)[1]
    rain_hours_per_day = CLIMATE_RAIN_MM[m] * rain_factor / days / RAIN_INTENSITY_MM_PER_HOUR
    p_rain = min(0.6, rain_hours_per_day / 24) * (1.35 if 13 <= at.hour <= 20 else 0.8)
    precip = 0.0
    if stable_unit("rain", *key) < p_rain:
        precip = RAIN_INTENSITY_MM_PER_HOUR * (0.4 + 1.8 * stable_unit("rain-amount", *key))

    wind = CLIMATE_WIND_KMH[m] * (0.6 + 0.8 * stable_unit("wind", *key)) * (1.25 if 12 <= at.hour <= 18 else 0.85)
    gust = wind * 1.7
    storm = at.month in (3, 4, 5) and 14 <= at.hour <= 20 and stable_unit("storm", *key) < 0.035
    if storm:  # Kalbaishakhi (nor'wester) squall
        gust = 65.0 + 35.0 * stable_unit("storm-gust", *key)
        precip += 12.0

    rh = float(np.clip(CLIMATE_MEAN_RH_PCT[m] - 2.2 * (temp - mean), 35, 99))
    if precip > 0:
        rh = max(rh, 92.0)
    return HourSample(
        time=at.replace(minute=0, second=0, microsecond=0),
        temperature_c=round(temp, 1),
        relative_humidity_pct=round(rh, 1),
        precipitation_mm=round(precip, 1),
        precipitation_probability_pct=85.0 if precip > 0 else round(min(70.0, p_rain * 240), 0),
        wind_speed_kmh=round(wind, 1),
        wind_gusts_kmh=round(gust, 1),
        wind_direction_deg=float((CLIMATE_WIND_DIR_DEG[m] + 40 * (stable_unit("wdir", *key) - 0.5)) % 360),
        weather_code=_weather_code(precip, rh, storm),
        surface_pressure_hpa=round(CLIMATE_PRESSURE_HPA[m] - (4.0 if storm else 0.0), 1),
    )


def apparent_temperature_c(temp_c: float, rh_pct: float, wind_kmh: float) -> float:
    """NOAA Rothfusz heat index above 27 deg C, otherwise a mild wind-chill adjustment."""
    if temp_c >= 27.0 and rh_pct >= 40.0:
        t = temp_c * 9 / 5 + 32
        hi = (
            -42.379 + 2.04901523 * t + 10.14333127 * rh_pct - 0.22475541 * t * rh_pct
            - 6.83783e-3 * t**2 - 5.481717e-2 * rh_pct**2 + 1.22874e-3 * t**2 * rh_pct
            + 8.5282e-4 * t * rh_pct**2 - 1.99e-6 * t**2 * rh_pct**2
        )
        return round((hi - 32) * 5 / 9, 1)
    return round(temp_c - 0.04 * wind_kmh, 1)


# ---------------------------------------------------------------------------
# Haor seed data: upstream catchments, upazila exposure, historical losses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class UpstreamCatchment:
    name: str
    lat: float
    lon: float
    monthly_rain_mm: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class HaorDistrict:
    catchment: UpstreamCatchment
    trigger_rainfall_72h_mm: float
    boro_loss_benchmark_pct: float  # share of Boro lost in the April 2017 flash flood
    truck_depot: str
    safe_storage: str


@dataclass(frozen=True, slots=True)
class HaorUpazila:
    name_bn: str
    embankment_vulnerability: float
    boro_area_ha: float
    flood_wave_lead_time_h: float


SOHRA = UpstreamCatchment(
    "Meghalaya - Sohra (Cherrapunji) catchment", 25.2700, 91.7300,
    (11, 40, 210, 650, 1090, 2350, 2520, 1780, 1190, 450, 50, 10),
)
GARO_HILLS = UpstreamCatchment(
    "Meghalaya - Garo Hills (Tura) catchment", 25.5138, 90.2036,
    (10, 25, 70, 210, 420, 600, 560, 480, 410, 210, 30, 8),
)
BARAK = UpstreamCatchment(
    "Barak basin - Silchar (Assam) catchment", 24.8333, 92.7789,
    (15, 50, 180, 380, 520, 560, 500, 440, 330, 190, 40, 12),
)

HAOR_DISTRICTS: dict[str, HaorDistrict] = {
    "Sunamganj": HaorDistrict(SOHRA, 180.0, 65.0, "Sunamganj Sadar Truck Terminal", "Sunamganj Sadar LSD godown (DG Food) and elevated union kholas"),
    "Kishoreganj": HaorDistrict(BARAK, 230.0, 44.0, "Bhairab Truck Terminal", "Bhairab rice-mill drying yards and Kishoreganj LSD godown"),
    "Netrokona": HaorDistrict(GARO_HILLS, 200.0, 21.0, "Mohanganj Truck Stand", "Mohanganj LSD godown (DG Food) and Netrokona Sadar mills"),
}

HAOR_UPAZILAS: dict[str, HaorUpazila] = {
    "Sunamganj Sadar": HaorUpazila("সুনামগঞ্জ সদর", 0.70, 14_200, 20),
    "Tahirpur": HaorUpazila("তাহিরপুর", 0.82, 18_500, 18),
    "Dharmapasha": HaorUpazila("ধর্মপাশা", 0.78, 31_000, 28),
    "Jamalganj": HaorUpazila("জামালগঞ্জ", 0.74, 16_500, 24),
    "Derai": HaorUpazila("দিরাই", 0.72, 23_000, 30),
    "Shalla": HaorUpazila("শাল্লা", 0.80, 14_000, 34),
    "Kishoreganj Sadar": HaorUpazila("কিশোরগঞ্জ সদর", 0.45, 9_800, 60),
    "Itna": HaorUpazila("ইটনা", 0.70, 25_000, 48),
    "Mithamain": HaorUpazila("মিঠামইন", 0.66, 18_000, 50),
    "Austagram": HaorUpazila("অষ্টগ্রাম", 0.62, 22_000, 54),
    "Nikli": HaorUpazila("নিকলী", 0.60, 14_500, 52),
    "Netrokona Sadar": HaorUpazila("নেত্রকোনা সদর", 0.40, 8_500, 46),
    "Khaliajuri": HaorUpazila("খালিয়াজুরী", 0.68, 20_500, 40),
    "Mohanganj": HaorUpazila("মোহনগঞ্জ", 0.58, 16_000, 36),
    "Madan": HaorUpazila("মদন", 0.55, 13_500, 42),
}

BORO_YIELD_T_PER_HA = 4.2
# Share of the Boro crop standing in the field, by calendar month (harvest peaks late April-May).
BORO_SEASONAL_EXPOSURE = (0.15, 0.25, 0.70, 1.00, 0.85, 0.20, 0.05, 0.05, 0.05, 0.10, 0.10, 0.10)

_BANGLA_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


def to_bangla_digits(value: object) -> str:
    return str(value).translate(_BANGLA_DIGITS)


async def upstream_rainfall_72h(catchment: UpstreamCatchment, today: date) -> tuple[float, WeatherDataSource]:
    """Next-72-hour accumulated rainfall over an upstream catchment (mm)."""
    payload = await _open_meteo(
        {"latitude": catchment.lat, "longitude": catchment.lon, "hourly": "precipitation", "forecast_hours": 72}
    )
    hourly = (payload or {}).get("hourly", {}).get("precipitation")
    if isinstance(hourly, list) and hourly:
        return round(sum(_num(v, 0.0) for v in hourly[:72]), 1), WeatherDataSource.OPEN_METEO_LIVE
    days = calendar.monthrange(today.year, today.month)[1]
    mean_72h = catchment.monthly_rain_mm[today.month - 1] / days * 3
    return round(mean_72h * (0.6 + 0.8 * stable_unit("upstream", catchment.name, today.isoformat())), 1), (
        WeatherDataSource.CLIMATOLOGY_FALLBACK
    )


# ---------------------------------------------------------------------------
# Tools: weather
# ---------------------------------------------------------------------------

_CURRENT_FIELDS = (
    "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,"
    "weather_code,surface_pressure,wind_speed_10m,wind_direction_10m"
)
_HOURLY_FIELDS = (
    "temperature_2m,relative_humidity_2m,precipitation,precipitation_probability,"
    "wind_speed_10m,wind_gusts_10m,weather_code"
)


@server.tool(
    title="Current weather (Open-Meteo)",
    input_model=GetCurrentWeatherInput,
    output_model=GetCurrentWeatherOutput,
    open_world=True,
)
async def get_current_weather(params: GetCurrentWeatherInput) -> GetCurrentWeatherOutput:
    """Live temperature, humidity, wind and precipitation for a Bangladeshi coordinate from the
    Open-Meteo forecast API (e.g. Sunamganj 25.0658, 91.3950), with a deterministic BMD-climatology
    fallback when offline. ``data_source`` states which was used."""
    lat, lon = params.latitude, params.longitude
    nearest = bd_geo.nearest_district(lat, lon)
    now = now_bdt()
    fallback = climatology_hour(lat, lon, now)
    payload = await _open_meteo({"latitude": lat, "longitude": lon, "current": _CURRENT_FIELDS})
    current = (payload or {}).get("current")

    if isinstance(current, dict) and isinstance(current.get("temperature_2m"), (int, float)):
        code = int(_num(current.get("weather_code"), fallback.weather_code))
        return GetCurrentWeatherOutput(
            latitude=lat,
            longitude=lon,
            nearest_district=nearest.name,
            observed_at=_local_time(current["time"]) if isinstance(current.get("time"), str) else now,
            temperature_c=_num(current.get("temperature_2m"), fallback.temperature_c),
            apparent_temperature_c=_num(current.get("apparent_temperature"), fallback.temperature_c),
            relative_humidity_pct=_num(current.get("relative_humidity_2m"), fallback.relative_humidity_pct),
            wind_speed_kmh=_num(current.get("wind_speed_10m"), fallback.wind_speed_kmh),
            wind_direction_deg=_num(current.get("wind_direction_10m"), fallback.wind_direction_deg),
            precipitation_mm=_num(current.get("precipitation"), 0.0),
            surface_pressure_hpa=_num(current.get("surface_pressure"), fallback.surface_pressure_hpa),
            weather_code=code,
            weather_description=WMO_WEATHER_CODES.get(code, "Unknown"),
            data_source=WeatherDataSource.OPEN_METEO_LIVE,
        )

    return GetCurrentWeatherOutput(
        latitude=lat,
        longitude=lon,
        nearest_district=nearest.name,
        observed_at=fallback.time,
        temperature_c=fallback.temperature_c,
        apparent_temperature_c=apparent_temperature_c(
            fallback.temperature_c, fallback.relative_humidity_pct, fallback.wind_speed_kmh
        ),
        relative_humidity_pct=fallback.relative_humidity_pct,
        wind_speed_kmh=fallback.wind_speed_kmh,
        wind_direction_deg=fallback.wind_direction_deg,
        precipitation_mm=fallback.precipitation_mm,
        surface_pressure_hpa=fallback.surface_pressure_hpa,
        weather_code=fallback.weather_code,
        weather_description=WMO_WEATHER_CODES[fallback.weather_code],
        data_source=WeatherDataSource.CLIMATOLOGY_FALLBACK,
    )


def _is_storm(sample: HourSample) -> bool:
    return sample.wind_gusts_kmh >= STORM_GUST_KMH or 95 <= sample.weather_code <= 99


@server.tool(
    title="Hourly weather for a date range (max 7 days)",
    input_model=GetWeatherByDatetimeRangeInput,
    output_model=GetWeatherByDatetimeRangeOutput,
    open_world=True,
)
async def get_weather_by_datetime_range(params: GetWeatherByDatetimeRangeInput) -> GetWeatherByDatetimeRangeOutput:
    """Hourly temperature, humidity, rain, rain probability, wind and gusts for up to 7 days, with
    daily aggregates and storm warnings (Kalbaishakhi squalls >= 62 km/h gusts, BMD heavy-rain days
    >= 44 mm). Uses Open-Meteo (about -92 to +16 days from today) or the climatology fallback."""
    lat, lon = params.latitude, params.longitude
    span_days = (params.end_date - params.start_date).days + 1
    expected_hours = span_days * 24
    payload = await _open_meteo(
        {
            "latitude": lat,
            "longitude": lon,
            "hourly": _HOURLY_FIELDS,
            "start_date": params.start_date.isoformat(),
            "end_date": params.end_date.isoformat(),
        }
    )
    hourly = (payload or {}).get("hourly") or {}
    times = hourly.get("time")

    samples: list[HourSample]
    if isinstance(times, list) and len(times) == expected_hours:
        source = WeatherDataSource.OPEN_METEO_LIVE
        samples = []
        for i, stamp in enumerate(times):
            at = _local_time(stamp)
            fb = climatology_hour(lat, lon, at)

            def column(name: str, default: float, index: int = i) -> float:
                values = hourly.get(name)
                return _num(values[index], default) if isinstance(values, list) and index < len(values) else default

            precip = column("precipitation", fb.precipitation_mm)
            samples.append(
                HourSample(
                    time=at,
                    temperature_c=column("temperature_2m", fb.temperature_c),
                    relative_humidity_pct=column("relative_humidity_2m", fb.relative_humidity_pct),
                    precipitation_mm=precip,
                    precipitation_probability_pct=column(
                        "precipitation_probability", 85.0 if precip > 0 else fb.precipitation_probability_pct
                    ),
                    wind_speed_kmh=column("wind_speed_10m", fb.wind_speed_kmh),
                    wind_gusts_kmh=column("wind_gusts_10m", fb.wind_gusts_kmh),
                    wind_direction_deg=fb.wind_direction_deg,
                    weather_code=int(column("weather_code", fb.weather_code)),
                    surface_pressure_hpa=fb.surface_pressure_hpa,
                )
            )
    else:
        source = WeatherDataSource.CLIMATOLOGY_FALLBACK
        start = datetime(params.start_date.year, params.start_date.month, params.start_date.day, tzinfo=BDT)
        samples = [climatology_hour(lat, lon, start + timedelta(hours=h)) for h in range(expected_hours)]

    daily: list[DailyWeatherSummary] = []
    warnings: list[str] = []
    for day_index in range(span_days):
        chunk = samples[day_index * 24 : (day_index + 1) * 24]
        precip = np.array([s.precipitation_mm for s in chunk])
        temps = np.array([s.temperature_c for s in chunk])
        gusts = np.array([s.wind_gusts_kmh for s in chunk])
        summary = DailyWeatherSummary(
            date=params.start_date + timedelta(days=day_index),
            total_precipitation_mm=round(float(precip.sum()), 1),
            max_temperature_c=round(float(temps.max()), 1),
            min_temperature_c=round(float(temps.min()), 1),
            mean_relative_humidity_pct=round(float(np.mean([s.relative_humidity_pct for s in chunk])), 1),
            max_wind_gust_kmh=round(float(gusts.max()), 1),
            heavy_rain_hours=int((precip >= HEAVY_RAIN_MM_PER_HOUR).sum()),
            storm_hours=sum(1 for s in chunk if _is_storm(s)),
        )
        daily.append(summary)
        if summary.storm_hours:
            warnings.append(
                f"{summary.date}: {summary.storm_hours} thunderstorm/squall hour(s), gusts up to "
                f"{summary.max_wind_gust_kmh:.0f} km/h - secure polythene sheds, postpone spraying, harvest mature plots."
            )
        if summary.total_precipitation_mm >= 89:
            warnings.append(f"{summary.date}: very heavy rain {summary.total_precipitation_mm:.0f} mm (BMD >= 89 mm) - waterlogging and flash-flood risk.")
        elif summary.total_precipitation_mm >= 44:
            warnings.append(f"{summary.date}: heavy rain {summary.total_precipitation_mm:.0f} mm (BMD 44-88 mm) - clear field drains.")

    all_precip = [s.precipitation_mm for s in samples]
    return GetWeatherByDatetimeRangeOutput(
        latitude=lat,
        longitude=lon,
        nearest_district=bd_geo.nearest_district(lat, lon).name,
        start_date=params.start_date,
        end_date=params.end_date,
        hours_count=len(samples),
        total_precipitation_mm=round(sum(all_precip), 1),
        max_hourly_precipitation_mm=round(max(all_precip), 1),
        storm_risk=bool(warnings),
        storm_warnings=warnings,
        daily=daily,
        hourly=[
            HourlyWeatherPoint(
                time=s.time,
                temperature_c=s.temperature_c,
                relative_humidity_pct=min(100.0, s.relative_humidity_pct),
                precipitation_mm=s.precipitation_mm,
                precipitation_probability_pct=s.precipitation_probability_pct,
                wind_speed_kmh=s.wind_speed_kmh,
                wind_gusts_kmh=s.wind_gusts_kmh,
                weather_code=s.weather_code,
                is_storm_hour=_is_storm(s),
            )
            for s in samples
        ],
        data_source=source,
    )


# ---------------------------------------------------------------------------
# Tools: haor flash flood + early harvest
# ---------------------------------------------------------------------------


def _haor_context(upazila_name: str) -> tuple[bd_geo.Upazila, HaorDistrict, HaorUpazila]:
    upazila = bd_geo.resolve_upazila(upazila_name)
    district = HAOR_DISTRICTS.get(upazila.district)
    profile = HAOR_UPAZILAS.get(upazila.name)
    if district is None or profile is None:
        raise ToolExecutionError(
            f"'{upazila.name}' ({upazila.district}) is not a modelled haor upazila. "
            f"Supported: {', '.join(HAOR_UPAZILAS)}."
        )
    return upazila, district, profile


def breach_probability(rainfall_72h_mm: float, sar_db: float, district: HaorDistrict, profile: HaorUpazila,
                       month: int) -> tuple[float, float, float, float]:
    """Logistic fusion of upstream rain, SAR water fraction, embankment vulnerability and Boro exposure.

    Returns (probability, sar_water_fraction, rain_ratio, seasonal_exposure).
    """
    water_fraction = 1.0 / (1.0 + math.exp((sar_db + 16.5) / 1.6))
    rain_ratio = rainfall_72h_mm / district.trigger_rainfall_72h_mm
    exposure = BORO_SEASONAL_EXPOSURE[month - 1]
    z = -5.0 + 3.2 * rain_ratio + 2.6 * water_fraction + 2.0 * profile.embankment_vulnerability + 1.2 * exposure
    return 1.0 / (1.0 + math.exp(-z)), water_fraction, rain_ratio, exposure


def _alert_level(probability: float) -> FloodAlertLevel:
    if probability >= 0.70:
        return FloodAlertLevel.RED
    if probability >= 0.45:
        return FloodAlertLevel.ORANGE
    if probability >= 0.20:
        return FloodAlertLevel.YELLOW
    return FloodAlertLevel.GREEN


@server.tool(
    title="Haor flash-flood embankment breach risk (Sentinel-1 SAR + upstream rain)",
    input_model=CalculateHaorFlashFloodRiskInput,
    output_model=CalculateHaorFlashFloodRiskOutput,
    open_world=True,
)
async def calculate_haor_flash_flood_risk(
    params: CalculateHaorFlashFloodRiskInput,
) -> CalculateHaorFlashFloodRiskOutput:
    """Fuse cloud-penetrating Sentinel-1 VV backscatter (water fraction via a logistic on dB) with
    72-hour forecast rainfall over the upstream Meghalaya/Barak catchment to estimate the haor
    embankment breach probability, alert level, expected Boro loss against the 2017 benchmarks
    (65% Sunamganj, 44% Kishoreganj, 21% Netrokona) and the hours left for emergency harvest."""
    upazila, district, profile = _haor_context(params.upazila)
    now = now_bdt()
    rainfall, source = await upstream_rainfall_72h(district.catchment, now.date())
    month = now.month

    flood = ANOMALIES.latest("haor_flash_flood", lambda a: a.params.get("district") == upazila.district)
    if flood is not None:
        rainfall = max(rainfall, float(flood.params["upstream_rainfall_72h_mm"]))
        month = int(flood.params["scenario_month"])

    probability, water_fraction, rain_ratio, exposure = breach_probability(
        rainfall, params.sar_water_backscatter_db, district, profile, month)
    alert = _alert_level(probability)

    lead_time = profile.flood_wave_lead_time_h * float(np.clip(1.25 - 0.35 * rain_ratio, 0.45, 1.25))
    harvest_within = {
        FloodAlertLevel.RED: max(4.0, lead_time - 6.0),
        FloodAlertLevel.ORANGE: lead_time + 12.0,
        FloodAlertLevel.YELLOW: 48.0,
        FloodAlertLevel.GREEN: 72.0,
    }[alert]
    expected_loss_pct = district.boro_loss_benchmark_pct * probability
    at_risk_tons = profile.boro_area_ha * BORO_YIELD_T_PER_HA * exposure * expected_loss_pct / 100.0
    pct_bn = to_bangla_digits(min(99, round(probability * 100)))
    hours_bn = to_bangla_digits(round(harvest_within))

    actions: list[str]
    match alert:
        case FloodAlertLevel.RED:
            actions = [
                "Call trigger_early_harvest_window with urgency_level=CRITICAL for every cluster in the upazila.",
                f"Harvest all plots >= 80% grain maturity within {harvest_within:.0f} h; prioritise plots nearest the embankment.",
                "Move threshed paddy to elevated kholas or the LSD godown; do not dry on the haor floor.",
                "Alert the BWDB embankment PIC committee and Upazila Agriculture Officer for sandbag reinforcement.",
            ]
            voice = f"জরুরি সতর্কতা: {profile.name_bn} হাওরে বাঁধ ভাঙার সম্ভাবনা {pct_bn} শতাংশ। আগামী {hours_bn} ঘণ্টার মধ্যে পাকা বোরো ধান কেটে উঁচু জায়গায় সরিয়ে নিন।"
        case FloodAlertLevel.ORANGE:
            actions = [
                "Call trigger_early_harvest_window with urgency_level=HIGH and pre-book combine harvesters.",
                "Start harvesting plots >= 85% mature; stage tarpaulins and trucks at the nearest high road.",
                "Re-run this tool every 6 h with the latest Sentinel-1 pass.",
            ]
            voice = f"সতর্কতা: উজানে ভারী বৃষ্টি। {profile.name_bn} হাওরে বাঁধ ভাঙার ঝুঁকি {pct_bn} শতাংশ। {hours_bn} ঘণ্টার মধ্যে ধান কাটার প্রস্তুতি নিন।"
        case FloodAlertLevel.YELLOW:
            actions = [
                "Keep harvesters and labour on standby; confirm truck availability at the depot.",
                "Monitor upstream rainfall and the next Sentinel-1 acquisition (6-12 day revisit).",
            ]
            voice = f"{profile.name_bn} হাওরে পানি বাড়ছে। বাঁধ ভাঙার ঝুঁকি {pct_bn} শতাংশ। ধান কাটার যন্ত্র ও শ্রমিক প্রস্তুত রাখুন।"
        case FloodAlertLevel.GREEN:
            actions = ["No emergency action; continue the normal harvest calendar and weekly monitoring."]
            voice = f"{profile.name_bn} হাওরে বন্যার ঝুঁকি কম ({pct_bn} শতাংশ)। স্বাভাবিক সময়সূচিতে ধান কাটুন।"

    return CalculateHaorFlashFloodRiskOutput(
        upazila=upazila.name,
        district=upazila.district,
        sar_water_backscatter_db=params.sar_water_backscatter_db,
        sar_water_fraction=round(water_fraction, 4),
        upstream_catchment=district.catchment.name,
        upstream_rainfall_72h_mm=round(rainfall, 1),
        rainfall_source=source,
        rainfall_trigger_threshold_mm=district.trigger_rainfall_72h_mm,
        embankment_vulnerability_index=profile.embankment_vulnerability,
        seasonal_exposure_factor=exposure,
        embankment_breach_probability_pct=round(probability * 100.0, 2),
        alert_level=alert,
        historical_boro_loss_benchmark_pct=district.boro_loss_benchmark_pct,
        expected_boro_loss_pct=round(expected_loss_pct, 2),
        boro_area_ha=profile.boro_area_ha,
        boro_at_risk_tons=round(at_risk_tons, 1),
        flood_wave_lead_time_hours=round(lead_time, 1),
        recommended_harvest_within_hours=round(harvest_within, 1),
        simulated_anomaly_active=flood is not None,
        recommended_actions=actions,
        voice_alert_bn=voice,
    )


URGENCY_COMPLETION_HOURS: dict[UrgencyLevel, int] = {
    UrgencyLevel.LOW: 72,
    UrgencyLevel.MODERATE: 60,
    UrgencyLevel.HIGH: 48,
    UrgencyLevel.CRITICAL: 36,
}
URGENCY_COMBINE_SHARE: dict[UrgencyLevel, float] = {
    UrgencyLevel.LOW: 0.50,
    UrgencyLevel.MODERATE: 0.60,
    UrgencyLevel.HIGH: 0.70,
    UrgencyLevel.CRITICAL: 0.80,
}
COMBINE_HA_PER_HOUR = 0.40
MANUAL_HA_PER_PERSON_HOUR = 0.006
FIELD_HOURS_PER_DAY = 14
COMBINE_COST_TK_PER_HA = 9_500.0
MANUAL_WAGE_TK_PER_DAY = 950.0
HAUL_KM_TO_SAFE_STORAGE = 30.0
TRUCK_CAPACITY_KG = 5_000
PHASE_PLAN = (
    (1, 0.45, "Lowest-lying plots nearest embankment breach points"),
    (2, 0.35, "Mid-elevation plots"),
    (3, 0.20, "Higher plots and threshing-floor clearance"),
)

_DISPATCH_LEDGER: dict[str, TriggerEarlyHarvestWindowOutput] = {}


@server.tool(
    title="Trigger 72-hour early harvest window",
    input_model=TriggerEarlyHarvestWindowInput,
    output_model=TriggerEarlyHarvestWindowOutput,
    read_only=False,
)
async def trigger_early_harvest_window(params: TriggerEarlyHarvestWindowInput) -> TriggerEarlyHarvestWindowOutput:
    """Generate an emergency 72-hour harvest dispatch plan for a farmer cluster: harvestable area,
    combine harvesters and labourers needed to finish within the urgency deadline (CRITICAL 36 h,
    HIGH 48 h, MODERATE 60 h, LOW 72 h), a 3-phase low-to-high field sequence, and pre-booked 5-ton
    trucks to safe storage. Idempotent per cluster/upazila/urgency/day."""
    upazila = bd_geo.resolve_upazila(params.upazila)
    haor = HAOR_DISTRICTS.get(upazila.district)
    now = now_bdt()
    digest = hashlib.sha256(
        f"{params.cluster_id}|{upazila.name}|{params.urgency_level.value}|{now.date()}".encode()
    ).hexdigest()
    dispatch_id = f"EHW-{now:%Y%m%d}-{digest[:8].upper()}"
    if dispatch_id in _DISPATCH_LEDGER:
        return _DISPATCH_LEDGER[dispatch_id].model_copy(update={"idempotent_replay": True})

    cid = params.cluster_id.upper()
    farmer_count = 25 + int(stable_unit("farmers", cid) * 96)
    area_ha = farmer_count * (0.35 + 0.25 * stable_unit("holding", cid))
    maturity_pct = 78.0 + 16.0 * stable_unit("maturity", cid)
    target_area = area_ha * maturity_pct / 100.0
    paddy_tons = target_area * BORO_YIELD_T_PER_HA

    completion_h = URGENCY_COMPLETION_HOURS[params.urgency_level]
    working_hours = completion_h * FIELD_HOURS_PER_DAY / 24
    combine_share = URGENCY_COMBINE_SHARE[params.urgency_level]
    combines = math.ceil(target_area * combine_share / (COMBINE_HA_PER_HOUR * working_hours))
    labourers = math.ceil(target_area * (1 - combine_share) / (MANUAL_HA_PER_PERSON_HOUR * working_hours))
    surge = 1.3 if params.urgency_level is UrgencyLevel.CRITICAL else 1.0

    window_start = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    depot = haor.truck_depot if haor else f"{upazila.district} Sadar Truck Terminal"
    storage = haor.safe_storage if haor else f"{upazila.district} Sadar LSD godown (DG Food)"
    phase_hours = completion_h / len(PHASE_PLAN)

    phases: list[HarvestPhase] = []
    bookings: list[TruckBooking] = []
    for phase_no, share, priority in PHASE_PLAN:
        start = window_start + timedelta(hours=phase_hours * (phase_no - 1))
        phase_tons = paddy_tons * share
        trucks = max(1, math.ceil(phase_tons * 1000 / TRUCK_CAPACITY_KG))
        phases.append(
            HarvestPhase(
                phase=phase_no,
                start_at=start,
                end_at=start + timedelta(hours=phase_hours),
                priority=priority,
                target_area_ha=round(target_area * share, 2),
                target_paddy_tons=round(phase_tons, 2),
                combine_harvesters=combines,
                manual_labourers=labourers,
                trucks=trucks,
            )
        )
        for n in range(1, trucks + 1):
            bookings.append(
                TruckBooking(
                    booking_id=f"TRK-{upazila.district[:3].upper()}-{digest[8:12].upper()}-{phase_no}{n:02d}",
                    depot=depot,
                    truck_capacity_kg=TRUCK_CAPACITY_KG,
                    phase=phase_no,
                    dispatch_at=start + timedelta(hours=4 + (n - 1) * 1.5),
                    assigned_tons=round(phase_tons / trucks, 2),
                    status="PRE_BOOKED",
                )
            )

    days = completion_h / 24
    harvest_cost = (
        target_area * combine_share * COMBINE_COST_TK_PER_HA * surge
        + labourers * MANUAL_WAGE_TK_PER_DAY * surge * math.ceil(days)
    )
    transport_cost = len(bookings) * (HAUL_KM_TO_SAFE_STORAGE * 68.0 + 1_500.0)
    name_bn = HAOR_UPAZILAS[upazila.name].name_bn if upazila.name in HAOR_UPAZILAS else upazila.name
    voice = (
        f"জরুরি ধান কাটা কর্মসূচি: {name_bn} এলাকার {params.cluster_id} ক্লাস্টারের "
        f"{to_bangla_digits(farmer_count)} জন কৃষক, {to_bangla_digits(completion_h)} ঘণ্টার মধ্যে পাকা ধান কাটা শেষ করুন। "
        f"{to_bangla_digits(combines)}টি কম্বাইন হারভেস্টার ও {to_bangla_digits(len(bookings))}টি ট্রাক বুক করা হয়েছে।"
    )
    plan = TriggerEarlyHarvestWindowOutput(
        dispatch_id=dispatch_id,
        cluster_id=params.cluster_id,
        upazila=upazila.name,
        district=upazila.district,
        urgency_level=params.urgency_level,
        plan_horizon_hours=72,
        window_start=window_start,
        harvest_complete_by=window_start + timedelta(hours=completion_h),
        farmer_count=farmer_count,
        boro_area_ha=round(area_ha, 2),
        harvestable_maturity_pct=round(maturity_pct, 1),
        expected_paddy_tons=round(paddy_tons, 2),
        combine_harvesters_required=combines,
        manual_labourers_required=labourers,
        trucks_required=len(bookings),
        truck_bookings=bookings,
        phases=phases,
        safe_storage_destination=storage,
        estimated_harvest_cost_tk=round(harvest_cost, 2),
        estimated_transport_cost_tk=round(transport_cost, 2),
        idempotent_replay=False,
        voice_alert_bn=voice,
    )
    _DISPATCH_LEDGER[dispatch_id] = plan
    return plan


# ---------------------------------------------------------------------------
# Tool: crop VPD stress
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CropDiseaseProfile:
    field_vpd_band_kpa: tuple[float, float]
    storage_vpd_band_kpa: tuple[float, float]
    field_pathogen: str
    field_optimum_c: float
    field_sigma_c: float
    storage_pathogen: str
    storage_optimum_c: float
    storage_sigma_c: float
    storage_rh_threshold_pct: float


_POTATO_PROFILE = CropDiseaseProfile(
    (0.45, 1.00), (0.05, 0.25), "Late blight (Phytophthora infestans)", 18.0, 6.0,
    "Dry rot / soft rot (Fusarium spp., Pectobacterium carotovorum)", 20.0, 7.0, 96.0,
)
DISEASE_PROFILES: dict[Crop, CropDiseaseProfile] = {
    Crop.CARDINAL_POTATO: _POTATO_PROFILE,
    Crop.DIAMANT_POTATO: _POTATO_PROFILE,
    Crop.GREEN_CHILI: CropDiseaseProfile(
        (0.70, 1.25), (0.10, 0.35), "Anthracnose / dieback (Colletotrichum capsici)", 27.0, 5.0,
        "Post-harvest fruit rot (Colletotrichum, Alternaria)", 25.0, 6.0, 93.0,
    ),
    Crop.BRINJAL: CropDiseaseProfile(
        (0.70, 1.30), (0.10, 0.35), "Phomopsis blight (Phomopsis vexans)", 28.0, 5.0,
        "Phomopsis fruit rot", 27.0, 6.0, 93.0,
    ),
    Crop.BORO_RICE: CropDiseaseProfile(
        (0.60, 1.30), (0.80, 1.60), "Rice blast (Magnaporthe oryzae)", 25.0, 4.0,
        "Storage mould (Aspergillus flavus)", 30.0, 6.0, 75.0,
    ),
}
STAGE_BAND_SHIFT: dict[CropStage, tuple[float, float]] = {
    CropStage.SEEDLING: (-0.15, -0.20),
    CropStage.VEGETATIVE: (0.0, 0.0),
    CropStage.FLOWERING: (-0.05, -0.20),
    CropStage.FRUITING_OR_TUBER_BULKING: (0.0, 0.0),
    CropStage.MATURITY: (0.10, 0.30),
    CropStage.POST_HARVEST_STORAGE: (0.0, 0.0),
}
STAGE_SUSCEPTIBILITY: dict[CropStage, float] = {
    CropStage.SEEDLING: 0.80,
    CropStage.VEGETATIVE: 0.90,
    CropStage.FLOWERING: 1.15,
    CropStage.FRUITING_OR_TUBER_BULKING: 1.10,
    CropStage.MATURITY: 0.85,
    CropStage.POST_HARVEST_STORAGE: 0.70,
}
FIELD_RH_THRESHOLD_PCT = 88.0


def _risk_level(risk_pct: float) -> RiskLevel:
    if risk_pct >= 75:
        return RiskLevel.SEVERE
    if risk_pct >= 50:
        return RiskLevel.HIGH
    if risk_pct >= 25:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


@server.tool(
    title="Crop vapour-pressure-deficit stress and fungal risk",
    input_model=ComputeCropVpdStressInput,
    output_model=ComputeCropVpdStressOutput,
)
async def compute_crop_vpd_stress(params: ComputeCropVpdStressInput) -> ComputeCropVpdStressOutput:
    """Compute saturation/actual vapour pressure (Tetens), VPD (kPa) and dew point (Magnus), compare
    VPD with the crop- and stage-specific optimal band, and estimate the risk (%) of the dominant
    fungal disease (late blight, anthracnose, Phomopsis blight, rice blast or storage mould) from
    humidity, leaf-wetness proxy, temperature suitability and stage susceptibility."""
    t, rh = params.temp_c, params.rh_pct
    profile = DISEASE_PROFILES[params.crop]
    storage = params.crop_stage is CropStage.POST_HARVEST_STORAGE

    svp = 0.6108 * math.exp(17.27 * t / (t + 237.3))
    avp = svp * rh / 100.0
    vpd = svp - avp
    gamma = math.log(max(rh, 1.0) / 100.0) + 17.62 * t / (243.12 + t)
    dew_point = 243.12 * gamma / (17.62 - gamma)

    base_low, base_high = profile.storage_vpd_band_kpa if storage else profile.field_vpd_band_kpa
    shift_low, shift_high = STAGE_BAND_SHIFT[params.crop_stage]
    low, high = max(0.05, base_low + shift_low), max(0.15, base_high + shift_high)
    if vpd < low:
        status = VpdStatus.TOO_LOW
    elif vpd <= high:
        status = VpdStatus.OPTIMAL
    elif vpd <= high * 1.6:
        status = VpdStatus.ELEVATED
    else:
        status = VpdStatus.SEVERE
    stress = float(np.clip((vpd - high) / (high * 1.5), 0.0, 1.0))

    pathogen = profile.storage_pathogen if storage else profile.field_pathogen
    optimum = profile.storage_optimum_c if storage else profile.field_optimum_c
    sigma = profile.storage_sigma_c if storage else profile.field_sigma_c
    rh_threshold = profile.storage_rh_threshold_pct if storage else FIELD_RH_THRESHOLD_PCT
    humidity_factor = 1.0 / (1.0 + math.exp(-(rh - rh_threshold) / 2.5))
    wetness_factor = 1.0 / (1.0 + math.exp((vpd - 0.35) / 0.12))
    temperature_suitability = math.exp(-(((t - optimum) / sigma) ** 2))
    risk = float(np.clip(
        100.0 * max(humidity_factor, wetness_factor) * temperature_suitability * STAGE_SUSCEPTIBILITY[params.crop_stage],
        0.0, 99.0,
    ))
    level = _risk_level(risk)

    recommendations: list[str] = []
    if level in (RiskLevel.HIGH, RiskLevel.SEVERE):
        recommendations.append(
            f"High {pathogen.split(' (')[0].lower()} pressure: apply a DAE-registered protectant fungicide "
            "per label before the next wet spell and repeat after 7 days if conditions persist."
            if not storage
            else f"High {pathogen.split(' (')[0].lower()} pressure in storage: sort out damaged produce and increase ventilation."
        )
    if status is VpdStatus.TOO_LOW:
        recommendations.append("Leaf/tuber surfaces stay wet: avoid evening irrigation and improve air movement between rows or stacks.")
    elif status in (VpdStatus.ELEVATED, VpdStatus.SEVERE):
        recommendations.append(
            "Transpiration stress: irrigate in the early morning"
            + (" and re-flood Boro to 3-5 cm (AWD)" if params.crop is Crop.BORO_RICE else " and mulch to conserve soil moisture")
            + "."
        )
    if storage and params.crop is Crop.BORO_RICE:
        recommendations.append("Dry paddy to <= 14% moisture and store on raised pallets in hermetic bags.")
    elif storage:
        recommendations.append("Hold 9-10 deg C and 92-95% RH; ventilate 30 min every 6 h to purge CO2 and avoid condensation.")
    if not recommendations:
        recommendations.append("Conditions are within the optimal band; continue routine scouting twice a week.")

    return ComputeCropVpdStressOutput(
        crop=params.crop,
        crop_stage=params.crop_stage,
        temp_c=t,
        rh_pct=rh,
        saturation_vapor_pressure_kpa=round(svp, 3),
        actual_vapor_pressure_kpa=round(avp, 3),
        vpd_kpa=round(vpd, 3),
        dew_point_c=round(dew_point, 2),
        optimal_vpd_band_kpa=(round(low, 2), round(high, 2)),
        vpd_status=status,
        transpiration_stress_index=round(stress, 3),
        pathogen=pathogen,
        fungal_risk_pct=round(risk, 2),
        fungal_risk_level=level,
        recommendations=recommendations,
    )


if __name__ == "__main__":
    asyncio.run(run_stdio(standalone_dispatcher(server)))
