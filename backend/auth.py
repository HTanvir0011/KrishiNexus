"""Demo accounts: password login, one-click quick login by role, signed session tokens and the admin API.

This is a demo login, not a production one: quick login needs no password, so anyone can pick a demo account, the
seeded accounts share a published demo password, and the other API routes stay open. Roles decide which workspace a user lands on and who may manage accounts (admin only).
Accounts persist in .state/users.json (delete it to re-seed).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import threading
import time
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from agents.tracing import BROADCASTER
from automation.workflows import STATE_DIR, TRUCK_POOLS
from config import now_bdt, settings
from market_bids import ESCROWS, EscrowReceipt
from mcp_servers.anomaly_state import ANOMALIES

USERS_FILE = STATE_DIR / "users.json"
DEMO_PASSWORD = "krishi2026"  # shown on the login page; every seeded account uses it
PBKDF2_ROUNDS = 200_000
TOKEN_TTL_SECONDS = 12 * 3600


class Role(StrEnum):
    FARMER = "farmer"
    COOP = "coop"
    STORAGE = "storage"
    BUYER = "buyer"
    BANK = "bank"
    DRIVER = "driver"
    JUDGE = "judge"
    ADMIN = "admin"


ID_PREFIX = {Role.FARMER: "FARM", Role.COOP: "COOP", Role.STORAGE: "HIMAGAR", Role.BUYER: "BUY", Role.BANK: "BANK", Role.DRIVER: "DRIVER", Role.JUDGE: "JUDGE", Role.ADMIN: "ADMIN"}


class User(BaseModel):
    user_id: str = Field(pattern=r"^[A-Z0-9-]{3,40}$")
    name: str = Field(min_length=2, max_length=60)
    role: Role
    district: str = Field(default="", max_length=40)
    title: str = Field(default="", max_length=80, description="What this account represents, e.g. 'Potato grower, Pirgachha'.")
    active: bool = True


class NewUser(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    role: Role
    district: str = Field(default="", max_length=40)
    title: str = Field(default="", max_length=80)
    password: str | None = Field(default=None, min_length=6, max_length=128, description="Defaults to the demo password.")


class UserPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=60)
    role: Role | None = None
    district: str | None = Field(default=None, max_length=40)
    title: str | None = Field(default=None, max_length=80)
    active: bool | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)


class LoginRequest(BaseModel):
    user_id: str = Field(min_length=3, max_length=40, description="Account id, any case, e.g. farm-ran-001.")
    password: str | None = Field(default=None, max_length=128, description="Omit for the demo quick login.")


class Session(BaseModel):
    token: str
    expires_in_s: int
    user: User


class AdminOverview(BaseModel):
    users_by_role: dict[str, int]
    active_users: int
    truck_pools: int
    lots_in_pools: int
    escrows_locked: int
    active_anomalies: int
    trace_events: int
    time: str


SEED_USERS = [
    User(user_id="FARM-RAN-001", name="Rahim Mia", role=Role.FARMER, district="Rangpur", title="Potato grower, Pirgachha"),
    User(user_id="FARM-BOG-104", name="Abdul Karim", role=Role.FARMER, district="Bogura", title="Potato and chili grower, Shibganj"),
    User(user_id="FARM-SUN-007", name="Jamila Begum", role=Role.FARMER, district="Sunamganj", title="Boro rice grower, Tahirpur haor"),
    User(user_id="COOP-BOG-01", name="Shibganj Union Co-op", role=Role.COOP, district="Bogura", title="Co-op and cold-chain desk"),
    User(user_id="HIMAGAR-BOG-05", name="Shajahanpur Himagar", role=Role.STORAGE, district="Bogura", title="Cold-storage manager, BCSA-BOG-05"),
    User(user_id="BUY-DHK-01", name="Dhaka Fresh DC", role=Role.BUYER, district="Dhaka", title="Supermarket distribution centre"),
    User(user_id="BUY-BOG-02", name="Bogura Agro Traders", role=Role.BUYER, district="Bogura", title="Wholesale trader buying direct from farmers"),
    User(user_id="DRIVER-BOG-01", name="Jalal Uddin", role=Role.DRIVER, district="Bogura", title="5-ton truck driver, Bogura"),
    User(user_id="BANK-UCB-01", name="UCB Agri Desk", role=Role.BANK, district="Dhaka", title="Collateral-free agri-credit officer"),
    User(user_id="JUDGE-01", name="Congress Judge", role=Role.JUDGE, title="Sees every seat in split-screen"),
    User(user_id="ADMIN-01", name="Platform Admin", role=Role.ADMIN, title="Manages accounts and demo state"),
]


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def password_matches(password: str, stored: str) -> bool:
    _, rounds, salt, digest = stored.split("$")
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
    return hmac.compare_digest(candidate.hex(), digest)


class UserBook:
    """Accounts and their password hashes, kept in .state/users.json and written atomically on every change.
    The hashes never leave this class: the API returns `User`, which has no password field."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.users: dict[str, User] = {}
        self.password_hashes: dict[str, str] = {}
        if USERS_FILE.exists():
            records = json.loads(USERS_FILE.read_text(encoding="utf-8"))
            self.users = {r["user_id"]: User(**r) for r in records}
            demo_hash = hash_password(DEMO_PASSWORD)  # files written before passwords existed get the demo password
            self.password_hashes = {r["user_id"]: r.get("password_hash") or demo_hash for r in records}
        else:
            self.reset()

    def _persist(self) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = USERS_FILE.with_suffix(".tmp")
        records = [{**u.model_dump(mode="json"), "password_hash": self.password_hashes[u.user_id]} for u in self.users.values()]
        tmp.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, USERS_FILE)

    def reset(self) -> list[User]:
        demo_hash = hash_password(DEMO_PASSWORD)
        with self._lock:
            self.users = {u.user_id: u.model_copy() for u in SEED_USERS}
            self.password_hashes = {u.user_id: demo_hash for u in SEED_USERS}
            self._persist()
            return list(self.users.values())

    def authenticate(self, user_id: str, password: str | None) -> User:
        """The active account for this id (any case); with a password, only if it matches."""
        user = self.users.get(user_id.strip().upper())
        if password is not None:
            if user is None or not password_matches(password, self.password_hashes[user.user_id]):
                raise HTTPException(status_code=401, detail="Wrong account ID or password.")
        if user is None or not user.active:
            raise HTTPException(status_code=403, detail="That account does not exist or is disabled.")
        return user

    def _check_admin_left(self, candidate: dict[str, User]) -> None:
        if not any(u.role is Role.ADMIN and u.active for u in candidate.values()):
            raise HTTPException(status_code=409, detail="At least one active admin account must remain.")

    def create(self, body: NewUser) -> User:
        prefix = ID_PREFIX[body.role]
        with self._lock:
            number = 1 + max((int(m.group(1)) for u in self.users.values()
                              if (m := re.fullmatch(rf"{prefix}-U(\d+)", u.user_id))), default=0)
            user = User(user_id=f"{prefix}-U{number:03d}", **body.model_dump(exclude={"password"}))
            self.users[user.user_id] = user
            self.password_hashes[user.user_id] = hash_password(body.password or DEMO_PASSWORD)
            self._persist()
            return user

    def update(self, user_id: str, patch: UserPatch) -> User:
        with self._lock:
            current = self.users.get(user_id)
            if current is None:
                raise HTTPException(status_code=404, detail=f"No account '{user_id}'.")
            updated = current.model_copy(update=patch.model_dump(exclude_none=True, exclude={"password"}))
            self._check_admin_left({**self.users, user_id: updated})
            self.users[user_id] = updated
            if patch.password:
                self.password_hashes[user_id] = hash_password(patch.password)
            self._persist()
            return updated

    def delete(self, user_id: str) -> None:
        with self._lock:
            if user_id not in self.users:
                raise HTTPException(status_code=404, detail=f"No account '{user_id}'.")
            self._check_admin_left({k: v for k, v in self.users.items() if k != user_id})
            del self.users[user_id]
            del self.password_hashes[user_id]
            self._persist()


USERS = UserBook()


def _sign(payload: str) -> str:
    return hmac.new(settings.receipt_signing_key.encode(), f"session|{payload}".encode(), hashlib.sha256).hexdigest()


def issue_token(user_id: str, now: float | None = None) -> str:
    payload = f"{user_id}.{int((now or time.time()) + TOKEN_TTL_SECONDS)}"
    return f"{payload}.{_sign(payload)}"


def user_from_token(token: str, now: float | None = None) -> User | None:
    """The active account a token was issued to, or None if it is forged, expired, disabled or deleted."""
    payload, _, signature = token.rpartition(".")
    user_id, _, expires = payload.partition(".")
    if not (payload and expires.isdigit() and hmac.compare_digest(signature, _sign(payload))):
        return None
    if int(expires) < (now or time.time()):
        return None
    user = USERS.users.get(user_id)
    return user if user is not None and user.active else None


def current_user(authorization: Annotated[str, Header()] = "") -> User:
    scheme, _, token = authorization.partition(" ")
    user = user_from_token(token) if scheme.lower() == "bearer" else None
    if user is None:
        raise HTTPException(status_code=401, detail="Log in again: no valid session.", headers={"WWW-Authenticate": "Bearer"})
    return user


def admin_user(user: Annotated[User, Depends(current_user)]) -> User:
    if user.role is not Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin accounts only.")
    return user


router = APIRouter(prefix="/auth", tags=["auth"])
admin = APIRouter(prefix="/auth/admin", tags=["auth"], dependencies=[Depends(admin_user)])


@router.get("/demo-users", response_model=list[User])
async def demo_users() -> list[User]:
    """Active accounts for the quick-login screen."""
    return [u for u in USERS.users.values() if u.active]


@router.post("/login", response_model=Session)
async def login(body: LoginRequest) -> Session:
    """Log in with an account id and password, or (demo quick login) with the id alone; returns a signed token."""
    user = USERS.authenticate(body.user_id, body.password)
    return Session(token=issue_token(user.user_id), expires_in_s=TOKEN_TTL_SECONDS, user=user)


@router.get("/me", response_model=User)
async def me(user: Annotated[User, Depends(current_user)]) -> User:
    return user


@admin.get("/users", response_model=list[User])
async def list_users() -> list[User]:
    return list(USERS.users.values())


@admin.post("/users", response_model=User, status_code=201)
async def create_user(body: NewUser) -> User:
    return USERS.create(body)


@admin.patch("/users/{user_id}", response_model=User)
async def update_user(user_id: str, body: UserPatch) -> User:
    return USERS.update(user_id, body)


@admin.delete("/users/{user_id}")
async def delete_user(user_id: str) -> dict[str, str]:
    USERS.delete(user_id)
    return {"deleted": user_id}


@admin.post("/users/reset", response_model=list[User])
async def reset_users() -> list[User]:
    """Restore the seeded demo accounts."""
    return USERS.reset()


@admin.get("/escrows", response_model=list[EscrowReceipt])
async def list_escrows() -> list[EscrowReceipt]:
    """Every simulated escrow the node holds, newest first (wallet numbers are already masked)."""
    return sorted(ESCROWS.receipts.values(), key=lambda r: r.locked_at, reverse=True)


@admin.get("/overview", response_model=AdminOverview)
async def overview() -> AdminOverview:
    pools = await TRUCK_POOLS.list_pools()
    by_role = {role.value: 0 for role in Role}
    for u in USERS.users.values():
        by_role[u.role.value] += 1
    return AdminOverview(
        users_by_role=by_role,
        active_users=sum(u.active for u in USERS.users.values()),
        truck_pools=len(pools),
        lots_in_pools=sum(len(p.lots) for p in pools),
        escrows_locked=len(ESCROWS.receipts),
        active_anomalies=len(ANOMALIES.active()),
        trace_events=len(BROADCASTER.history(None, 2_000)),
        time=now_bdt().isoformat(),
    )
