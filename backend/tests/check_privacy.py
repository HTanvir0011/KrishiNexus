"""Self-check for the privacy promises in /docs#data: the PII vault forgets, and feedback stores no personal details.

Run from backend/:  .venv/Scripts/python -m tests.check_privacy   (uses temporary files; .state is left alone)
"""

import tempfile
from pathlib import Path

from starlette.testclient import TestClient

import auth
import feedback
from guardrails.pii_scrubber import PIIVault
from main import app

# The vault keeps hidden originals for its time limit only.
vault = PIIVault(ttl_seconds=100)
old = vault.store([("<PHONE_1>", "01711223344")], now=0)
kept = vault.store([("<NAME_1>", "Rahim")], now=50)
assert vault.restore(old, "call <PHONE_1>", now=60) == "call 01711223344"
vault.store([("<X>", "y")], now=120)
assert len(vault) == 2
try:
    vault.restore(old, "<PHONE_1>", now=120)
    raise AssertionError("an expired vault entry was restored")
except KeyError:
    pass
assert vault.restore(kept, "hi <NAME_1>", now=149) == "hi Rahim"

tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
feedback.FEEDBACK_FILE = Path(tmp.name) / "feedback.json"
feedback.FEEDBACK.items = []
auth.USERS_FILE = Path(tmp.name) / "users.json"
auth.USERS.reset()

with TestClient(app) as client:
    farmer = client.post("/auth/login", json={"user_id": "FARM-RAN-001"}).json()["token"]
    admin = client.post("/auth/login", json={"user_id": "ADMIN-01"}).json()["token"]

    sent = client.post("/feedback", json={"useful": True, "comment": "Good advice. Call me on 01711223344", "session_id": "KNX-UI-TEST1"},
                       headers={"Authorization": f"Bearer {farmer}"})
    assert sent.status_code == 201, sent.text
    item = sent.json()
    assert "01711223344" not in item["comment"] and item["pii_hidden"] == 1
    assert item["user_id"] == "FARM-RAN-001" and item["role"] == "farmer"
    assert "01711223344" not in feedback.FEEDBACK_FILE.read_text(encoding="utf-8")

    anonymous = client.post("/feedback", json={"useful": False}).json()
    assert anonymous["user_id"] is None and anonymous["comment"] == ""
    assert client.post("/feedback", json={"useful": True, "comment": "x" * 501}).status_code == 422

    assert client.get("/auth/admin/feedback", headers={"Authorization": f"Bearer {farmer}"}).status_code == 403
    summary = client.get("/auth/admin/feedback", headers={"Authorization": f"Bearer {admin}"}).json()
    assert summary["total"] == 2 and summary["useful"] == 1 and summary["useful_pct"] == 50.0
    assert summary["by_role"] == {"farmer": 1, "visitor": 1} and summary["items"][0]["useful"] is False

print("privacy and feedback: all checks passed")
