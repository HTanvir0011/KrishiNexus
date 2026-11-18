"""Self-check for auth.py: quick login, signed tokens, role guard and the last-admin rule.

Run from backend/:  .venv/Scripts/python check_auth.py   (uses a temporary users file; .state is left alone)
"""

import os
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

print("auth.py: all checks passed")
