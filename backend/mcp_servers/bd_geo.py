"""Bangladesh geography shared by the KrishiNexus MCP servers.

District/market and upazila centroids (WGS84), name resolution with common
spelling variants (Bogra/Bogura, Jashore/Jessore, Kawran/Karwan Bazar), and a
road-distance model: great-circle distance x 1.32 circuity factor for the
Bangladeshi national/regional highway network, plus the major river-bridge
crossings a 5-ton truck pays tolls on.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from mcp_servers.base import ToolExecutionError

ROAD_CIRCUITY_FACTOR = 1.32
EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True, slots=True)
class District:
    name: str
    division: str
    lat: float
    lon: float
    aliases: tuple[str, ...] = field(default=())

    @property
    def zone(self) -> str:
        """Road-network zone separated by the Jamuna and Padma rivers."""
        if self.division in {"Rajshahi", "Rangpur"}:
            return "NORTHWEST"
        if self.division in {"Khulna", "Barishal"}:
            return "SOUTHWEST"
        return "EAST"


@dataclass(frozen=True, slots=True)
class Upazila:
    name: str
    district: str
    lat: float
    lon: float


@dataclass(frozen=True, slots=True)
class BridgeCrossing:
    name: str
    toll_tk_medium_truck: float


DISTRICTS: tuple[District, ...] = (
    District("Dhaka Karwan Bazar", "Dhaka", 23.7509, 90.3935, ("dhaka", "karwan bazar", "kawran bazar", "kawran bazaar", "karwan bazaar", "tejgaon")),
    District("Dhaka Mirpur", "Dhaka", 23.8223, 90.3654, ("mirpur", "dhaka mirpur 1", "mirpur 1")),
    District("Munshiganj", "Dhaka", 23.5422, 90.5305, ("munshigonj", "bikrampur")),
    District("Kishoreganj", "Dhaka", 24.4449, 90.7766, ("kishorganj",)),
    District("Netrokona", "Mymensingh", 24.8709, 90.7279, ("netrakona",)),
    District("Sunamganj", "Sylhet", 25.0658, 91.3950, ("sunamgonj",)),
    District("Sylhet", "Sylhet", 24.8949, 91.8687, ("sylhet bandar bazar",)),
    District("Bogura", "Rajshahi", 24.8466, 89.3776, ("bogra",)),
    District("Rangpur", "Rangpur", 25.7439, 89.2752, ()),
    District("Thakurgaon", "Rangpur", 26.0337, 88.4617, ("thakurgaon sadar",)),
    District("Kurigram", "Rangpur", 25.8054, 89.6362, ()),
    District("Jessore", "Khulna", 23.1664, 89.2081, ("jashore", "jessore sadar")),
    District("Cox's Bazar", "Chattogram", 21.4272, 92.0058, ("coxs bazar", "cox bazar", "coxsbazar")),
)

UPAZILAS: tuple[Upazila, ...] = (
    # Bogura
    Upazila("Bogura Sadar", "Bogura", 24.8466, 89.3776),
    Upazila("Shibganj", "Bogura", 25.0167, 89.3167),
    Upazila("Sherpur", "Bogura", 24.6667, 89.4167),
    Upazila("Kahaloo", "Bogura", 24.8333, 89.2667),
    Upazila("Gabtali", "Bogura", 24.8833, 89.4500),
    Upazila("Sariakandi", "Bogura", 24.8833, 89.5667),
    Upazila("Shajahanpur", "Bogura", 24.7833, 89.3833),
    # Rangpur
    Upazila("Rangpur Sadar", "Rangpur", 25.7439, 89.2752),
    Upazila("Mithapukur", "Rangpur", 25.5667, 89.2833),
    Upazila("Badarganj", "Rangpur", 25.6745, 89.0533),
    Upazila("Kaunia", "Rangpur", 25.7833, 89.4167),
    # Munshiganj
    Upazila("Munshiganj Sadar", "Munshiganj", 23.5422, 90.5305),
    Upazila("Tongibari", "Munshiganj", 23.5000, 90.4667),
    Upazila("Sirajdikhan", "Munshiganj", 23.5833, 90.3833),
    Upazila("Sreenagar", "Munshiganj", 23.5333, 90.2833),
    Upazila("Lohajang", "Munshiganj", 23.4667, 90.3500),
    Upazila("Gazaria", "Munshiganj", 23.5500, 90.6167),
    # Jessore
    Upazila("Jessore Sadar", "Jessore", 23.1664, 89.2081),
    Upazila("Jhikargacha", "Jessore", 23.1000, 89.1000),
    Upazila("Chaugachha", "Jessore", 23.2667, 89.0167),
    Upazila("Manirampur", "Jessore", 23.0167, 89.2333),
    Upazila("Bagherpara", "Jessore", 23.2167, 89.3500),
    # Sylhet
    Upazila("Sylhet Sadar", "Sylhet", 24.8949, 91.8687),
    Upazila("Companiganj", "Sylhet", 25.0667, 91.7500),
    Upazila("Golapganj", "Sylhet", 24.8500, 92.0167),
    # Sunamganj (haor)
    Upazila("Sunamganj Sadar", "Sunamganj", 25.0658, 91.3950),
    Upazila("Tahirpur", "Sunamganj", 25.1167, 91.1750),
    Upazila("Dharmapasha", "Sunamganj", 24.9083, 91.0083),
    Upazila("Jamalganj", "Sunamganj", 24.9667, 91.2333),
    Upazila("Derai", "Sunamganj", 24.8000, 91.3500),
    Upazila("Shalla", "Sunamganj", 24.7000, 91.2667),
    # Kishoreganj (haor)
    Upazila("Kishoreganj Sadar", "Kishoreganj", 24.4449, 90.7766),
    Upazila("Itna", "Kishoreganj", 24.5333, 91.0833),
    Upazila("Mithamain", "Kishoreganj", 24.4333, 91.0333),
    Upazila("Austagram", "Kishoreganj", 24.2667, 91.1000),
    Upazila("Nikli", "Kishoreganj", 24.3167, 90.9333),
    # Netrokona (haor)
    Upazila("Netrokona Sadar", "Netrokona", 24.8709, 90.7279),
    Upazila("Khaliajuri", "Netrokona", 24.7000, 91.1167),
    Upazila("Mohanganj", "Netrokona", 24.8667, 90.9667),
    Upazila("Madan", "Netrokona", 24.7167, 90.9500),
    # Thakurgaon
    Upazila("Ranisankail", "Thakurgaon", 25.9333, 88.2333),
    Upazila("Baliadangi", "Thakurgaon", 26.1000, 88.2833),
    Upazila("Haripur", "Thakurgaon", 25.8667, 88.1500),
    # Kurigram
    Upazila("Kurigram Sadar", "Kurigram", 25.8054, 89.6362),
    Upazila("Ulipur", "Kurigram", 25.6667, 89.6333),
    Upazila("Chilmari", "Kurigram", 25.5667, 89.6833),
    Upazila("Nageshwari", "Kurigram", 25.9667, 89.7000),
    Upazila("Bhurungamari", "Kurigram", 26.1167, 89.6667),
    Upazila("Rajarhat", "Kurigram", 25.8000, 89.5333),
    Upazila("Rowmari", "Kurigram", 25.5667, 89.8500),
    # Cox's Bazar
    Upazila("Cox's Bazar Sadar", "Cox's Bazar", 21.4272, 92.0058),
    Upazila("Ukhia", "Cox's Bazar", 21.2833, 92.1000),
    Upazila("Teknaf", "Cox's Bazar", 20.8624, 92.3058),
    Upazila("Ramu", "Cox's Bazar", 21.4333, 92.1000),
    Upazila("Chakaria", "Cox's Bazar", 21.7667, 92.0667),
    Upazila("Pekua", "Cox's Bazar", 21.8167, 91.9667),
    Upazila("Maheshkhali", "Cox's Bazar", 21.5500, 91.9333),
)

# 2025 toll schedule, medium truck (5-ton class).
JAMUNA_BRIDGE = BridgeCrossing("Bangabandhu (Jamuna) Bridge", 1_800.0)
PADMA_BRIDGE = BridgeCrossing("Padma Multipurpose Bridge", 2_800.0)
LALON_SHAH_BRIDGE = BridgeCrossing("Lalon Shah (Paksey) Bridge", 480.0)


def normalize_place(value: str) -> str:
    cleaned = re.sub(r"['’`.]", "", value.strip().lower())
    cleaned = re.sub(r"[\s_\-/,]+", " ", cleaned).strip()
    return re.sub(r"\s+(district|zila|upazila|thana)$", "", cleaned)


_DISTRICT_INDEX: dict[str, District] = {}
for _district in DISTRICTS:
    _DISTRICT_INDEX[normalize_place(_district.name)] = _district
    for _alias in _district.aliases:
        _DISTRICT_INDEX[normalize_place(_alias)] = _district

_UPAZILA_INDEX: dict[str, Upazila] = {normalize_place(u.name): u for u in UPAZILAS}

_DISTRICT_BY_NAME: dict[str, District] = {d.name: d for d in DISTRICTS}


def resolve_district(name: str) -> District:
    """Resolve a district or market-node name (case/spelling tolerant)."""
    key = normalize_place(name)
    district = _DISTRICT_INDEX.get(key) or _DISTRICT_INDEX.get(key.removesuffix(" sadar"))
    if district is None:
        known = ", ".join(d.name for d in DISTRICTS)
        raise ToolExecutionError(f"Unknown district or market '{name}'. Supported: {known}.")
    return district


def district_by_name(name: str) -> District:
    return _DISTRICT_BY_NAME[name]


def resolve_upazila(name: str) -> Upazila:
    """Resolve an upazila; a bare district name maps to that district's Sadar upazila."""
    key = normalize_place(name)
    upazila = _UPAZILA_INDEX.get(key)
    if upazila is not None:
        return upazila
    district = _DISTRICT_INDEX.get(key) or _DISTRICT_INDEX.get(key.removesuffix(" sadar"))
    if district is not None:
        return Upazila(f"{district.name} Sadar", district.name, district.lat, district.lon)
    known = ", ".join(u.name for u in UPAZILAS)
    raise ToolExecutionError(f"Unknown upazila '{name}'. Supported: {known}.")


def upazilas_in(district_name: str) -> list[Upazila]:
    return [u for u in UPAZILAS if u.district == district_name]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def road_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return haversine_km(lat1, lon1, lat2, lon2) * ROAD_CIRCUITY_FACTOR


def bridge_crossings(origin: District, destination: District) -> list[BridgeCrossing]:
    zones = {origin.zone, destination.zone}
    if len(zones) == 1:
        return []
    if zones == {"NORTHWEST", "EAST"}:
        return [JAMUNA_BRIDGE]
    if zones == {"SOUTHWEST", "EAST"}:
        return [PADMA_BRIDGE]
    return [LALON_SHAH_BRIDGE]


def nearest_district(lat: float, lon: float) -> District:
    return min(DISTRICTS, key=lambda d: haversine_km(lat, lon, d.lat, d.lon))
