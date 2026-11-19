"""Demo accounts: password login, one-click quick login by role, sign-up with KYC, signed session tokens and the admin API.

This is a demo login, not a production one: quick login needs no password, so anyone can pick a demo account, the
seeded accounts share a published demo password, and the other API routes stay open. Where KNX_ADMIN_PASSWORD is set
(the hosted demo), admin accounts need that password instead. Roles decide which workspace a user lands on and who may manage accounts (admin only).
Anyone can sign up (POST /auth/register) as a farmer, buyer or driver, active at once; co-op, cold-storage and bank
accounts wait for an admin to approve them. A sign-up's national ID, phone and wallet number are kept only as HMAC
digests (for duplicate and payout checks) and masked forms; such accounts sign in with their own password, never by
quick login. Accounts persist in .state/users.json (delete it to re-seed).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from agents.tracing import BROADCASTER
from automation.workflows import STATE_DIR, TRUCK_POOLS
from config import now_bdt, settings
from market_bids import ESCROWS, EscrowReceipt, Wallet
from mcp_servers.anomaly_state import ANOMALIES

USERS_FILE = STATE_DIR / "users.json"
DEMO_PASSWORD = "krishi2026"  # shown on the login page; every seeded account uses it
PBKDF2_ROUNDS = 200_000
TOKEN_TTL_SECONDS = 12 * 3600
MAX_SELF_REGISTERED = 500
BANGLA_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


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
REVIEWED_ROLES = (Role.COOP, Role.STORAGE, Role.BANK)  # sign-ups an admin must approve
ID_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # no 0/O or 1/I to misread


class Kyc(BaseModel):
    """What a sign-up registered, masked. The raw numbers are never stored; their HMAC digests stay in UserBook."""
    nid_last4: str
    phone_masked: str
    wallet_provider: Wallet
    wallet_masked: str
    registered_at: datetime
    verified: bool = Field(default=False, description="An admin approved the account.")


class User(BaseModel):
    user_id: str = Field(pattern=r"^[A-Z0-9-]{3,40}$")
    name: str = Field(min_length=2, max_length=60)
    role: Role
    district: str = Field(default="", max_length=40)
    title: str = Field(default="", max_length=80, description="What this account represents, e.g. 'Potato grower, Pirgachha'.")
    active: bool = True
    kyc: Kyc | None = None
    pending_review: bool = False
    self_registered: bool = False


def plain_number(value: object) -> object:
    """Bangla digits to ASCII, spaces and dashes dropped: '০১৭১১-২২৩ ৩৪৪' -> '01711223344'."""
    return re.sub(r"[\s\-\u2010-\u2015]", "", value.translate(BANGLA_DIGITS)) if isinstance(value, str) else value


def kyc_digest(kind: str, number: str) -> str:
    """HMAC-SHA256 of a national ID, phone or wallet number under the server's signing key (the one session tokens use)."""
    return hmac.new(settings.receipt_signing_key.encode(), f"kyc|{kind}|{number}".encode(), hashlib.sha256).hexdigest()


def mask_number(number: str) -> str:
    return f"{number[:3]}••••{number[-4:]}"


class Registration(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=60)
    role: Literal["farmer", "buyer", "driver", "coop", "storage", "bank"]
    district: str = Field(min_length=2, max_length=40)
    upazila: str = Field(default="", max_length=40)
    organization: str = Field(default="", max_length=80, description="Required for coop, storage and bank accounts.")
    phone: str = Field(pattern=r"^01[3-9][0-9]{8}$")
    nid: str = Field(pattern=r"^([0-9]{10}|[0-9]{13}|[0-9]{17})$")
    wallet_provider: Wallet
    wallet_number: str = Field(pattern=r"^01[3-9][0-9]{8}$")
    password: Annotated[str, StringConstraints(strip_whitespace=False, min_length=8, max_length=128)]
    consent: Literal[True]

    ascii_numbers = field_validator("phone", "nid", "wallet_number", mode="before")(plain_number)

    @model_validator(mode="after")
    def organization_for_institutions(self) -> Registration:
        if Role(self.role) in REVIEWED_ROLES and not self.organization:
            raise ValueError("organization is required for co-op, cold-storage and bank accounts")
        return self


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


class Registered(BaseModel):
    status: Literal["ACTIVE", "PENDING_REVIEW"]
    user: User
    session: Session | None


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
    """Accounts, their password hashes and sign-ups' KYC digests, kept in .state/users.json and written atomically on
    every change. Hashes and digests never leave this class: the API returns `User`, which has neither."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.users: dict[str, User] = {}
        self.password_hashes: dict[str, str] = {}
        self.kyc_digests: dict[str, dict[str, str]] = {}  # user_id -> {"nid", "phone", "wallet"}: HMAC hex digests
        if USERS_FILE.exists():
            records = json.loads(USERS_FILE.read_text(encoding="utf-8"))
            self.users = {r["user_id"]: User(**r) for r in records}
            demo_hash = hash_password(DEMO_PASSWORD)  # files written before passwords existed get the demo password
            self.password_hashes = {r["user_id"]: r.get("password_hash") or demo_hash for r in records}
            self.kyc_digests = {r["user_id"]: r["kyc_digests"] for r in records if r.get("kyc_digests")}
        else:
            self.reset()

    def _persist(self) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = USERS_FILE.with_suffix(".tmp")
        records = [{**u.model_dump(mode="json"), "password_hash": self.password_hashes[u.user_id],
                    **({"kyc_digests": self.kyc_digests[u.user_id]} if u.user_id in self.kyc_digests else {})}
                   for u in self.users.values()]
        tmp.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, USERS_FILE)

    def reset(self) -> list[User]:
        """Exactly the seeded accounts again: admin-created and self-registered accounts (and their KYC digests) go, so
        their national IDs and phone numbers can sign up again."""
        demo_hash = hash_password(DEMO_PASSWORD)
        with self._lock:
            self.users = {u.user_id: u.model_copy() for u in SEED_USERS}
            self.password_hashes = {u.user_id: demo_hash for u in SEED_USERS}
            self.kyc_digests = {}
            self._persist()
            return list(self.users.values())

    def authenticate(self, user_id: str, password: str | None) -> User:
        """The active account for this id (any case); with a password, only if it matches."""
        user = self.users.get(user_id.strip().upper())
        # A public host sets KNX_ADMIN_PASSWORD: admin accounts then need it, and neither quick login nor the published
        # demo password opens them. Unset (local runs), admins log in like every other demo account.
        admin_password = os.getenv("KNX_ADMIN_PASSWORD")
        if admin_password and user is not None and user.role is Role.ADMIN:
            if password is None or not hmac.compare_digest(password.encode(), admin_password.encode()):
                raise HTTPException(status_code=401, detail="Admin accounts need the admin password on this server.")
        elif password is not None:
            if user is None or not password_matches(password, self.password_hashes[user.user_id]):
                raise HTTPException(status_code=401, detail="Wrong account ID or password.")
        elif user is not None and user.self_registered:
            raise HTTPException(status_code=401, detail="Enter this account's password: quick login only opens the demo accounts.")
        if user is not None and user.pending_review:
            raise HTTPException(status_code=403, detail="This account is waiting for an admin to approve it.")
        if user is None or not user.active:
            raise HTTPException(status_code=403, detail="That account does not exist or is disabled.")
        return user

    def register(self, body: Registration) -> User:
        """A self-registered account: active for farmers, buyers and drivers, waiting for an admin for the others."""
        role = Role(body.role)
        digests = {"nid": kyc_digest("nid", body.nid), "phone": kyc_digest("phone", body.phone),
                   "wallet": kyc_digest("wallet", body.wallet_number)}
        password_hash = hash_password(body.password)  # slow on purpose, so outside the lock
        letters = re.sub(r"[^A-Z]", "", body.district.upper())
        district_code = "DHK" if letters.startswith("DHAKA") else letters[:3] if len(letters) >= 3 else "BGD"
        pending = role in REVIEWED_ROLES
        with self._lock:
            if sum(u.self_registered for u in self.users.values()) >= MAX_SELF_REGISTERED:
                raise HTTPException(status_code=429, detail="Sign-ups are paused on this demo node.")
            if any(d["nid"] == digests["nid"] for d in self.kyc_digests.values()):
                raise HTTPException(status_code=409, detail="An account with this national ID already exists.")
            if any(d["phone"] == digests["phone"] for d in self.kyc_digests.values()):
                raise HTTPException(status_code=409, detail="An account with this phone number already exists.")
            user_id = ""
            while not user_id or user_id in self.users:
                user_id = f"{ID_PREFIX[role]}-{district_code}-{''.join(secrets.choice(ID_ALPHABET) for _ in range(4))}"
            user = User(user_id=user_id, name=body.name, role=role, district=body.district,
                        title=", ".join(filter(None, (body.organization or role.value.capitalize(), body.upazila)))[:80],
                        active=not pending, pending_review=pending, self_registered=True,
                        kyc=Kyc(nid_last4=body.nid[-4:], phone_masked=mask_number(body.phone),
                                wallet_provider=body.wallet_provider, wallet_masked=mask_number(body.wallet_number),
                                registered_at=now_bdt()))
            self.users[user_id] = user
            self.password_hashes[user_id] = password_hash
            self.kyc_digests[user_id] = digests
            self._persist()
            return user

    def payout_wallet_matches(self, user: User, wallet: str, number: str) -> bool:
        """A sign-up's payouts go only to the wallet it registered; seeded and admin-made accounts have none to match."""
        if user.kyc is None:
            return True
        stored = self.kyc_digests.get(user.user_id, {}).get("wallet", "")
        return wallet == user.kyc.wallet_provider and hmac.compare_digest(kyc_digest("wallet", number), stored)

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
            if current.pending_review and patch.active:  # an admin approves a sign-up that was waiting
                updated = updated.model_copy(update={"pending_review": False, "kyc": current.kyc and current.kyc.model_copy(
                    update={"verified": True})})
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
            self.kyc_digests.pop(user_id, None)  # its national ID and phone can sign up again
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
    """Active demo accounts for the quick-login screen (never people's own sign-ups)."""
    return [u for u in USERS.users.values() if u.active and not u.self_registered]


@router.post("/register", response_model=Registered, status_code=201)
def register(body: Registration) -> Registered:  # sync: the password hash runs in a worker thread, off the event loop
    """Sign up with KYC. Farmers, buyers and drivers are active at once and get a session; co-op, cold-storage and bank
    accounts wait for an admin (PENDING_REVIEW, no session). 409 for a national ID or phone already registered."""
    user = USERS.register(body)
    if user.pending_review:
        return Registered(status="PENDING_REVIEW", user=user, session=None)
    return Registered(status="ACTIVE", user=user,
                      session=Session(token=issue_token(user.user_id), expires_in_s=TOKEN_TTL_SECONDS, user=user))


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
    """Change an account; `{"active": true}` on a sign-up waiting for review approves it (KYC marked verified)."""
    return USERS.update(user_id, body)


@admin.delete("/users/{user_id}")
async def delete_user(user_id: str) -> dict[str, str]:
    """Delete an account (for a sign-up waiting for review: reject it)."""
    USERS.delete(user_id)
    return {"deleted": user_id}


@admin.post("/users/reset", response_model=list[User])
async def reset_users() -> list[User]:
    """Restore exactly the seeded demo accounts; admin-created and self-registered accounts are removed."""
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
