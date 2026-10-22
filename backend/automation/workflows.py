"""Durable workflow automation.

``TemporalTruckPoolManager`` runs one Temporal-style workflow per 5-ton (5,000 kg) union truck pool.
Every state change is appended to the pool's event history (PoolOpened, LotAdded, LotRejected,
CapacityReached, TruckDispatched, EscrowLocked, TimerFired) and the whole state is persisted
atomically to ``backend/.state/truck_pools.json`` after each transition, so pools survive restarts
and replays are idempotent per farmer. A durable timer auto-dispatches a pool that is at least
80% full when its dispatch deadline passes.

``N8nWebhookHandlers`` implement the two n8n-triggered jobs (6:00 AM daily DAM price sync into the
retrieval index, hourly Sentinel-1 haor flood polling with outbound Bangla voice alerts) and export
importable n8n workflow definitions that call them.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import threading
from datetime import date, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from config import now_bdt
from mcp_servers import bd_geo
from mcp_servers.base import ToolExecutionError, stable_unit
from mcp_servers.dam_market_mcp import TRUCK_CAPACITY_KG, find_optimal_selling_hub
from schemas.mcp_models import Crop, CropField, FindOptimalSellingHubInput, Grade

STATE_DIR = Path(__file__).resolve().parent.parent / ".state"
POOL_STATE_FILE = STATE_DIR / "truck_pools.json"
UNION_RADIUS_KM = 5.0
DISPATCH_DEADLINE_HOURS = 8
AUTO_DISPATCH_MIN_FILL = 0.80

_GRADE_ALIASES = {"A": Grade.A, "GRADE-A": Grade.A, "GRADE A": Grade.A, "B": Grade.B, "GRADE-B": Grade.B,
                  "GRADE B": Grade.B, "C": Grade.C, "GRADE-C": Grade.C, "GRADE C": Grade.C}


def parse_grade(value: str) -> Grade:
    key = value.strip().upper().split(" EXPORT")[0].split(" WHOLESALE")[0].split(" PROCESSING")[0].strip()
    if key not in _GRADE_ALIASES:
        raise ValueError(f"unknown grade '{value}'; use Grade-A, Grade-B or Grade-C")
    return _GRADE_ALIASES[key]


class PoolStatus(StrEnum):
    OPEN = "OPEN"
    DISPATCHED = "DISPATCHED"


class PoolLot(BaseModel):
    farmer_id: str
    weight_kg: float
    grade: Grade
    distance_km: float
    joined_at: datetime
    source: Literal["seed", "farmer"]


class WorkflowEvent(BaseModel):
    seq: int
    event_type: str
    at: datetime
    data: dict[str, Any] = Field(default_factory=dict)


class Dispatch(BaseModel):
    truck_booking_id: str
    buyer_hub_id: str
    buyer_name: str
    buyer_type: str
    road_distance_km: float
    eta_hours: float
    contract_price_tk_per_kg: float
    contract_value_tk: float
    escrow_id: str
    escrow_amount_tk: float
    escrow_status: Literal["LOCKED"]
    dispatched_at: datetime
    trigger: Literal["CAPACITY_REACHED", "DEADLINE_TIMER"]


class TruckPool(BaseModel):
    pool_id: str
    workflow_id: str
    district: str
    upazila: str
    union: str
    crop: Crop
    capacity_kg: float = TRUCK_CAPACITY_KG
    roster_size: int
    status: PoolStatus = PoolStatus.OPEN
    created_at: datetime
    dispatch_deadline: datetime
    lots: list[PoolLot] = Field(default_factory=list)
    events: list[WorkflowEvent] = Field(default_factory=list)
    dispatch: Dispatch | None = None

    @property
    def loaded_kg(self) -> float:
        return round(sum(lot.weight_kg for lot in self.lots), 1)

    def record(self, event_type: str, **data: Any) -> None:
        self.events.append(WorkflowEvent(seq=len(self.events) + 1, event_type=event_type, at=now_bdt(), data=data))


class PoolView(BaseModel):
    pool_id: str
    workflow_id: str
    district: str
    upazila: str
    union: str
    crop: Crop
    status: PoolStatus
    capacity_kg: float
    loaded_kg: float
    remaining_kg: float
    fill_pct: float
    smallholders: int
    roster_size: int
    union_radius_km: float
    dispatch_deadline: datetime
    dispatch: Dispatch | None
    lots: list[PoolLot]
    recent_events: list[WorkflowEvent]


class JoinPoolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    cluster_id: str = Field(pattern=r"^[A-Za-z0-9\-]{3,40}$", description="Pool id, e.g. POOL-BOGURA-01.")
    farmer_id: str = Field(pattern=r"^[A-Za-z0-9\-]{3,40}$")
    crop: CropField
    weight_kg: float = Field(gt=0, le=TRUCK_CAPACITY_KG)
    grade: Grade

    @field_validator("grade", mode="before")
    @classmethod
    def _grade(cls, value: Any) -> Any:
        return parse_grade(value) if isinstance(value, str) else value


class JoinPoolResult(BaseModel):
    accepted: bool
    idempotent_replay: bool
    accepted_kg: float
    overflow_kg: float
    overflow_pool_id: str | None
    message: str
    pool: PoolView


# Seed: (pool_id, district, upazila, union, crop, lot sizes in kg)
_SEED_POOLS: tuple[tuple[str, str, str, str, Crop, tuple[int, ...]], ...] = (
    ("POOL-BOGURA-01", "Bogura", "Shibganj", "Mokamtala Union", Crop.CARDINAL_POTATO,
     (500, 450, 400, 350, 600, 300, 400, 450, 350, 500, 300)),
    ("POOL-RANGPUR-01", "Rangpur", "Mithapukur", "Ranipukur Union", Crop.CARDINAL_POTATO, (400, 450, 350, 500, 300, 400, 350, 400)),
    ("POOL-MUNSHIGANJ-01", "Munshiganj", "Tongibari", "Dighirpar Union", Crop.DIAMANT_POTATO, (400, 400, 450, 350, 400, 400, 400)),
    ("POOL-JESSORE-01", "Jessore", "Jhikargacha", "Gadkhali Union", Crop.BRINJAL, (300, 350, 250, 400, 300, 300)),
    ("POOL-BOGURA-02", "Bogura", "Sariakandi", "Kutubpur Union", Crop.GREEN_CHILI, (250, 300, 200, 250, 250)),
)


def farmer_distance_km(farmer_id: str, district: str) -> float:
    """Registered farmers of the district (id prefix FARM-<DIS>) live inside the union radius."""
    local = farmer_id.upper().startswith(f"FARM-{district[:3].upper()}")
    return round(stable_unit("farmer-distance", farmer_id) * (4.9 if local else 9.0), 2)


class TemporalTruckPoolManager:
    def __init__(self, state_file: Path = POOL_STATE_FILE) -> None:
        self.state_file = state_file
        self._lock = threading.Lock()
        self._async_lock = asyncio.Lock()
        self.pools: dict[str, TruckPool] = {}
        if state_file.exists():
            raw = json.loads(state_file.read_text(encoding="utf-8"))
            self.pools = {p["pool_id"]: TruckPool.model_validate(p) for p in raw["pools"]}
        else:
            self.reset()

    # -- persistence -------------------------------------------------------

    def _persist(self) -> None:
        with self._lock:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            tmp = self.state_file.with_suffix(".tmp")
            payload = {"saved_at": now_bdt().isoformat(), "pools": [p.model_dump(mode="json") for p in self.pools.values()]}
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self.state_file)

    def _open_pool(self, pool_id: str, district: str, upazila: str, union: str, crop: Crop) -> TruckPool:
        now = now_bdt()
        pool = TruckPool(
            pool_id=pool_id, workflow_id=f"wf-truckpool-{pool_id.lower()}", district=district, upazila=upazila,
            union=union, crop=crop, roster_size=30 + int(stable_unit("roster", upazila) * 21), created_at=now,
            dispatch_deadline=now + timedelta(hours=DISPATCH_DEADLINE_HOURS),
        )
        pool.record("PoolOpened", district=district, upazila=upazila, crop=crop.value, capacity_kg=pool.capacity_kg)
        self.pools[pool_id] = pool
        return pool

    def reset(self) -> list[PoolView]:
        self.pools = {}
        for pool_id, district, upazila, union, crop, lots in _SEED_POOLS:
            pool = self._open_pool(pool_id, district, upazila, union, crop)
            code = district[:3].upper()
            for n, kg in enumerate(lots, start=1):
                farmer = f"FARM-{code}-{n:03d}"
                pool.lots.append(PoolLot(farmer_id=farmer, weight_kg=kg, grade=Grade.A if n % 4 else Grade.B,
                                         distance_km=farmer_distance_km(farmer, district), joined_at=pool.created_at,
                                         source="seed"))
                pool.record("LotAdded", farmer_id=farmer, weight_kg=kg, loaded_kg=pool.loaded_kg)
        self._persist()
        return [self.view(p) for p in self.pools.values()]

    # -- queries -----------------------------------------------------------

    def view(self, pool: TruckPool) -> PoolView:
        return PoolView(
            pool_id=pool.pool_id, workflow_id=pool.workflow_id, district=pool.district, upazila=pool.upazila,
            union=pool.union, crop=pool.crop, status=pool.status, capacity_kg=pool.capacity_kg, loaded_kg=pool.loaded_kg,
            remaining_kg=round(pool.capacity_kg - pool.loaded_kg, 1),
            fill_pct=round(pool.loaded_kg / pool.capacity_kg * 100, 1), smallholders=len(pool.lots),
            roster_size=pool.roster_size, union_radius_km=UNION_RADIUS_KM, dispatch_deadline=pool.dispatch_deadline,
            dispatch=pool.dispatch, lots=pool.lots, recent_events=pool.events[-6:],
        )

    async def list_pools(self) -> list[PoolView]:
        await self.fire_timers()
        return [self.view(p) for p in self.pools.values()]

    def open_pool_for(self, district: str, upazila: str, crop: Crop) -> TruckPool | None:
        candidates = [p for p in self.pools.values()
                      if p.status is PoolStatus.OPEN and p.crop is crop and p.district == district]
        same_upazila = [p for p in candidates if p.upazila == upazila]
        return (same_upazila or candidates or [None])[0]

    # -- workflow transitions ---------------------------------------------

    async def _dispatch(self, pool: TruckPool, trigger: Literal["CAPACITY_REACHED", "DEADLINE_TIMER"]) -> None:
        grades = [lot.grade for lot in pool.lots]
        pool_grade = max(set(grades), key=grades.count)
        offer = await find_optimal_selling_hub(FindOptimalSellingHubInput(
            crop=pool.crop, weight_kg=pool.loaded_kg, origin_district=pool.district, grade=pool_grade))
        best = offer.best_option
        if best is None:
            pool.record("DispatchFailed", reason="no buyer accepts this crop/grade")
            return
        now = now_bdt()
        digest = hashlib.sha256(f"{pool.workflow_id}|{now.isoformat()}|{best.hub_id}".encode()).hexdigest()
        contract_value = round(best.net_payout_tk_per_kg * pool.loaded_kg, 2)
        pool.dispatch = Dispatch(
            truck_booking_id=f"TRK-{pool.district[:3].upper()}-{digest[:8].upper()}", buyer_hub_id=best.hub_id,
            buyer_name=best.hub_name, buyer_type=best.hub_type.value, road_distance_km=best.road_distance_km,
            eta_hours=best.transit_hours, contract_price_tk_per_kg=best.net_payout_tk_per_kg,
            contract_value_tk=contract_value, escrow_id=f"ESC-{digest[8:20].upper()}", escrow_amount_tk=contract_value,
            escrow_status="LOCKED", dispatched_at=now, trigger=trigger,
        )
        pool.status = PoolStatus.DISPATCHED
        pool.record("TruckDispatched", truck_booking_id=pool.dispatch.truck_booking_id, buyer=best.hub_name,
                    loaded_kg=pool.loaded_kg, trigger=trigger)
        pool.record("EscrowLocked", escrow_id=pool.dispatch.escrow_id, amount_tk=contract_value,
                    per_farmer={lot.farmer_id: round(lot.weight_kg * best.net_payout_tk_per_kg, 2) for lot in pool.lots})

    async def fire_timers(self) -> None:
        async with self._async_lock:
            now = now_bdt()
            fired = False
            for pool in self.pools.values():
                if pool.status is PoolStatus.OPEN and now >= pool.dispatch_deadline:
                    fired = True
                    if pool.loaded_kg >= AUTO_DISPATCH_MIN_FILL * pool.capacity_kg:
                        pool.record("TimerFired", action="auto-dispatch", fill_pct=round(pool.loaded_kg / pool.capacity_kg * 100, 1))
                        await self._dispatch(pool, "DEADLINE_TIMER")
                    else:
                        pool.dispatch_deadline = now + timedelta(hours=DISPATCH_DEADLINE_HOURS)
                        pool.record("TimerFired", action="deadline-extended", new_deadline=pool.dispatch_deadline.isoformat())
            if fired:
                self._persist()

    async def join(self, request: JoinPoolRequest) -> JoinPoolResult:
        async with self._async_lock:
            pool = self.pools.get(request.cluster_id.upper())
            if pool is None:
                raise ToolExecutionError(f"Unknown truck pool '{request.cluster_id}'. Open pools: "
                                         f"{', '.join(p.pool_id for p in self.pools.values() if p.status is PoolStatus.OPEN)}.")
            existing = next((lot for lot in pool.lots if lot.farmer_id == request.farmer_id), None)
            if existing is not None:
                return JoinPoolResult(accepted=True, idempotent_replay=True, accepted_kg=existing.weight_kg, overflow_kg=0.0,
                                      overflow_pool_id=None, message=f"{request.farmer_id} already holds {existing.weight_kg:g} kg "
                                      f"in {pool.pool_id}; no change.", pool=self.view(pool))

            def reject(reason: str) -> JoinPoolResult:
                pool.record("LotRejected", farmer_id=request.farmer_id, weight_kg=request.weight_kg, reason=reason)
                self._persist()
                return JoinPoolResult(accepted=False, idempotent_replay=False, accepted_kg=0.0, overflow_kg=0.0,
                                      overflow_pool_id=None, message=reason, pool=self.view(pool))

            if pool.status is not PoolStatus.OPEN:
                return reject(f"{pool.pool_id} already dispatched ({pool.dispatch.truck_booking_id if pool.dispatch else ''}); "
                              "POST /automation/truck-pools/reset to replay the demo.")
            if request.crop is not pool.crop:
                return reject(f"{pool.pool_id} carries {pool.crop.value}, not {request.crop.value}.")
            if request.grade is Grade.C:
                return reject("Grade-C lots go to processors, not pooled B2B trucks.")
            distance = farmer_distance_km(request.farmer_id, pool.district)
            if distance > UNION_RADIUS_KM:
                return reject(f"{request.farmer_id} is {distance:.1f} km from the collection point (limit {UNION_RADIUS_KM:g} km).")

            remaining = pool.capacity_kg - pool.loaded_kg
            accepted = round(min(request.weight_kg, remaining), 1)
            overflow = round(request.weight_kg - accepted, 1)
            pool.lots.append(PoolLot(farmer_id=request.farmer_id, weight_kg=accepted, grade=request.grade,
                                     distance_km=distance, joined_at=now_bdt(), source="farmer"))
            pool.record("LotAdded", farmer_id=request.farmer_id, weight_kg=accepted, loaded_kg=pool.loaded_kg)

            overflow_pool_id = None
            if overflow > 0:
                overflow_pool_id = f"{pool.pool_id}-N{sum(p.pool_id.startswith(pool.pool_id) for p in self.pools.values())}"
                spill = self._open_pool(overflow_pool_id, pool.district, pool.upazila, pool.union, pool.crop)
                spill.lots.append(PoolLot(farmer_id=request.farmer_id, weight_kg=overflow, grade=request.grade,
                                          distance_km=distance, joined_at=now_bdt(), source="farmer"))
                spill.record("LotAdded", farmer_id=request.farmer_id, weight_kg=overflow, loaded_kg=spill.loaded_kg)

            message = f"Added {accepted:g} kg; pool at {pool.loaded_kg:g}/{pool.capacity_kg:g} kg."
            if pool.loaded_kg >= pool.capacity_kg:
                pool.record("CapacityReached", loaded_kg=pool.loaded_kg, smallholders=len(pool.lots))
                await self._dispatch(pool, "CAPACITY_REACHED")
                if pool.dispatch:
                    message += (f" Truck {pool.dispatch.truck_booking_id} dispatched to {pool.dispatch.buyer_name}; "
                                f"escrow {pool.dispatch.escrow_id} locked Tk {pool.dispatch.escrow_amount_tk:,.0f}.")
            if overflow_pool_id:
                message += f" {overflow:g} kg overflow opened {overflow_pool_id}."
            self._persist()
            return JoinPoolResult(accepted=True, idempotent_replay=False, accepted_kg=accepted, overflow_kg=overflow,
                                  overflow_pool_id=overflow_pool_id, message=message, pool=self.view(pool))


TRUCK_POOLS = TemporalTruckPoolManager()


# ---------------------------------------------------------------------------
# n8n cron / webhook jobs
# ---------------------------------------------------------------------------


class DamAnomalyRow(BaseModel):
    district: str
    crop: Crop
    grower_tk_per_kg: float
    wholesale_tk_per_kg: float
    retail_tk_per_kg: float
    markup_pct: float


class DamSyncReport(BaseModel):
    run_id: str
    workflow: str
    cron: str
    timezone: str
    market_date: date
    rows_ingested: int
    anomaly_threshold_pct: float
    anomalies_flagged: int
    top_anomalies: list[DamAnomalyRow]
    documents_upserted: int
    index_chunks_after: int
    vector_table: str
    next_run_at: datetime


class FloodCheckRow(BaseModel):
    upazila: str
    district: str
    sar_backscatter_db: float
    sar_source: str
    breach_probability_pct: float
    alert_level: str
    simulated_anomaly_active: bool


class VoiceAlertDispatch(BaseModel):
    batch_id: str
    upazila: str
    district: str
    alert_level: str
    breach_probability_pct: float
    recipients: int
    channel: str
    message_bn: str
    status: Literal["QUEUED"]


class SarFloodReport(BaseModel):
    run_id: str
    workflow: str
    cron: str
    checked_at: datetime
    upazilas_checked: int
    rows: list[FloodCheckRow]
    voice_alerts: list[VoiceAlertDispatch]
    early_harvest_dispatches: list[str]
    next_run_at: datetime


class SarFloodCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sar_overrides_db: dict[str, float] = Field(default_factory=dict, description="Upazila -> Sentinel-1 VV dB for this run.")


def _run_id(job: str) -> str:
    now = now_bdt()
    return f"n8n-{job}-{now:%Y%m%dT%H%M%S}-{hashlib.sha256(now.isoformat().encode()).hexdigest()[:6]}"


class N8nWebhookHandlers:
    DAILY_CRON = "0 6 * * *"
    HOURLY_CRON = "0 * * * *"

    async def daily_dam_sync(self) -> DamSyncReport:
        """6:00 AM job: pull today's DAM-modelled spreads, flag syndicate anomalies, upsert bulletins into the index."""
        from mcp_servers.dam_market_mcp import DISTRICT_MARKET_FACTORS, market_prices, markup_pct
        from prompts.prompt_registry import PROMPT_REGISTRY
        from rag.hybrid_retriever import get_retriever
        from rag.knowledge_seed import KnowledgeDoc

        today = now_bdt().date()
        threshold = float(PROMPT_REGISTRY.params("syndicate_bypass")["anomaly_threshold_pct"])
        rows: list[DamAnomalyRow] = []
        docs: list[KnowledgeDoc] = []
        for district_name in DISTRICT_MARKET_FACTORS:
            district = bd_geo.district_by_name(district_name)
            lines = []
            for crop in Crop:
                p = market_prices(crop, district, today)
                rows.append(DamAnomalyRow(district=district_name, crop=crop, grower_tk_per_kg=p.grower,
                                          wholesale_tk_per_kg=p.wholesale, retail_tk_per_kg=p.retail,
                                          markup_pct=markup_pct(p.grower, p.retail)))
                lines.append(f"{crop.value} grower Tk {p.grower:.2f}/kg, wholesale Tk {p.wholesale:.2f}/kg, "
                             f"retail Tk {p.retail:.2f}/kg ({markup_pct(p.grower, p.retail):.0f}% markup)")
            docs.append(KnowledgeDoc(
                doc_id=f"DAM-DAILY-{district_name.upper().replace(' ', '-').replace(chr(39), '')}",
                title=f"DAM daily price bulletin {today.isoformat()} - {district_name}",
                source="Department of Agricultural Marketing (n8n daily sync)", doc_type="daily market price bulletin",
                year=today.year, crops=tuple(c.value for c in Crop), districts=(district_name,),
                topics=("daily price", "price spread", "markup"),
                text=f"Market prices in {district_name} on {today.isoformat()}: " + "; ".join(lines) + ".",
            ))
        chunks_after = get_retriever().upsert_documents(docs)
        anomalies = sorted((r for r in rows if r.markup_pct > threshold), key=lambda r: -r.markup_pct)
        now = now_bdt()
        next_run = now.replace(hour=6, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        return DamSyncReport(
            run_id=_run_id("daily-dam-sync"), workflow="KrishiNexus - Daily DAM Price Sync", cron=self.DAILY_CRON,
            timezone="Asia/Dhaka", market_date=today, rows_ingested=len(rows), anomaly_threshold_pct=threshold,
            anomalies_flagged=len(anomalies), top_anomalies=anomalies[:10], documents_upserted=len(docs),
            index_chunks_after=chunks_after, vector_table="rag_chunks (pgvector schema, in-memory numpy mirror)",
            next_run_at=next_run,
        )

    async def hourly_sar_flood_check(self, request: SarFloodCheckRequest) -> SarFloodReport:
        """Hourly job: score every haor upazila from the latest Sentinel-1 pass, queue Bangla voice alerts
        for ORANGE/RED, and open a CRITICAL 72-hour harvest window for RED."""
        from mcp_servers.agri_weather_sar_mcp import HAOR_UPAZILAS, calculate_haor_flash_flood_risk, trigger_early_harvest_window
        from mcp_servers.anomaly_state import ANOMALIES
        from schemas.mcp_models import CalculateHaorFlashFloodRiskInput, TriggerEarlyHarvestWindowInput, UrgencyLevel

        now = now_bdt()
        overrides = {bd_geo.normalize_place(k): v for k, v in request.sar_overrides_db.items()}
        rows: list[FloodCheckRow] = []
        alerts: list[VoiceAlertDispatch] = []
        dispatches: list[str] = []
        for name, profile in HAOR_UPAZILAS.items():
            upazila = bd_geo.resolve_upazila(name)
            injected = ANOMALIES.latest("haor_flash_flood", lambda a, d=upazila.district: a.params.get("district") == d)
            if bd_geo.normalize_place(name) in overrides:
                sar, source = overrides[bd_geo.normalize_place(name)], "operator override"
            elif injected is not None:
                sar, source = float(injected.params["sar_water_backscatter_db"]), "injected anomaly scene"
            else:
                sar = round(-11.5 + 3.0 * (stable_unit("s1-pass", name, now.strftime("%Y%m%d%H")) - 0.5), 2)
                sar, source = sar, "simulated Sentinel-1 IW GRD pass (no live Copernicus feed)"
            risk = await calculate_haor_flash_flood_risk(CalculateHaorFlashFloodRiskInput(upazila=name, sar_water_backscatter_db=sar))
            rows.append(FloodCheckRow(upazila=name, district=upazila.district, sar_backscatter_db=sar, sar_source=source,
                                      breach_probability_pct=risk.embankment_breach_probability_pct,
                                      alert_level=risk.alert_level.value, simulated_anomaly_active=risk.simulated_anomaly_active))
            if risk.alert_level.value in ("ORANGE", "RED"):
                alerts.append(VoiceAlertDispatch(
                    batch_id=f"IVR-{name[:3].upper()}-{now:%Y%m%d%H}", upazila=name, district=upazila.district,
                    alert_level=risk.alert_level.value, breach_probability_pct=risk.embankment_breach_probability_pct,
                    recipients=math.ceil(profile.boro_area_ha / 0.6), channel="IVR outbound voice call + SMS fallback",
                    message_bn=risk.voice_alert_bn, status="QUEUED"))
            if risk.alert_level.value == "RED":
                plan = await trigger_early_harvest_window(TriggerEarlyHarvestWindowInput(
                    cluster_id=f"HAOR-{name[:4].upper()}-01", upazila=name, urgency_level=UrgencyLevel.CRITICAL))
                dispatches.append(plan.dispatch_id)
        return SarFloodReport(
            run_id=_run_id("hourly-sar-flood-check"), workflow="KrishiNexus - Hourly SAR Flood Check", cron=self.HOURLY_CRON,
            checked_at=now, upazilas_checked=len(rows), rows=rows, voice_alerts=alerts, early_harvest_dispatches=dispatches,
            next_run_at=(now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0),
        )

    def workflow_definitions(self, base_url: str) -> list[dict[str, Any]]:
        """Importable n8n workflow JSON: Schedule Trigger -> HTTP Request to this backend."""
        def workflow(name: str, cron: str, path: str) -> dict[str, Any]:
            return {
                "name": name,
                "nodes": [
                    {"id": "trigger", "name": "Schedule Trigger", "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2,
                     "position": [0, 0], "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": cron}]}}},
                    {"id": "call", "name": "Call KrishiNexus", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
                     "position": [260, 0], "parameters": {"method": "POST", "url": f"{base_url}{path}",
                                                          "sendBody": True, "specifyBody": "json", "jsonBody": "{}"}},
                ],
                "connections": {"Schedule Trigger": {"main": [[{"node": "Call KrishiNexus", "type": "main", "index": 0}]]}},
                "settings": {"timezone": "Asia/Dhaka", "executionOrder": "v1"},
            }

        return [
            workflow("KrishiNexus - Daily DAM Price Sync", self.DAILY_CRON, "/automation/n8n/daily-dam-sync"),
            workflow("KrishiNexus - Hourly SAR Flood Check", self.HOURLY_CRON, "/automation/n8n/hourly-sar-flood-check"),
        ]


N8N_HANDLERS = N8nWebhookHandlers()
