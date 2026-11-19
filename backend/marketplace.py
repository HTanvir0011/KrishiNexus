"""Direct marketplace: farmers list lots, buyers bid, the farmer accepts, a driver delivers, delivery releases the escrow.

The chain, all role-checked:
  farmer  POST /market/lots                         list a lot (crop, grade, kg, district, asking price)
  buyer   POST /market/lots/{lot_id}/bids           bid Tk/kg; a new bid from the same buyer replaces the old one
  farmer  POST /market/lots/{lot_id}/accept         accept one bid -> HMAC-signed escrow HELD + delivery job
  driver  POST /market/deliveries/{lot_id}/claim    take the job, then /pickup, /temperature (shelf-life check), /deliver
  delivered -> escrow RELEASED to the farmer

A bid below the crop's production-cost floor can only be accepted with `accept_below_floor`, the marketplace's own
circuit breaker. The escrow is SIMULATED like the 1-tap escrow in market_bids.py: no money moves and no wallet API is
called. State lives in .state/marketplace.json; a fresh node seeds three demo lots so every seat has something to do.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
from datetime import datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

import auth
from automation.workflows import ARRIVAL_SHELF_RESERVE, STATE_DIR
from config import now_bdt, settings
from guardrails.pii_scrubber import PII_SCRUBBER
from mcp_servers.base import ToolExecutionError
from mcp_servers.bd_geo import resolve_district, road_distance_km
from mcp_servers.coldchain_iot_mcp import calculate_dynamic_shelf_life
from mcp_servers.dam_market_mcp import AVG_TRUCK_SPEED_KMH, LOADING_HOURS, SEASONAL_CURVES
from schemas.mcp_models import CalculateDynamicShelfLifeInput, Crop, Grade

MARKET_FILE = STATE_DIR / "marketplace.json"
MAX_LOTS = 300
MAX_BIDS_PER_LOT = 50
Wallet = Literal["bKash", "Nagad"]
SIMULATED_NOTE = "Simulated escrow: no money moves and no bKash or Nagad API is called."


class MarketBid(BaseModel):
    bid_id: str
    buyer_id: str
    buyer_name: str
    buyer_district: str
    price_tk_per_kg: float
    note: str = ""
    placed_at: datetime
    status: Literal["ACTIVE", "ACCEPTED", "REJECTED", "WITHDRAWN"] = "ACTIVE"


class Escrow(BaseModel):
    escrow_id: str
    amount_tk: float
    wallet: Wallet
    wallet_masked: str
    status: Literal["HELD", "RELEASED"] = "HELD"
    locked_at: datetime
    released_at: datetime | None = None
    simulated: Literal[True] = True
    note: str = SIMULATED_NOTE
    signature: str


class DeliveryEvent(BaseModel):
    at: datetime
    kind: Literal["CREATED", "CLAIMED", "PICKED_UP", "TEMPERATURE", "DELIVERED"]
    detail: str


class Delivery(BaseModel):
    status: Literal["AWAITING_DRIVER", "ASSIGNED", "PICKED_UP", "DELIVERED"] = "AWAITING_DRIVER"
    origin_district: str
    destination_district: str
    distance_km: float
    eta_hours: float
    driver_id: str | None = None
    driver_name: str | None = None
    last_temp_c: float | None = None
    last_rh_pct: float | None = None
    shelf_life_hours: float | None = None
    at_risk: bool = False
    events: list[DeliveryEvent] = Field(default_factory=list)


class Lot(BaseModel):
    lot_id: str
    farmer_id: str
    farmer_name: str
    crop: Crop
    grade: Grade
    weight_kg: float
    district: str
    upazila: str = ""
    asking_price_tk_per_kg: float | None = None
    floor_tk_per_kg: float = Field(description="The crop's production-cost floor; accepting below it needs a confirmation.")
    certificate_id: str | None = None
    note: str = ""
    listed_at: datetime
    status: Literal["OPEN", "SOLD", "IN_TRANSIT", "DELIVERED", "CANCELLED"] = "OPEN"
    bids: list[MarketBid] = Field(default_factory=list)
    accepted_bid_id: str | None = None
    escrow: Escrow | None = None
    delivery: Delivery | None = None


class NewLot(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    crop: Crop
    grade: Grade
    weight_kg: float = Field(ge=50, le=20_000)
    district: str = Field(min_length=2, max_length=40)
    upazila: str = Field(default="", max_length=40)
    asking_price_tk_per_kg: float | None = Field(default=None, gt=0, le=500)
    certificate_id: str | None = Field(default=None, pattern=r"^[A-Z0-9-]{6,60}$")
    note: str = Field(default="", max_length=200)


class NewBid(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    price_tk_per_kg: float = Field(gt=0, le=500)
    note: str = Field(default="", max_length=200)


class AcceptBid(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bid_id: str = Field(pattern=r"^MB-[A-Z0-9]{6,20}$")
    wallet: Wallet
    wallet_number: str = Field(pattern=r"^01[3-9]\d{8}$", description="Only a masked form is stored.")
    accept_below_floor: bool = False


class TemperatureReport(BaseModel):
    temp_c: float = Field(ge=-5, le=55)
    rh_pct: float = Field(default=85, ge=5, le=100)


def _scrub(text: str) -> str:
    return PII_SCRUBBER.scrub(text).anonymized_text.strip() if text.strip() else ""


def _id(prefix: str, *parts: object) -> str:
    return f"{prefix}-" + hashlib.sha256("|".join(map(str, (*parts, now_bdt().isoformat(), os.urandom(4).hex()))).encode()).hexdigest()[:10].upper()


def _route(origin: str, destination: str) -> tuple[float, float]:
    a, b = resolve_district(origin), resolve_district(destination)
    km = round(road_distance_km(a.lat, a.lon, b.lat, b.lon), 1)
    return km, round(km / AVG_TRUCK_SPEED_KMH + LOADING_HOURS, 1)


def _sign(fields: dict[str, object]) -> str:
    canonical = json.dumps(fields, sort_keys=True, ensure_ascii=False, default=str)
    return hmac.new(settings.receipt_signing_key.encode(), f"market|{canonical}".encode(), hashlib.sha256).hexdigest()


class MarketBook:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.lots: dict[str, Lot] = {}
        if MARKET_FILE.exists():
            self.lots = {k: Lot(**v) for k, v in json.loads(MARKET_FILE.read_text(encoding="utf-8")).items()}
        else:
            self.reset()

    def _persist(self) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = MARKET_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps({k: v.model_dump(mode="json") for k, v in self.lots.items()}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        os.replace(tmp, MARKET_FILE)

    def reset(self) -> list[Lot]:
        """Seven demo lots, enough for a walkthrough: four open with competing bids (one only below the cost floor, so the
        circuit breaker shows), one sold and waiting for a driver, one on the road with Jalal, one delivered and paid."""
        now = now_bdt()
        floor = {c: SEASONAL_CURVES[c].production_cost_floor for c in Crop}
        dhaka, bogura = ("BUY-DHK-01", "Dhaka Fresh DC", "Dhaka"), ("BUY-BOG-02", "Bogura Agro Traders", "Bogura")

        def ago(hours: float) -> datetime:
            return now - timedelta(hours=hours)

        def bid(lot: str, buyer: tuple[str, str, str], price: float, hours: float, note: str = "") -> MarketBid:
            return MarketBid(bid_id=f"MB-SEED{lot[-2:]}{buyer[0][-2:]}", buyer_id=buyer[0], buyer_name=buyer[1],
                             buyer_district=buyer[2], price_tk_per_kg=price, note=note, placed_at=ago(hours))

        def lot(lot_id: str, farmer: tuple[str, str], crop: Crop, grade: Grade, kg: float, district: str, upazila: str,
                asking: float, hours: float, bids: list[MarketBid], note: str = "") -> Lot:
            return Lot(lot_id=lot_id, farmer_id=farmer[0], farmer_name=farmer[1], crop=crop, grade=grade, weight_kg=kg,
                       district=district, upazila=upazila, asking_price_tk_per_kg=asking, floor_tk_per_kg=floor[crop],
                       note=note, listed_at=ago(hours), bids=bids)

        def sold(item: Lot, buyer: tuple[str, str, str], price: float, hours: float, wallet: str) -> Lot:
            """Mark `item` sold to `buyer` `hours` ago, with a signed escrow and a delivery job (as accept() does)."""
            chosen = bid(item.lot_id, buyer, price, hours + 1).model_copy(update={"status": "ACCEPTED"})
            km, eta = _route(item.district, buyer[2])
            fields = {"escrow_id": f"MES-{item.lot_id[4:]}", "amount_tk": round(price * item.weight_kg, 2), "wallet": "bKash",
                      "wallet_masked": wallet, "locked_at": ago(hours).isoformat()}
            return item.model_copy(update={
                "status": "SOLD", "bids": [*item.bids, chosen], "accepted_bid_id": chosen.bid_id,
                "escrow": Escrow(**{**fields, "locked_at": ago(hours)}, signature=_sign(fields)),
                "delivery": Delivery(origin_district=item.district, destination_district=resolve_district(buyer[2]).name,
                                     distance_km=km, eta_hours=eta,
                                     events=[DeliveryEvent(at=ago(hours), kind="CREATED",
                                                           detail=f"Sold to {buyer[1]} at Tk {price:g}/kg")])})

        rahim, jamila, abdul = ("FARM-RAN-001", "Rahim Mia"), ("FARM-SUN-007", "Jamila Begum"), ("FARM-BOG-104", "Abdul Karim")
        lots = [
            lot("LOT-SEED01", rahim, Crop.CARDINAL_POTATO, Grade.A, 400, "Rangpur", "Pirgachha", 19, 5,
                [bid("LOT-SEED01", bogura, 17.75, 4), bid("LOT-SEED01", dhaka, 18.5, 2, "Can collect this week")],
                note="Sorted and bagged, 50 kg sacks"),
            lot("LOT-SEED04", rahim, Crop.DIAMANT_POTATO, Grade.B, 600, "Rangpur", "Pirgachha", 17, 3,
                [bid("LOT-SEED04", bogura, 13.5, 1, "Grade B, small tubers")]),
            lot("LOT-SEED02", jamila, Crop.BORO_RICE, Grade.B, 1_200, "Sunamganj", "Tahirpur", 44, 9,
                [bid("LOT-SEED02", bogura, 42.5, 7), bid("LOT-SEED02", dhaka, 43.25, 3)],
                note="Harvested before the flood warning"),
            lot("LOT-SEED05", abdul, Crop.BRINJAL, Grade.A, 250, "Bogura", "Shibganj", 25, 6,
                [bid("LOT-SEED05", dhaka, 22, 5), bid("LOT-SEED05", bogura, 23.5, 2)]),
            sold(lot("LOT-SEED03", abdul, Crop.GREEN_CHILI, Grade.A, 300, "Bogura", "Shibganj", 60, 8, []),
                 bogura, 58, 2, "017•••••344"),
            sold(lot("LOT-SEED06", rahim, Crop.CARDINAL_POTATO, Grade.A, 800, "Rangpur", "Mithapukur", 18.5, 30, []),
                 dhaka, 18, 26, "018•••••512"),
            sold(lot("LOT-SEED07", jamila, Crop.BORO_RICE, Grade.A, 1_000, "Sunamganj", "Tahirpur", 44, 100, []),
                 dhaka, 43, 96, "019•••••207"),
        ]
        by_id = {item.lot_id: item for item in lots}
        # On the road with Jalal: claimed and loaded, no temperature reading yet (the walkthrough reports one live).
        on_road = by_id["LOT-SEED06"]
        on_road.status = "IN_TRANSIT"
        on_road.delivery.status, on_road.delivery.driver_id, on_road.delivery.driver_name = "PICKED_UP", "DRIVER-BOG-01", "Jalal Uddin"
        on_road.delivery.events += [DeliveryEvent(at=ago(25), kind="CLAIMED", detail="Jalal Uddin took the job"),
                                    DeliveryEvent(at=ago(3), kind="PICKED_UP", detail="800 kg loaded in Rangpur")]
        # Delivered last week: the escrow was released to Jamila.
        done = by_id["LOT-SEED07"]
        done.status = "DELIVERED"
        done.escrow.status, done.escrow.released_at = "RELEASED", ago(80)
        done.delivery.status, done.delivery.driver_id, done.delivery.driver_name = "DELIVERED", "DRIVER-BOG-01", "Jalal Uddin"
        done.delivery.events += [DeliveryEvent(at=ago(95), kind="CLAIMED", detail="Jalal Uddin took the job"),
                                 DeliveryEvent(at=ago(90), kind="PICKED_UP", detail="1000 kg loaded in Sunamganj"),
                                 DeliveryEvent(at=ago(80), kind="DELIVERED",
                                               detail=f"Weighed at {done.delivery.destination_district}; escrow released to the farmer")]
        with self._lock:
            self.lots = by_id
            self._persist()
            return list(self.lots.values())

    def _get(self, lot_id: str) -> Lot:
        lot = self.lots.get(lot_id)
        if lot is None:
            raise HTTPException(status_code=404, detail=f"No lot '{lot_id}'.")
        return lot

    def list_lot(self, body: NewLot, farmer: auth.User) -> Lot:
        try:
            district = resolve_district(body.district).name
        except ToolExecutionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        lot = Lot(lot_id=_id("LOT", farmer.user_id), farmer_id=farmer.user_id, farmer_name=farmer.name, crop=body.crop,
                  grade=body.grade, weight_kg=body.weight_kg, district=district, upazila=body.upazila,
                  asking_price_tk_per_kg=body.asking_price_tk_per_kg, floor_tk_per_kg=SEASONAL_CURVES[body.crop].production_cost_floor,
                  certificate_id=body.certificate_id, note=_scrub(body.note), listed_at=now_bdt())
        with self._lock:
            if sum(1 for l in self.lots.values() if l.farmer_id == farmer.user_id and l.status == "OPEN") >= 10:
                raise HTTPException(status_code=409, detail="You already have 10 open lots; sell or cancel one first.")
            if len(self.lots) >= MAX_LOTS:  # keep the newest; drop the oldest finished lot
                finished = [l for l in self.lots.values() if l.status in ("DELIVERED", "CANCELLED")]
                if not finished:
                    raise HTTPException(status_code=409, detail="The marketplace is full; try again later.")
                del self.lots[min(finished, key=lambda l: l.listed_at).lot_id]
            self.lots[lot.lot_id] = lot
            self._persist()
        return lot

    def bid(self, lot_id: str, body: NewBid, buyer: auth.User) -> Lot:
        with self._lock:
            lot = self._get(lot_id)
            if lot.status != "OPEN":
                raise HTTPException(status_code=409, detail="This lot is no longer open for bids.")
            for old in lot.bids:  # a buyer's new bid replaces their earlier one
                if old.buyer_id == buyer.user_id and old.status == "ACTIVE":
                    old.status = "WITHDRAWN"
            if len(lot.bids) >= MAX_BIDS_PER_LOT:
                raise HTTPException(status_code=409, detail="This lot has reached its bid limit.")
            lot.bids.append(MarketBid(bid_id=_id("MB", lot_id, buyer.user_id), buyer_id=buyer.user_id, buyer_name=buyer.name,
                                      buyer_district=buyer.district or "Dhaka", price_tk_per_kg=round(body.price_tk_per_kg, 2),
                                      note=_scrub(body.note), placed_at=now_bdt()))
            self._persist()
            return lot

    def accept(self, lot_id: str, body: AcceptBid, farmer: auth.User) -> Lot:
        with self._lock:
            lot = self._get(lot_id)
            if lot.farmer_id != farmer.user_id:
                raise HTTPException(status_code=403, detail="Only the farmer who listed this lot can accept a bid.")
            if lot.status != "OPEN":
                raise HTTPException(status_code=409, detail="This lot is no longer open.")
            chosen = next((b for b in lot.bids if b.bid_id == body.bid_id and b.status == "ACTIVE"), None)
            if chosen is None:
                raise HTTPException(status_code=404, detail="That bid is not active on this lot.")
            if chosen.price_tk_per_kg < lot.floor_tk_per_kg and not body.accept_below_floor:
                raise HTTPException(status_code=409, detail=(
                    f"Circuit breaker: Tk {chosen.price_tk_per_kg:g}/kg is below the Tk {lot.floor_tk_per_kg:g}/kg production cost. "
                    "Confirm to sell at a loss anyway."))
            for b in lot.bids:
                if b.status == "ACTIVE":
                    b.status = "ACCEPTED" if b.bid_id == chosen.bid_id else "REJECTED"
            now = now_bdt()
            fields = {"escrow_id": _id("MES", lot_id), "amount_tk": round(chosen.price_tk_per_kg * lot.weight_kg, 2),
                      "wallet": body.wallet, "wallet_masked": f"{body.wallet_number[:3]}•••••{body.wallet_number[-3:]}",
                      "locked_at": now.isoformat()}
            km, eta = _route(lot.district, chosen.buyer_district)
            lot.status, lot.accepted_bid_id = "SOLD", chosen.bid_id
            lot.escrow = Escrow(**{**fields, "locked_at": now}, signature=_sign(fields))
            lot.delivery = Delivery(origin_district=lot.district, destination_district=resolve_district(chosen.buyer_district).name,
                                    distance_km=km, eta_hours=eta,
                                    events=[DeliveryEvent(at=now, kind="CREATED",
                                                          detail=f"Sold to {chosen.buyer_name} at Tk {chosen.price_tk_per_kg:g}/kg")])
            self._persist()
            return lot

    def cancel(self, lot_id: str, farmer: auth.User) -> Lot:
        with self._lock:
            lot = self._get(lot_id)
            if lot.farmer_id != farmer.user_id:
                raise HTTPException(status_code=403, detail="Only the farmer who listed this lot can cancel it.")
            if lot.status != "OPEN":
                raise HTTPException(status_code=409, detail="Only an open lot can be cancelled.")
            lot.status = "CANCELLED"
            for b in lot.bids:
                if b.status == "ACTIVE":
                    b.status = "REJECTED"
            self._persist()
            return lot

    def _job(self, lot_id: str, driver: auth.User, *, need: str) -> tuple[Lot, Delivery]:
        lot = self._get(lot_id)
        if lot.delivery is None:
            raise HTTPException(status_code=404, detail="This lot has no delivery job.")
        if lot.delivery.status != need:
            raise HTTPException(status_code=409, detail=f"The delivery is {lot.delivery.status.replace('_', ' ').lower()}.")
        if need != "AWAITING_DRIVER" and lot.delivery.driver_id != driver.user_id:
            raise HTTPException(status_code=403, detail="This delivery belongs to another driver.")
        return lot, lot.delivery

    def claim(self, lot_id: str, driver: auth.User) -> Lot:
        with self._lock:
            lot, job = self._job(lot_id, driver, need="AWAITING_DRIVER")
            job.status, job.driver_id, job.driver_name = "ASSIGNED", driver.user_id, driver.name
            job.events.append(DeliveryEvent(at=now_bdt(), kind="CLAIMED", detail=f"{driver.name} took the job"))
            self._persist()
            return lot

    def pickup(self, lot_id: str, driver: auth.User) -> Lot:
        with self._lock:
            lot, job = self._job(lot_id, driver, need="ASSIGNED")
            job.status, lot.status = "PICKED_UP", "IN_TRANSIT"
            job.events.append(DeliveryEvent(at=now_bdt(), kind="PICKED_UP", detail=f"{lot.weight_kg:g} kg loaded in {lot.district}"))
            self._persist()
            return lot

    async def temperature(self, lot_id: str, body: TemperatureReport, driver: auth.User) -> Lot:
        with self._lock:
            lot, _ = self._job(lot_id, driver, need="PICKED_UP")
        life = await calculate_dynamic_shelf_life(CalculateDynamicShelfLifeInput(
            crop=lot.crop, grade=lot.grade, transit_temp_c=body.temp_c, rh_pct=body.rh_pct))
        with self._lock:
            lot, job = self._job(lot_id, driver, need="PICKED_UP")
            job.last_temp_c, job.last_rh_pct = body.temp_c, body.rh_pct
            job.shelf_life_hours = life.remaining_shelf_life_hours
            # The same rule as the truck pools' transit check: arrive with at least a quarter of the shelf life left.
            job.at_risk = job.eta_hours > life.remaining_shelf_life_hours * (1 - ARRIVAL_SHELF_RESERVE)
            job.events.append(DeliveryEvent(at=now_bdt(), kind="TEMPERATURE", detail=(
                f"{body.temp_c:g} °C, {body.rh_pct:g}% RH: {life.remaining_shelf_life_hours:.0f} h of shelf life"
                + (" — at risk, cool the load or deliver sooner" if job.at_risk else ""))))
            self._persist()
            return lot

    def deliver(self, lot_id: str, driver: auth.User) -> Lot:
        with self._lock:
            lot, job = self._job(lot_id, driver, need="PICKED_UP")
            now = now_bdt()
            job.status, lot.status = "DELIVERED", "DELIVERED"
            if lot.escrow is not None:
                lot.escrow.status, lot.escrow.released_at = "RELEASED", now
            job.events.append(DeliveryEvent(at=now, kind="DELIVERED",
                                            detail=f"Weighed at {job.destination_district}; escrow released to the farmer"))
            self._persist()
            return lot


MARKET = MarketBook()


def _role(user: auth.User, *roles: auth.Role) -> None:
    if user.role not in roles and user.role is not auth.Role.ADMIN:
        raise HTTPException(status_code=403, detail=f"Only {' or '.join(r.value for r in roles)} accounts can do this.")


User = Annotated[auth.User, Depends(auth.current_user)]
router = APIRouter(prefix="/market", tags=["marketplace"])


@router.get("/lots", response_model=list[Lot])
async def lots(user: User, status: str | None = None) -> list[Lot]:
    """Every lot, newest first (any logged-in account): bids are public, so buyers compete in the open."""
    items = sorted(MARKET.lots.values(), key=lambda l: l.listed_at, reverse=True)
    return [l for l in items if status is None or l.status == status]


@router.post("/lots", response_model=Lot, status_code=201)
async def list_lot(body: NewLot, user: User) -> Lot:
    _role(user, auth.Role.FARMER)
    return MARKET.list_lot(body, user)


@router.post("/lots/{lot_id}/bids", response_model=Lot)
async def place_bid(lot_id: str, body: NewBid, user: User) -> Lot:
    _role(user, auth.Role.BUYER)
    return MARKET.bid(lot_id, body, user)


@router.post("/lots/{lot_id}/accept", response_model=Lot)
async def accept_bid(lot_id: str, body: AcceptBid, user: User) -> Lot:
    _role(user, auth.Role.FARMER)
    return MARKET.accept(lot_id, body, user)


@router.post("/lots/{lot_id}/cancel", response_model=Lot)
async def cancel_lot(lot_id: str, user: User) -> Lot:
    _role(user, auth.Role.FARMER)
    return MARKET.cancel(lot_id, user)


@router.get("/deliveries", response_model=list[Lot])
async def deliveries(user: User) -> list[Lot]:
    """Sold lots with a delivery job: for a driver, the open ones and their own; judges (read-only) and admins see all."""
    _role(user, auth.Role.DRIVER, auth.Role.JUDGE)
    jobs = [l for l in MARKET.lots.values() if l.delivery is not None]
    if user.role is auth.Role.DRIVER:
        jobs = [l for l in jobs if l.delivery.status == "AWAITING_DRIVER" or l.delivery.driver_id == user.user_id]
    return sorted(jobs, key=lambda l: l.listed_at, reverse=True)


@router.post("/deliveries/{lot_id}/claim", response_model=Lot)
async def claim(lot_id: str, user: User) -> Lot:
    _role(user, auth.Role.DRIVER)
    return MARKET.claim(lot_id, user)


@router.post("/deliveries/{lot_id}/pickup", response_model=Lot)
async def pickup(lot_id: str, user: User) -> Lot:
    _role(user, auth.Role.DRIVER)
    return MARKET.pickup(lot_id, user)


@router.post("/deliveries/{lot_id}/temperature", response_model=Lot)
async def temperature(lot_id: str, body: TemperatureReport, user: User) -> Lot:
    _role(user, auth.Role.DRIVER)
    return await MARKET.temperature(lot_id, body, user)


@router.post("/deliveries/{lot_id}/deliver", response_model=Lot)
async def deliver(lot_id: str, user: User) -> Lot:
    _role(user, auth.Role.DRIVER)
    return MARKET.deliver(lot_id, user)


@router.post("/reset", response_model=list[Lot])
async def reset(user: User) -> list[Lot]:
    """Admin: restore the seven demo lots."""
    _role(user, auth.Role.ADMIN)
    return MARKET.reset()
