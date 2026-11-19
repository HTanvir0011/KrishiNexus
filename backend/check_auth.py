"""Self-check for auth.py: quick login, signed tokens, role guard, the last-admin rule and sign-up with KYC.

Run from backend/:  .venv/Scripts/python check_auth.py   (uses a temporary users file; .state is left alone)
"""

import json
import os
import re
import tempfile
import time
from pathlib import Path

from starlette.testclient import TestClient

import auth
from main import app

tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
auth.USERS_FILE = Path(tmp.name) / "users.json"
auth.USERS.reset()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


with TestClient(app) as client:
    users = client.get("/auth/demo-users").json()
    assert {u["role"] for u in users} == {r.value for r in auth.Role}

    farmer = client.post("/auth/login", json={"user_id": "FARM-RAN-001"}).json()
    admin = client.post("/auth/login", json={"user_id": "ADMIN-01"}).json()
    assert client.get("/auth/me", headers=bearer(farmer["token"])).json()["name"] == "Rahim Mia"
    assert client.post("/auth/login", json={"user_id": "NOPE-01"}).status_code == 403

    # Password login: any-case id, the demo password, wrong passwords refused; hashes never reach the API.
    login = client.post("/auth/login", json={"user_id": "farm-ran-001", "password": auth.DEMO_PASSWORD})
    assert login.status_code == 200 and login.json()["user"]["user_id"] == "FARM-RAN-001"
    assert client.post("/auth/login", json={"user_id": "FARM-RAN-001", "password": "wrong-pass"}).status_code == 401
    assert client.post("/auth/login", json={"user_id": "NOPE-01", "password": "wrong-pass"}).status_code == 401
    assert "password" not in str(client.get("/auth/demo-users").json())

    # Forged, tampered and expired tokens are refused.
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers=bearer("FARM-RAN-001.9999999999.deadbeef")).status_code == 401
    assert client.get("/auth/me", headers=bearer(farmer["token"].replace("FARM-RAN-001", "ADMIN-01"))).status_code == 401
    expired = auth.issue_token("FARM-RAN-001", now=time.time() - auth.TOKEN_TTL_SECONDS - 5)
    assert client.get("/auth/me", headers=bearer(expired)).status_code == 401

    # Only admins reach the admin API.
    assert client.get("/auth/admin/users", headers=bearer(farmer["token"])).status_code == 403
    assert client.get("/auth/admin/overview", headers=bearer(admin["token"])).json()["users_by_role"]["farmer"] == 3
    assert isinstance(client.get("/auth/admin/escrows", headers=bearer(admin["token"])).json(), list)
    assert client.get("/auth/admin/escrows", headers=bearer(farmer["token"])).status_code == 403

    created = client.post("/auth/admin/users", headers=bearer(admin["token"]),
                          json={"name": "Nasima Akter", "role": "farmer", "district": "Thakurgaon"}).json()
    assert created["user_id"] == "FARM-U001"
    client.patch("/auth/admin/users/FARM-U001", headers=bearer(admin["token"]), json={"password": "nasima-pass"})
    assert client.post("/auth/login", json={"user_id": "FARM-U001", "password": "nasima-pass"}).status_code == 200
    assert client.post("/auth/login", json={"user_id": "FARM-U001", "password": auth.DEMO_PASSWORD}).status_code == 401
    stored = auth.USERS_FILE.read_text(encoding="utf-8")
    assert "password_hash" in stored and "nasima-pass" not in stored  # stored hashed, never in plain text
    token = client.post("/auth/login", json={"user_id": "FARM-U001"}).json()["token"]
    client.patch("/auth/admin/users/FARM-U001", headers=bearer(admin["token"]), json={"active": False})
    assert client.get("/auth/me", headers=bearer(token)).status_code == 401  # a disabled account's session ends
    assert client.post("/auth/login", json={"user_id": "FARM-U001"}).status_code == 403

    # The last active admin can be neither demoted nor deleted.
    assert client.patch("/auth/admin/users/ADMIN-01", headers=bearer(admin["token"]), json={"role": "judge"}).status_code == 409
    assert client.delete("/auth/admin/users/ADMIN-01", headers=bearer(admin["token"])).status_code == 409
    assert client.delete("/auth/admin/users/FARM-U001", headers=bearer(admin["token"])).status_code == 200
    assert len(client.post("/auth/admin/users/reset", headers=bearer(admin["token"])).json()) == len(auth.SEED_USERS)

    # A public host sets KNX_ADMIN_PASSWORD: admins then need it; quick login and the demo password are refused.
    os.environ["KNX_ADMIN_PASSWORD"] = "host-only-secret"
    try:
        assert client.post("/auth/login", json={"user_id": "ADMIN-01"}).status_code == 401
        assert client.post("/auth/login", json={"user_id": "admin-01", "password": auth.DEMO_PASSWORD}).status_code == 401
        assert client.post("/auth/login", json={"user_id": "ADMIN-01", "password": "host-only-secret"}).status_code == 200
        assert client.post("/auth/login", json={"user_id": "FARM-RAN-001"}).status_code == 200  # other roles unchanged
    finally:
        del os.environ["KNX_ADMIN_PASSWORD"]

    # Sign-up with KYC: farmers, buyers and drivers are active at once; co-op, cold storage and bank wait for an admin.
    def signup(n: int, role: str = "farmer", **over: object):
        body = {"name": f"Sign-up {n}", "role": role, "district": "Bogura", "upazila": "Shibganj",
                "phone": f"0171100{n:04d}", "nid": f"{1_000_000_000 + n}", "wallet_provider": "Rocket",
                "wallet_number": f"0181100{n:04d}", "password": "own-pass-123", "consent": True,
                **({"organization": "Shibganj Krishi Samabay"} if role in ("coop", "storage", "bank") else {})}
        return client.post("/auth/register", json={**body, **over})

    out = {}
    for n, role in enumerate(("farmer", "buyer", "driver", "coop", "storage", "bank"), start=1):
        reply = signup(n, role)
        assert reply.status_code == 201, reply.text
        out[role] = reply.json()
    for role in ("farmer", "buyer", "driver"):
        assert out[role]["status"] == "ACTIVE" and out[role]["user"]["active"] and not out[role]["user"]["pending_review"]
        assert client.get("/auth/me", headers=bearer(out[role]["session"]["token"])).json()["user_id"] == out[role]["user"]["user_id"]
    for role in ("coop", "storage", "bank"):
        assert out[role]["status"] == "PENDING_REVIEW" and out[role]["session"] is None
        assert not out[role]["user"]["active"] and out[role]["user"]["pending_review"]
    ids = {role: o["user"]["user_id"] for role, o in out.items()}
    assert ids["farmer"].startswith("FARM-BOG-") and ids["storage"].startswith("HIMAGAR-BOG-") and ids["bank"].startswith("BANK-")
    assert all(re.fullmatch(r"[A-Za-z0-9\-]{3,40}", i) for i in ids.values()) and len(set(ids.values())) == 6
    farmer = out["farmer"]["user"]
    assert farmer["self_registered"] and farmer["title"] == "Farmer, Shibganj" and out["coop"]["user"]["title"].startswith("Shibganj Krishi")
    assert {k: farmer["kyc"][k] for k in ("nid_last4", "phone_masked", "wallet_provider", "wallet_masked", "verified")} == {
        "nid_last4": "0001", "phone_masked": "017••••0001", "wallet_provider": "Rocket", "wallet_masked": "018••••0001", "verified": False}
    farmer_token = out["farmer"]["session"]["token"]
    assert client.get("/auth/me", headers=bearer(farmer_token)).json()["kyc"]["registered_at"]
    assert client.post("/auth/register", json={"name": "Dhaka Buyer", "role": "buyer", "district": "Dhaka", "phone": "01911000077",
                                                "nid": "19900000000000077", "wallet_provider": "Upay", "wallet_number": "01911000077",
                                                "password": "own-pass-123", "consent": True}).json()["user"]["user_id"].startswith("BUY-DHK-")

    # Bangla digits, spaces and dashes are normalised before validation; duplicates are caught on the digests.
    bangla = signup(7, phone="০১৭১১-০০০০ ০৭", nid="১০০০ ০০০ ০০৭", wallet_number="০১৮১১-০০০০০৭")
    assert bangla.status_code == 201 and bangla.json()["user"]["kyc"]["phone_masked"] == "017••••0007", bangla.text
    again = signup(7)
    assert again.status_code == 409 and again.json()["detail"] == "An account with this national ID already exists."
    reused_phone = signup(8, phone="01711000001")
    assert reused_phone.status_code == 409 and "phone number" in reused_phone.json()["detail"]
    for bad in ({"role": "admin"}, {"role": "judge"}, {"consent": False}, {"phone": "01211000009"}, {"nid": "12345678901"},
                {"wallet_provider": "Paypal"}, {"password": "short"}, {"name": "X"}, {"is_admin": True}):
        assert signup(9, **bad).status_code == 422, bad
    assert signup(9, "coop", organization="  ").status_code == 422  # institutions must name their organisation

    # Pending accounts can't log in; sign-ups never quick-login; demo-users lists only the demo accounts.
    pending = client.post("/auth/login", json={"user_id": ids["coop"], "password": "own-pass-123"})
    assert pending.status_code == 403 and pending.json()["detail"] == "This account is waiting for an admin to approve it."
    assert client.post("/auth/login", json={"user_id": ids["coop"], "password": "wrong-pass-1"}).status_code == 401
    quick = client.post("/auth/login", json={"user_id": ids["farmer"]})
    assert quick.status_code == 401 and "password" in quick.json()["detail"]
    assert client.post("/auth/login", json={"user_id": ids["farmer"].lower(), "password": "own-pass-123"}).status_code == 200
    assert not any(u["self_registered"] for u in client.get("/auth/demo-users").json())
    assert len(client.get("/auth/demo-users").json()) == len(auth.SEED_USERS)

    # The admin approves one (KYC verified, it can log in) and rejects another (its national ID can sign up again).
    assert client.patch(f"/auth/admin/users/{ids['coop']}", headers=bearer(farmer_token), json={"active": True}).status_code == 403
    approved = client.patch(f"/auth/admin/users/{ids['coop']}", headers=bearer(admin["token"]), json={"active": True}).json()
    assert approved["active"] and not approved["pending_review"] and approved["kyc"]["verified"]
    assert client.post("/auth/login", json={"user_id": ids["coop"], "password": "own-pass-123"}).status_code == 200
    assert client.delete(f"/auth/admin/users/{ids['storage']}", headers=bearer(admin["token"])).status_code == 200
    assert signup(5, "storage").status_code == 201
    listed = client.get("/auth/admin/users", headers=bearer(admin["token"]))
    assert sum(u["self_registered"] for u in listed.json()) == 8 and "digest" not in listed.text

    # users.json holds digests and masks, never a raw national ID, phone or wallet number, and reloads the same.
    stored = auth.USERS_FILE.read_text(encoding="utf-8")
    raw = [f"0171100{n:04d}" for n in range(1, 8)] + [f"0181100{n:04d}" for n in range(1, 8)] + [str(1_000_000_000 + n) for n in range(1, 8)]
    assert "kyc_digests" in stored and not any(number in stored for number in raw + ["01911000077", "19900000000000077"])
    reloaded = auth.UserBook()
    assert reloaded.kyc_digests == auth.USERS.kyc_digests and reloaded.users[ids["farmer"]].kyc.wallet_masked == "018••••0001"
    assert reloaded.payout_wallet_matches(reloaded.users[ids["farmer"]], "Rocket", "01811000001")
    assert not reloaded.payout_wallet_matches(reloaded.users[ids["farmer"]], "bKash", "01811000001")

    # A users.json written before sign-ups existed still loads, every account without KYC.
    legacy = Path(tmp.name) / "legacy.json"
    legacy.write_text(json.dumps([{k: v for k, v in r.items() if k not in ("kyc", "pending_review", "self_registered")}
                                  for r in json.loads(stored) if not r.get("kyc_digests")]), encoding="utf-8")
    current_file, auth.USERS_FILE = auth.USERS_FILE, legacy
    old = auth.UserBook()
    assert len(old.users) == len(auth.SEED_USERS) and all(u.kyc is None and not u.self_registered for u in old.users.values())
    auth.USERS_FILE = current_file

    # Sign-ups pause at the cap; resetting accounts removes every sign-up (and frees its national ID).
    auth.MAX_SELF_REGISTERED = 8
    capped = signup(10)
    assert capped.status_code == 429 and capped.json()["detail"] == "Sign-ups are paused on this demo node."
    auth.MAX_SELF_REGISTERED = 500
    after_reset = client.post("/auth/admin/users/reset", headers=bearer(admin["token"])).json()
    assert len(after_reset) == len(auth.SEED_USERS) and not any(u["self_registered"] for u in after_reset)
    assert client.get("/auth/me", headers=bearer(farmer_token)).status_code == 401 and signup(1).status_code == 201

print("auth.py: all checks passed")
