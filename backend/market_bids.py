"""Buyer bids and the 1-tap escrow lock.

A bid is a buyer's modelled price for this lot today. The buyers are supermarket DCs, wholesale arats, agro-processors
and the 66 WFP aggregation centres. The prices come from the DAM-modelled hub rules that `find_optimal_selling_hub`
already ranks by net payout per kg after pooled 5-ton freight, hub fees and transit loss. They are not a live feed
from named buyers.

Locking a bid opens an escrow: the buyer's payment for the lot is held, and released to the farmer's bKash or Nagad
wallet when the delivery is weighed at the buyer's door. The escrow is SIMULATED: no money moves and no wallet API is
called. A live escrow needs a merchant agreement and API credentials from bKash or Nagad.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from automation.workflows import STATE_DIR
from config import BDT, now_bdt, settings
from mcp_servers.base import ToolExecutionError
from mcp_servers.dam_market_mcp import SEASONAL_CURVES, find_optimal_selling_hub
from schemas.mcp_models import Crop, FindOptimalSellingHubInput, Grade, HubType, SellingHubOption

ESCROW_FILE = STATE_DIR / "escrows.json"
Wallet = Literal["bKash", "Nagad"]
RELEASE_CONDITION = "Released to the farmer's wallet when the delivery is weighed at the buyer's door."
SIMULATED_NOTE = ("Simulated escrow: no money moves and no bKash or Nagad API is called. A live escrow needs a merchant "
                  "agreement and API credentials.")


class Bid(SellingHubOption):
    bid_id: str
    below_cost_floor: bool = Field(description="The net payout is under the crop's production-cost floor.")


class BidBoard(BaseModel):
    crop: Crop
    origin_district: str
    grade: Grade
    weight_kg: float
    market_date: date
    valid_until: datetime
    farmgate_baseline_tk_per_kg: float = Field(description="What a Faria pays at the farm gate today.")
    production_cost_floor_tk_per_kg: float
    bids: list[Bid] = Field(description="Best net payout first.")
    data_source: Literal["MODELLED_BIDS"] = "MODELLED_BIDS"
    note: str = ("Bids are modelled from DAM hub prices, freight and fees, not a live feed from named buyers. "
                 "Net payout is after transport, fees and transit loss.")


class LockBidRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    crop: Crop
    origin_district: str = Field(min_length=2, max_length=40)
    weight_kg: float = Field(gt=0, le=100_000)
    grade: Grade
    hub_id: str = Field(pattern=r"^[A-Z]{2,4}-[A-Z0-9-]{2,12}$", description="The buyer whose bid to lock.")
    wallet: Wallet
    wallet_number: str = Field(pattern=r"^01[3-9]\d{8}$", description="The farmer's wallet number; only a masked form is stored.")
    farmer_id: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9-]+$")


class EscrowReceipt(BaseModel):
    escrow_id: str
    bid_id: str
    status: Literal["HELD"]
    simulated: Literal[True] = True
    farmer_id: str
    hub_id: str
    buyer_name: str
    buyer_type: HubType
    crop: Crop
    grade: Grade
    weight_kg: float
    bid_price_tk_per_kg: float
    net_payout_tk_per_kg: float
    amount_tk: float
    below_cost_floor: bool
    wallet: Wallet
    wallet_masked: str
    release_condition: str = RELEASE_CONDITION
    locked_at: datetime
    note: str = SIMULATED_NOTE
    signature: str = Field(description="HMAC-SHA256 of the other fields, keyed by KNX_RECEIPT_SIGNING_KEY.")


def _bid_id(hub_id: str, crop: Crop, grade: Grade, weight_kg: float, origin: str, on: date) -> str:
    return "BID-" + hashlib.sha256(f"{hub_id}|{crop.value}|{grade.value}|{weight_kg:g}|{origin}|{on}".encode()).hexdigest()[:10].upper()


async def bid_board(crop: Crop, origin_district: str, weight_kg: float, grade: Grade) -> BidBoard:
    ranked = await find_optimal_selling_hub(FindOptimalSellingHubInput(
        crop=crop, weight_kg=weight_kg, origin_district=origin_district, grade=grade))
    floor = SEASONAL_CURVES[crop].production_cost_floor
    return BidBoard(
        crop=crop, origin_district=ranked.origin_district, grade=grade, weight_kg=weight_kg, market_date=ranked.market_date,
        valid_until=datetime.combine(ranked.market_date, time(23, 59), tzinfo=BDT),
        farmgate_baseline_tk_per_kg=ranked.farmgate_baseline_tk_per_kg, production_cost_floor_tk_per_kg=floor,
        bids=[Bid(**o.model_dump(), bid_id=_bid_id(o.hub_id, crop, grade, weight_kg, ranked.origin_district, ranked.market_date),
                  below_cost_floor=o.net_payout_tk_per_kg < floor) for o in ranked.ranked_options],
    )


def _mask(number: str) -> str:
    return f"{number[:3]}•••••{number[-3:]}"


class EscrowBook:
    """Locked bids, one per farmer and bid (a second tap returns the same escrow), kept in .state/escrows.json."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.receipts: dict[str, EscrowReceipt] = {}
        if ESCROW_FILE.exists():
            self.receipts = {k: EscrowReceipt(**v) for k, v in json.loads(ESCROW_FILE.read_text(encoding="utf-8")).items()}

    async def lock(self, request: LockBidRequest) -> EscrowReceipt:
        # The bid is recomputed here, so the price and payout come from the node, never from the client.
        board = await bid_board(request.crop, request.origin_district, request.weight_kg, request.grade)
        bid = next((b for b in board.bids if b.hub_id == request.hub_id), None)
        if bid is None:
            raise ToolExecutionError(f"{request.hub_id} is not bidding on this lot today; refresh the bids and choose again.")
        async with self._lock:
            key = f"{request.farmer_id}|{bid.bid_id}"
            existing = next((r for r in self.receipts.values() if f"{r.farmer_id}|{r.bid_id}" == key), None)
            if existing is not None:
                return existing
            fields = dict(
                escrow_id="ESC-" + hashlib.sha256(f"{key}|{now_bdt().isoformat()}".encode()).hexdigest()[:12].upper(),
                bid_id=bid.bid_id, status="HELD", farmer_id=request.farmer_id, hub_id=bid.hub_id, buyer_name=bid.hub_name,
                buyer_type=bid.hub_type, crop=request.crop, grade=request.grade, weight_kg=request.weight_kg,
                bid_price_tk_per_kg=bid.hub_price_tk_per_kg, net_payout_tk_per_kg=bid.net_payout_tk_per_kg,
                amount_tk=bid.net_payout_total_tk, below_cost_floor=bid.below_cost_floor, wallet=request.wallet,
                wallet_masked=_mask(request.wallet_number), locked_at=now_bdt())
            unsigned = EscrowReceipt(**fields, signature="")
            canonical = json.dumps(unsigned.model_dump(mode="json", exclude={"signature"}), sort_keys=True, ensure_ascii=False)
            receipt = unsigned.model_copy(update={"signature": hmac.new(
                settings.receipt_signing_key.encode(), canonical.encode(), hashlib.sha256).hexdigest()})
            self.receipts[receipt.escrow_id] = receipt
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            ESCROW_FILE.write_text(json.dumps({k: v.model_dump(mode="json") for k, v in self.receipts.items()},
                                              ensure_ascii=False, indent=1), encoding="utf-8")
            return receipt


ESCROWS = EscrowBook()
