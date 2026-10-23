/**
 * Geography for the story landscape. Places and cold stores use the backend's coordinates
 * (`mcp_servers/bd_geo.py`, `coldchain_iot_mcp._FACILITY_SEED`); rivers, the coast and haor basins are
 * stylised tracings in roughly the right place. One world unit is 10 km.
 */

export interface LatLon {
  lat: number;
  lon: number;
}

const ORIGIN: LatLon = { lat: 24.3, lon: 90.0 };
const KM_PER_DEG_LAT = 110.95;
const KM_PER_DEG_LON = 111.32 * Math.cos((ORIGIN.lat * Math.PI) / 180);
export const UNIT_KM = 10;

/** Equirectangular projection around central Bangladesh: x east, z south. */
export function project(p: LatLon): { x: number; z: number } {
  return {
    x: ((p.lon - ORIGIN.lon) * KM_PER_DEG_LON) / UNIT_KM,
    z: (-(p.lat - ORIGIN.lat) * KM_PER_DEG_LAT) / UNIT_KM,
  };
}

export function unproject(x: number, z: number): LatLon {
  return { lat: ORIGIN.lat - (z * UNIT_KM) / KM_PER_DEG_LAT, lon: ORIGIN.lon + (x * UNIT_KM) / KM_PER_DEG_LON };
}

export const formatLatLon = (p: LatLon) => `${p.lat.toFixed(2)}°N ${p.lon.toFixed(2)}°E`;

export const PLACES = {
  rahimPlot: { lat: 25.588, lon: 89.258 },
  mithapukur: { lat: 25.5667, lon: 89.2833 },
  rangpur: { lat: 25.7439, lon: 89.2752 },
  bogura: { lat: 24.8466, lon: 89.3776 },
  sariakandi: { lat: 24.8833, lon: 89.5667 },
  jamunaBridge: { lat: 24.396, lon: 89.787 },
  karwanBazar: { lat: 23.7509, lon: 90.3935 },
  tejgaon: { lat: 23.762, lon: 90.425 },
  mirpur: { lat: 23.8223, lon: 90.3654 },
  munshiganj: { lat: 23.5422, lon: 90.5305 },
  tongibari: { lat: 23.5, lon: 90.4667 },
  jhikargacha: { lat: 23.1, lon: 89.1 },
  thakurgaon: { lat: 26.0337, lon: 88.4617 },
  sunamganj: { lat: 25.0658, lon: 91.395 },
  tahirpur: { lat: 25.1167, lon: 91.175 },
  abdulFields: { lat: 25.098, lon: 91.142 },
  tanguarHaor: { lat: 25.14, lon: 91.07 },
} satisfies Record<string, LatLon>;

/** Approximate N5/N4 highway: Mithapukur, Pirganj, Gobindaganj, Bogura, Sherpur, Jamuna bridge, Tangail, Dhaka. */
export const ROUTE_TO_DHAKA: LatLon[] = [
  PLACES.mithapukur,
  { lat: 25.36, lon: 89.32 },
  { lat: 25.13, lon: 89.38 },
  PLACES.bogura,
  { lat: 24.64, lon: 89.42 },
  { lat: 24.43, lon: 89.6 },
  PLACES.jamunaBridge,
  { lat: 24.25, lon: 89.92 },
  { lat: 24.03, lon: 90.24 },
  { lat: 23.86, lon: 90.33 },
  PLACES.karwanBazar,
];

/** Where each trader adds their margin, as a fraction along the route (Dhaka tiers sit off the road). */
export const TIER_STOPS: { tier: string; at: number | LatLon }[] = [
  { tier: "Faria", at: 0.04 },
  { tier: "Bepari", at: 0.34 },
  { tier: "Aratdar", at: 1 },
  { tier: "Paiker", at: PLACES.tejgaon },
  { tier: "Retailer", at: PLACES.mirpur },
];

export interface River {
  name: string;
  width: number;
  points: LatLon[];
}

export const RIVERS: River[] = [
  { name: "Teesta", width: 0.14, points: [{ lat: 26.25, lon: 88.95 }, { lat: 26.05, lon: 89.15 }, { lat: 25.85, lon: 89.35 }, { lat: 25.75, lon: 89.48 }, { lat: 25.6, lon: 89.66 }] },
  { name: "Jamuna", width: 0.42, points: [{ lat: 26.25, lon: 89.76 }, { lat: 25.8, lon: 89.69 }, { lat: 25.56, lon: 89.69 }, { lat: 25.2, lon: 89.71 }, { lat: 24.9, lon: 89.73 }, { lat: 24.4, lon: 89.77 }, { lat: 24.0, lon: 89.76 }, { lat: 23.82, lon: 89.75 }] },
  { name: "Padma", width: 0.36, points: [{ lat: 24.42, lon: 88.2 }, { lat: 24.3, lon: 88.6 }, { lat: 24.1, lon: 89.0 }, { lat: 23.92, lon: 89.45 }, { lat: 23.82, lon: 89.75 }, { lat: 23.62, lon: 90.1 }, { lat: 23.45, lon: 90.4 }, { lat: 23.25, lon: 90.6 }] },
  { name: "Lower Meghna", width: 0.55, points: [{ lat: 23.25, lon: 90.6 }, { lat: 22.9, lon: 90.66 }, { lat: 22.5, lon: 90.76 }, { lat: 22.05, lon: 90.86 }] },
  { name: "Meghna", width: 0.18, points: [{ lat: 24.92, lon: 91.0 }, { lat: 24.5, lon: 90.96 }, { lat: 24.05, lon: 90.97 }, { lat: 23.7, lon: 90.75 }, { lat: 23.25, lon: 90.6 }] },
  { name: "Surma", width: 0.1, points: [{ lat: 25.0, lon: 92.05 }, { lat: 24.9, lon: 91.86 }, { lat: 25.05, lon: 91.44 }, { lat: 24.96, lon: 91.2 }, { lat: 24.6, lon: 91.03 }, { lat: 24.4, lon: 90.98 }] },
  { name: "Old Brahmaputra", width: 0.08, points: [{ lat: 25.22, lon: 89.93 }, { lat: 24.76, lon: 90.4 }, { lat: 24.4, lon: 90.76 }, { lat: 24.05, lon: 90.97 }] },
];

/** Haor basins around Tahirpur: centre and radius in km (stylised). */
export const HAOR_BASINS: { name: string; at: LatLon; radiusKm: number }[] = [
  { name: "Tanguar haor", at: PLACES.tanguarHaor, radiusKm: 9 },
  { name: "Matian haor", at: { lat: 25.08, lon: 91.22 }, radiusKm: 5 },
  { name: "Shanir haor", at: { lat: 25.02, lon: 91.12 }, radiusKm: 4.5 },
  { name: "Dekar haor", at: { lat: 24.98, lon: 91.42 }, radiusKm: 6 },
  { name: "Karchar haor", at: { lat: 25.05, lon: 90.95 }, radiusKm: 5 },
  { name: "Hail haor", at: { lat: 24.63, lon: 91.45 }, radiusKm: 4 },
];

/** Coast of the Bay of Bengal, as a latitude (stylised). */
export const COAST_LAT = 22.3;

export interface FacilitySeed {
  id: string;
  name: string;
  district: "Munshiganj" | "Rangpur" | "Bogura" | "Thakurgaon";
  at: LatLon;
  capacityMt: number;
}

export const FACILITIES: FacilitySeed[] = [
  { id: "BCSA-MUN-01", name: "Mirkadim Riverside Himagar Ltd.", district: "Munshiganj", at: { lat: 23.5545, lon: 90.515 }, capacityMt: 12000 },
  { id: "BCSA-MUN-02", name: "Tongibari Krishi Himagar", district: "Munshiganj", at: { lat: 23.501, lon: 90.469 }, capacityMt: 9500 },
  { id: "BCSA-MUN-03", name: "Sirajdikhan Cold Storage Ltd.", district: "Munshiganj", at: { lat: 23.584, lon: 90.385 }, capacityMt: 11000 },
  { id: "BCSA-MUN-04", name: "Sreenagar Agro Cold Storage", district: "Munshiganj", at: { lat: 23.532, lon: 90.286 }, capacityMt: 8500 },
  { id: "BCSA-MUN-05", name: "Lohajang Padma Himagar", district: "Munshiganj", at: { lat: 23.468, lon: 90.348 }, capacityMt: 7800 },
  { id: "BCSA-RAN-01", name: "Rangpur Uttara Himagar Ltd.", district: "Rangpur", at: { lat: 25.752, lon: 89.26 }, capacityMt: 10500 },
  { id: "BCSA-RAN-02", name: "Mithapukur Cold Storage", district: "Rangpur", at: { lat: 25.569, lon: 89.285 }, capacityMt: 9000 },
  { id: "BCSA-RAN-03", name: "Badarganj Agro Himagar", district: "Rangpur", at: { lat: 25.676, lon: 89.056 }, capacityMt: 8200 },
  { id: "BCSA-RAN-04", name: "Kaunia Teesta Cold Storage", district: "Rangpur", at: { lat: 25.785, lon: 89.415 }, capacityMt: 7500 },
  { id: "BCSA-BOG-01", name: "Shibganj Mahasthan Himagar", district: "Bogura", at: { lat: 25.015, lon: 89.32 }, capacityMt: 11500 },
  { id: "BCSA-BOG-02", name: "Sherpur Krishi Cold Storage", district: "Bogura", at: { lat: 24.669, lon: 89.415 }, capacityMt: 9800 },
  { id: "BCSA-BOG-03", name: "Kahaloo Agro Himagar", district: "Bogura", at: { lat: 24.835, lon: 89.269 }, capacityMt: 8700 },
  { id: "BCSA-BOG-04", name: "Gabtali Cold Storage Ltd.", district: "Bogura", at: { lat: 24.882, lon: 89.448 }, capacityMt: 7900 },
  { id: "BCSA-BOG-05", name: "Shajahanpur Himagar", district: "Bogura", at: { lat: 24.785, lon: 89.385 }, capacityMt: 10200 },
  { id: "BCSA-THA-01", name: "Thakurgaon Sadar Himagar", district: "Thakurgaon", at: { lat: 26.035, lon: 88.464 }, capacityMt: 9600 },
  { id: "BCSA-THA-02", name: "Ranisankail Cold Storage", district: "Thakurgaon", at: { lat: 25.934, lon: 88.235 }, capacityMt: 7400 },
  { id: "BCSA-THA-03", name: "Baliadangi Agro Himagar", district: "Thakurgaon", at: { lat: 26.101, lon: 88.285 }, capacityMt: 6800 },
  { id: "BCSA-THA-04", name: "Haripur Krishi Himagar", district: "Thakurgaon", at: { lat: 25.868, lon: 88.152 }, capacityMt: 6200 },
];

/** BCSA quota capture used by `coldchain-iot-mcp` (traders 45%, owners 32.32%, farmers 22.68%). */
export const QUOTA_SHARES = { traders: 0.45, owners: 0.3232, farmers: 0.2268 };

export const DISTRICT_LABELS: { name: string; at: LatLon }[] = [
  { name: "Rangpur", at: PLACES.rangpur },
  { name: "Thakurgaon", at: PLACES.thakurgaon },
  { name: "Bogura", at: PLACES.bogura },
  { name: "Dhaka", at: PLACES.karwanBazar },
  { name: "Munshiganj", at: PLACES.munshiganj },
  { name: "Sunamganj", at: PLACES.sunamganj },
];
