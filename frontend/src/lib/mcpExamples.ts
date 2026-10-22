/** Pre-populated, valid arguments for each of the 13 MCP tools (used by the inspector). */

const today = new Date();
const isoDate = (offsetDays: number) => new Date(today.getTime() + offsetDays * 86_400_000).toISOString().slice(0, 10);

export const MCP_EXAMPLE_ARGS: Record<string, Record<string, unknown>> = {
  get_daily_commodity_spread: { crop: "Green Chili", district: "Bogura" },
  detect_syndicate_markup_anomaly: { crop: "Green Chili", upazila: "Bogura", retail_hub: "Dhaka Karwan Bazar" },
  find_optimal_selling_hub: { crop: "Cardinal Potato", weight_kg: 5000, origin_district: "Bogura", grade: "A" },
  get_historical_seasonal_curve: { crop: "Cardinal Potato", month_range: [2, 3, 8, 9] },
  get_current_weather: { latitude: 25.0658, longitude: 91.395 },
  get_weather_by_datetime_range: { latitude: 24.8466, longitude: 89.3776, start_date: isoDate(0), end_date: isoDate(2) },
  calculate_haor_flash_flood_risk: { upazila: "Tahirpur", sar_water_backscatter_db: -19.5 },
  compute_crop_vpd_stress: { crop: "Cardinal Potato", crop_stage: "vegetative", temp_c: 16, rh_pct: 94 },
  trigger_early_harvest_window: { cluster_id: "SUN-TAH-07", upazila: "Tahirpur", urgency_level: "CRITICAL" },
  query_cold_storage_quota: { district: "Munshiganj", radius_km: 60, tons_needed: 250 },
  get_chamber_telemetry: { facility_id: "BCSA-MUN-01", chamber_id: "CH-03" },
  calculate_dynamic_shelf_life: { crop: "Green Chili", grade: "A", transit_temp_c: 30, rh_pct: 60 },
  reserve_collective_storage_slot: { cluster_id: "MUN-TNG-03", facility_id: "BCSA-MUN-02", tons: 40, farmer_count: 120 },
};
