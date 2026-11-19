"""Self-check for marketplace.py: list -> bid -> accept -> escrow -> driver delivery -> release, with every role check,
plus the live market events (stream and poll), the truck's location and the registered payout wallet.

Run from backend/:  .venv/Scripts/python check_marketplace.py   (uses temporary files; .state is left alone)
"""

import json
import tempfile
import time
from datetime import timedelta
from pathlib import Path

from starlette.testclient import TestClient

import auth
import market_bids
import marketplace
from main import app
from mcp_servers.bd_geo import resolve_district, road_distance_km
from mcp_servers.dam_market_mcp import AVG_TRUCK_SPEED_KMH

tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
auth.USERS_FILE = Path(tmp.name) / "users.json"
auth.USERS.reset()
marketplace.MARKET_FILE = Path(tmp.name) / "marketplace.json"
market_bids.ESCROW_FILE = Path(tmp.name) / "escrows.json"
seq0 = marketplace.EVENTS.seq
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

    # Disputes: a party to the sale reports a problem, the bank resolves it; a refund cancels the sale and the driver's job.
    bank = as_("BANK-UCB-01")
    lot2 = client.post("/market/lots", headers=farmer, json={"crop": "Brinjal", "grade": "A", "weight_kg": 300, "district": "Bogura",
                                                             "upazila": "Shibganj"}).json()
    bid2 = client.post(f"/market/lots/{lot2['lot_id']}/bids", headers=buyer, json={"price_tk_per_kg": 30}).json()["bids"][-1]
    sold2 = client.post(f"/market/lots/{lot2['lot_id']}/accept", headers=farmer, json={"bid_id": bid2["bid_id"], **wallet}).json()
    assert sold2["delivery"]["distance_km"] > 8  # driven from Shibganj, never 0 km
    assert client.post(f"/market/lots/{lot2['lot_id']}/disputes", headers=trader, json={"kind": "OTHER"}).status_code == 403
    d = client.post(f"/market/lots/{lot2['lot_id']}/disputes", headers=buyer,
                    json={"kind": "DELIVERY_PROBLEM", "note": "call 01711223344"}).json()["disputes"][-1]
    assert d["status"] == "OPEN" and "01711223344" not in d["note"]
    assert client.post(f"/market/disputes/{d['dispute_id']}/resolve", headers=farmer, json={"resolution": "NO_CHANGE"}).status_code == 403
    refunded = client.post(f"/market/disputes/{d['dispute_id']}/resolve", headers=bank,
                           json={"resolution": "REFUND_TO_BUYER", "note": "No truck could reach Shibganj"}).json()
    assert refunded["escrow"]["status"] == "REFUNDED" and refunded["status"] == "CANCELLED"
    assert client.post(f"/market/deliveries/{lot2['lot_id']}/claim", headers=driver).status_code == 409
    assert client.post(f"/market/disputes/{d['dispute_id']}/resolve", headers=bank, json={"resolution": "NO_CHANGE"}).status_code == 409
    rows = client.get("/market/ledger", headers=bank).json()
    assert any(r["escrow_id"] == refunded["escrow"]["escrow_id"] and r["status"] == "REFUNDED" for r in rows)
    assert client.get("/market/ledger", headers=farmer).status_code == 403
    assert [x["dispute_id"] for x in client.get("/market/disputes", headers=bank).json()][0] == "DSP-SEED06"  # open first

    # Cancelling: only the owner, only while open.
    open_lot = client.post("/market/lots", headers=farmer, json={"crop": "Brinjal", "grade": "B", "weight_kg": 200, "district": "Bogura"}).json()
    assert client.post(f"/market/lots/{open_lot['lot_id']}/cancel", headers=other_farmer).status_code == 403
    assert client.post(f"/market/lots/{open_lot['lot_id']}/cancel", headers=farmer).json()["status"] == "CANCELLED"
    assert client.post("/market/reset", headers=buyer).status_code == 403
    assert len(client.post("/market/reset", headers=admin).json()) == 7

    # Live truck location: only the job's driver, only while ASSIGNED or PICKED_UP, shown rounded, one per 10 s.
    spot = {"lat": 24.84567, "lng": 89.37123, "accuracy_m": 12, "speed_kmh": 38}
    where = "/market/deliveries/LOT-SEED06/location"  # seeded: picked up by Jalal, Rangpur -> Dhaka
    assert client.post("/market/deliveries/LOT-SEED03/location", headers=driver, json=spot).status_code == 409  # unclaimed
    assert client.post("/market/deliveries/LOT-SEED07/location", headers=driver, json=spot).status_code == 409  # delivered
    for who in (as_(second), buyer, judge, farmer):
        assert client.post(where, headers=who, json=spot).status_code == 403
    for bad in ({"lat": 91, "lng": 90}, {"lat": 24, "lng": 181}, {**spot, "speed_kmh": 250}, {**spot, "accuracy_m": -1}, {**spot, "alt": 9}):
        assert client.post(where, headers=driver, json=bad).status_code == 422, bad
    moved = client.post(where, headers=driver, json=spot)
    position, market = moved.json()["delivery"]["position"], resolve_district(moved.json()["delivery"]["destination_district"])
    km = road_distance_km(spot["lat"], spot["lng"], market.lat, market.lon)
    assert {k: position[k] for k in ("lat", "lng", "accuracy_m", "km_to_destination", "eta_hours_left")} == {
        "lat": 24.85, "lng": 89.37, "accuracy_m": 12, "km_to_destination": round(km), "eta_hours_left": round(km / AVG_TRUCK_SPEED_KMH, 1)}
    assert position["at"] and "24.84567" not in moved.text and "speed" not in moved.text
    assert marketplace.MARKET.lots["LOT-SEED06"].delivery._fix.lat == 24.84567  # the precise fix stays on the server
    assert "24.84567" not in marketplace.MARKET_FILE.read_text(encoding="utf-8")  # ... in memory, never on disk
    seq = marketplace.EVENTS.seq
    fast = client.post(where, headers=driver, json={**spot, "lat": 25.5})
    assert fast.status_code == 200 and fast.json()["delivery"]["position"] == position and marketplace.EVENTS.seq == seq
    marketplace.MARKET.lots["LOT-SEED06"].delivery.position.at -= timedelta(seconds=11)
    assert client.post(where, headers=driver, json={**spot, "lat": 25.5}).json()["delivery"]["position"]["lat"] == 25.5
    assert marketplace.EVENTS.seq == seq + 1
    client.post("/market/deliveries/LOT-SEED03/claim", headers=driver)  # ASSIGNED reports too
    assert client.post("/market/deliveries/LOT-SEED03/location", headers=driver, json=spot).json()["delivery"]["position"]["lng"] == 89.37
    assert any(l["delivery"] and l["delivery"]["position"] for l in client.get("/market/lots", headers=buyer).json())
    # Only the people in a sale see its truck: Dhaka Fresh DC bought LOT-SEED06, Bogura Agro Traders did not.
    def seed06(headers: dict[str, str]) -> dict:
        return next(l for l in client.get("/market/lots", headers=headers).json() if l["lot_id"] == "LOT-SEED06")
    assert seed06(buyer)["delivery"]["position"] and seed06(other_farmer)["delivery"]["position"]  # its buyer and farmer
    assert seed06(admin)["delivery"]["position"]
    assert seed06(trader)["delivery"]["position"] is None and seed06(farmer)["delivery"]["position"] is None
    assert marketplace.MARKET.lots["LOT-SEED06"].delivery.position is not None  # hidden in the view, kept in the book
    client.post("/market/deliveries/LOT-SEED06/deliver", headers=driver)
    assert client.post(where, headers=driver, json=spot).status_code == 409
    assert marketplace.MARKET.lots["LOT-SEED06"].delivery._fix is None

    # A sign-up's payouts go only to the wallet it registered (any of the four providers); seeded farmers keep today's rule.
    def register(n: int, role: str, district: str, wallet: str) -> dict[str, str]:
        reply = client.post("/auth/register", json={
            "name": f"Sign-up {n}", "role": role, "district": district, "phone": f"0171200{n:04d}", "nid": f"{2_000_000_000 + n}",
            "wallet_provider": wallet, "wallet_number": f"0181200{n:04d}", "password": "own-pass-123", "consent": True})
        assert reply.status_code == 201, reply.text
        return {"Authorization": f"Bearer {reply.json()['session']['token']}"}

    shirin, far_buyer = register(1, "farmer", "Bogura", "Rocket"), register(2, "buyer", "Chattogram", "Nagad")
    mine = client.post("/market/lots", headers=shirin, json={"crop": "Brinjal", "grade": "A", "weight_kg": 200, "district": "Bogura"}).json()
    offer = client.post(f"/market/lots/{mine['lot_id']}/bids", headers=far_buyer, json={"price_tk_per_kg": 30}).json()["bids"][-1]
    for wrong in ({"wallet": "bKash", "wallet_number": "01812000001"}, {"wallet": "Rocket", "wallet_number": "01812000009"}):
        refused = client.post(f"/market/lots/{mine['lot_id']}/accept", headers=shirin, json={"bid_id": offer["bid_id"], **wrong})
        assert refused.status_code == 409, refused.text
        assert refused.json()["detail"] == "Payouts go only to the wallet registered with this account (Rocket 018••••0001)."
    paid = client.post(f"/market/lots/{mine['lot_id']}/accept", headers=shirin,
                       json={"bid_id": offer["bid_id"], "wallet": "Rocket", "wallet_number": "০১৮১২-০০০০০১"}).json()
    assert paid["status"] == "SOLD" and paid["escrow"]["wallet"] == "Rocket" and paid["escrow"]["wallet_masked"] == "018•••••001"
    assert paid["delivery"]["destination_district"] == "Dhaka Karwan Bazar"  # a buyer district the node can't route delivers to Dhaka

    # The 1-tap truckload lock takes the new wallets too, and the bank's ledger shows both kinds.
    hub = client.get("/market/bids", params={"crop": "Cardinal Potato", "district": "Bogura", "weight_kg": 400}).json()["bids"][0]
    upay = client.post("/market/bids/lock", json={"crop": "Cardinal Potato", "origin_district": "Bogura", "weight_kg": 400, "grade": "A",
                                                  "hub_id": hub["hub_id"], "wallet": "Upay", "wallet_number": "01912000003",
                                                  "farmer_id": "FARM-BOG-104"})
    assert upay.status_code == 200 and upay.json()["wallet"] == "Upay" and "Upay" in upay.json()["note"]
    wallets = {(r["kind"], r["wallet"]) for r in client.get("/market/ledger", headers=bank).json()}
    assert {("Direct sale", "Rocket"), ("Truckload lock", "Upay")} <= wallets

    # Every change was a numbered public event: replayed by GET /market/events and by the stream after Last-Event-ID.
    page = client.get("/market/events", params={"since": seq0}).json()
    kinds = [e["kind"] for e in page["events"]]
    assert set(kinds) == {"lot_listed", "bid_placed", "lot_sold", "lot_cancelled", "job_claimed", "picked_up", "temperature_logged",
                          "location", "delivered", "dispute_opened", "dispute_resolved", "market_reset"}, set(kinds)
    seqs = [e["seq"] for e in page["events"]]
    assert seqs == list(range(seq0 + 1, seq0 + 1 + len(seqs))) and page["seq"] == seqs[-1] and kinds[0] == "market_reset"
    assert all(set(e) == {"seq", "kind", "lot_id", "crop", "status", "delivery_status", "at"} for e in page["events"])
    assert not any(word in json.dumps(page, ensure_ascii=False) for word in ("Abdul", "Jalal", "Sign-up", "0181200", "FARM-"))
    assert client.get("/market/events", params={"since": seqs[-2]}).json()["events"] == page["events"][-1:]
    sold_event = next(e for e in page["events"] if e["kind"] == "lot_sold" and e["lot_id"] == mine["lot_id"])
    assert sold_event["status"] == "SOLD" and sold_event["delivery_status"] == "AWAITING_DRIVER" and sold_event["crop"] == "Brinjal"

    def read_stream(lines_in, count: int, until: str = "data: ") -> list[str]:
        """Lines from an SSE line iterator until `count` lines start with `until`."""
        lines, seen = [], 0
        for line in lines_in:
            lines.append(line)
            seen += line.startswith(until)
            if seen == count:
                return lines
        raise AssertionError(lines)

    with client.stream("GET", "/market/stream", headers={"Last-Event-ID": str(seqs[-3])}) as sse:
        assert sse.headers["content-type"].startswith("text/event-stream") and sse.headers["x-accel-buffering"] == "no"
        assert sse.headers["cache-control"] == "no-cache"
        lines = read_stream(sse.iter_lines(), 2)  # the two events after seqs[-3]
        assert lines[:4] == ["retry: 5000", "", f"id: {seqs[-2]}", "event: market"]
        assert json.loads(lines[4].removeprefix("data: ")) == page["events"][-2] and lines[-3] == f"id: {seqs[-1]}"
    with client.stream("GET", "/market/stream", params={"since": 0}, headers={"Last-Event-ID": str(seqs[-2])}) as sse:
        assert read_stream(sse.iter_lines(), 1)[2] == f"id: {seqs[-1]}"  # the header wins over ?since (a browser reconnects so)
    with client.stream("GET", "/market/stream", params={"since": seqs[-2]}) as sse:
        assert read_stream(sse.iter_lines(), 1)[2] == f"id: {seqs[-1]}"
    with client.stream("GET", "/market/stream") as sse:  # no cursor: from now on, live
        live = sse.iter_lines()
        assert read_stream(live, 1, "retry") == ["retry: 5000"]
        fresh = client.post("/market/lots", headers=farmer, json={"crop": "Green Chili", "grade": "A", "weight_kg": 120, "district": "Bogura"}).json()
        event = json.loads(read_stream(live, 1)[-1].removeprefix("data: "))
        assert event["kind"] == "lot_listed" and event["lot_id"] == fresh["lot_id"] and event["status"] == "OPEN"
    marketplace.PING_S = 0.2
    with client.stream("GET", "/market/stream") as sse:
        assert ": ping" in read_stream(sse.iter_lines(), 1, ": ping")
    marketplace.PING_S, marketplace.MAX_STREAMS = 15.0, 0
    assert client.get("/market/stream").status_code == 503  # full: clients poll /market/events instead
    marketplace.MAX_STREAMS = 200
    for _ in range(40):  # closed streams give their slot back
        if marketplace.EVENTS.streams == 0:
            break
        time.sleep(0.05)
    assert marketplace.EVENTS.streams == 0, marketplace.EVENTS.streams

print("marketplace.py: all checks passed")
