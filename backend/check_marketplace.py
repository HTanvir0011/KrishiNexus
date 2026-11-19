"""Self-check for marketplace.py: list -> bid -> accept -> escrow -> driver delivery -> release, with every role check.

Run from backend/:  .venv/Scripts/python check_marketplace.py   (uses temporary files; .state is left alone)
"""

import tempfile
from pathlib import Path

from starlette.testclient import TestClient

import auth
import marketplace
from main import app

tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
auth.USERS_FILE = Path(tmp.name) / "users.json"
auth.USERS.reset()
marketplace.MARKET_FILE = Path(tmp.name) / "marketplace.json"
seeded = marketplace.MARKET.reset()
assert sorted(l.status for l in seeded) == ["DELIVERED", "IN_TRANSIT", "OPEN", "OPEN", "OPEN", "OPEN", "SOLD"]
assert all(l.escrow is None or l.escrow.signature for l in seeded) and len({b.bid_id for l in seeded for b in l.bids}) == 10
below = next(l for l in seeded if l.lot_id == "LOT-SEED04")
assert all(b.price_tk_per_kg < below.floor_tk_per_kg for b in below.bids)  # the circuit-breaker demo lot

with TestClient(app) as client:
    def as_(user_id: str) -> dict[str, str]:
        token = client.post("/auth/login", json={"user_id": user_id}).json()["token"]
        return {"Authorization": f"Bearer {token}"}

    farmer, other_farmer = as_("FARM-BOG-104"), as_("FARM-RAN-001")
    buyer, trader, driver, admin = as_("BUY-DHK-01"), as_("BUY-BOG-02"), as_("DRIVER-BOG-01"), as_("ADMIN-01")
    assert client.get("/market/lots").status_code == 401  # login required

    lot = client.post("/market/lots", headers=farmer, json={"crop": "Cardinal Potato", "grade": "A", "weight_kg": 500,
                                                            "district": "bogra", "asking_price_tk_per_kg": 20,
                                                            "note": "call 01711223344"}).json()
    lot_id = lot["lot_id"]
    assert lot["district"] == "Bogura" and lot["floor_tk_per_kg"] == 15 and "01711223344" not in lot["note"]
    assert client.post("/market/lots", headers=buyer, json={"crop": "Brinjal", "grade": "B", "weight_kg": 100, "district": "Bogura"}).status_code == 403

    # Buyers compete; a buyer's new bid replaces the old one; farmers can't bid.
    client.post(f"/market/lots/{lot_id}/bids", headers=buyer, json={"price_tk_per_kg": 14})
    client.post(f"/market/lots/{lot_id}/bids", headers=trader, json={"price_tk_per_kg": 18.5})
    bids = client.post(f"/market/lots/{lot_id}/bids", headers=buyer, json={"price_tk_per_kg": 19.25}).json()["bids"]
    assert [b["status"] for b in bids] == ["WITHDRAWN", "ACTIVE", "ACTIVE"]
    assert client.post(f"/market/lots/{lot_id}/bids", headers=farmer, json={"price_tk_per_kg": 30}).status_code == 403

    # Only the owner accepts; the cost-floor breaker needs a confirmation below Tk 15/kg.
    low = client.post(f"/market/lots/{lot_id}/bids", headers=trader, json={"price_tk_per_kg": 12}).json()["bids"][-1]
    wallet = {"wallet": "bKash", "wallet_number": "01711223344"}
    assert client.post(f"/market/lots/{lot_id}/accept", headers=other_farmer, json={"bid_id": low["bid_id"], **wallet}).status_code == 403
    blocked = client.post(f"/market/lots/{lot_id}/accept", headers=farmer, json={"bid_id": low["bid_id"], **wallet})
    assert blocked.status_code == 409 and "Circuit breaker" in blocked.json()["detail"]
    best = next(b for b in bids if b["status"] == "ACTIVE" and b["buyer_id"] == "BUY-DHK-01")
    sold = client.post(f"/market/lots/{lot_id}/accept", headers=farmer, json={"bid_id": best["bid_id"], **wallet}).json()
    assert sold["status"] == "SOLD" and sold["escrow"]["status"] == "HELD" and sold["escrow"]["amount_tk"] == 500 * 19.25
    assert sold["escrow"]["wallet_masked"] == "017•••••344" and "01711223344" not in str(sold)
    assert sold["delivery"]["destination_district"].startswith("Dhaka") and sold["delivery"]["eta_hours"] > 1.5
    assert sorted(b["status"] for b in sold["bids"]) == ["ACCEPTED", "REJECTED", "WITHDRAWN", "WITHDRAWN"]
    assert client.post(f"/market/lots/{lot_id}/bids", headers=trader, json={"price_tk_per_kg": 25}).status_code == 409

    # The driver's chain: claim, pickup, temperature check, deliver -> escrow released. Others are refused.
    assert client.get("/market/deliveries", headers=buyer).status_code == 403
    judge = as_("JUDGE-01")  # judges watch every delivery, read-only
    assert len(client.get("/market/deliveries", headers=judge).json()) == sum(1 for l in seeded if l.delivery is not None) + 1
    assert client.post(f"/market/deliveries/{lot_id}/claim", headers=judge).status_code == 403
    assert any(l["lot_id"] == lot_id for l in client.get("/market/deliveries", headers=driver).json())
    assert client.post(f"/market/deliveries/{lot_id}/pickup", headers=driver).status_code == 409  # claim first
    client.post(f"/market/deliveries/{lot_id}/claim", headers=driver)
    second = client.post("/auth/admin/users", headers=admin, json={"name": "Second Driver", "role": "driver"}).json()["user_id"]
    assert client.post(f"/market/deliveries/{lot_id}/pickup", headers=as_(second)).status_code == 403
    assert client.post(f"/market/deliveries/{lot_id}/pickup", headers=driver).json()["status"] == "IN_TRANSIT"
    hot = client.post(f"/market/deliveries/{lot_id}/temperature", headers=driver, json={"temp_c": 38, "rh_pct": 60}).json()
    assert hot["delivery"]["shelf_life_hours"] is not None and hot["delivery"]["events"][-1]["kind"] == "TEMPERATURE"
    done = client.post(f"/market/deliveries/{lot_id}/deliver", headers=driver).json()
    assert done["status"] == "DELIVERED" and done["escrow"]["status"] == "RELEASED" and done["escrow"]["released_at"]
    assert client.post(f"/market/deliveries/{lot_id}/deliver", headers=driver).status_code == 409

    # Cancelling: only the owner, only while open.
    open_lot = client.post("/market/lots", headers=farmer, json={"crop": "Brinjal", "grade": "B", "weight_kg": 200, "district": "Bogura"}).json()
    assert client.post(f"/market/lots/{open_lot['lot_id']}/cancel", headers=other_farmer).status_code == 403
    assert client.post(f"/market/lots/{open_lot['lot_id']}/cancel", headers=farmer).json()["status"] == "CANCELLED"
    assert client.post("/market/reset", headers=buyer).status_code == 403
    assert len(client.post("/market/reset", headers=admin).json()) == 7

print("marketplace.py: all checks passed")
