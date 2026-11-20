"""In-app feedback: was this advice useful? The evidence a field test collects (docs/FIELD_TEST_KIT.md).

Anyone may send feedback; a logged-in account's id and role are attached from its token. Comments are PII-scrubbed
before they are stored, and only the latest MAX_ITEMS are kept, in .state/feedback.json. Admins read a summary.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

import auth
from automation.workflows import STATE_DIR
from config import now_bdt
from guardrails.pii_scrubber import PII_SCRUBBER

FEEDBACK_FILE = STATE_DIR / "feedback.json"
MAX_ITEMS = 5_000


class FeedbackIn(BaseModel):
    useful: bool
    comment: str = Field(default="", max_length=500)
    context: Literal["farmer_decision", "general"] = "farmer_decision"
    session_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9-]{3,60}$", description="The agent session rated.")
    lang: Literal["bn", "en"] = "bn"


class Feedback(FeedbackIn):
    feedback_id: str
    at: str
    user_id: str | None
    role: str | None
    pii_hidden: int = Field(description="Personal details removed from the comment before storing.")


class FeedbackSummary(BaseModel):
    total: int
    useful: int
    useful_pct: float | None
    by_role: dict[str, int]
    items: list[Feedback]


class FeedbackBook:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.items: list[Feedback] = []
        if FEEDBACK_FILE.exists():
            self.items = [Feedback(**f) for f in json.loads(FEEDBACK_FILE.read_text(encoding="utf-8"))]

    def add(self, body: FeedbackIn, user: auth.User | None) -> Feedback:
        scrub = PII_SCRUBBER.scrub(body.comment) if body.comment.strip() else None
        item = Feedback(**body.model_dump(exclude={"comment"}), comment=scrub.anonymized_text.strip() if scrub else "",
                        feedback_id=f"FB-{uuid.uuid4().hex[:10].upper()}", at=now_bdt().isoformat(),
                        user_id=user.user_id if user else None, role=user.role.value if user else None,
                        pii_hidden=len(scrub.entities) if scrub else 0)
        with self._lock:
            self.items = (self.items + [item])[-MAX_ITEMS:]
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            tmp = FEEDBACK_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps([f.model_dump() for f in self.items], ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, FEEDBACK_FILE)
        return item

    def summary(self, limit: int = 200) -> FeedbackSummary:
        items = list(self.items)
        useful = sum(f.useful for f in items)
        by_role: dict[str, int] = {}
        for f in items:
            by_role[f.role or "visitor"] = by_role.get(f.role or "visitor", 0) + 1
        return FeedbackSummary(total=len(items), useful=useful,
                               useful_pct=round(100 * useful / len(items), 1) if items else None,
                               by_role=by_role, items=items[::-1][:limit])


FEEDBACK = FeedbackBook()

router = APIRouter(prefix="/feedback", tags=["feedback"])
admin = APIRouter(prefix="/auth/admin", tags=["auth"], dependencies=[Depends(auth.admin_user)])


@router.post("", response_model=Feedback, status_code=201)
async def send_feedback(body: FeedbackIn, authorization: Annotated[str, Header()] = "") -> Feedback:
    """Rate an answer. A valid session token attaches the account; personal details in the comment are removed."""
    scheme, _, token = authorization.partition(" ")
    user = auth.user_from_token(token) if scheme.lower() == "bearer" else None
    return FEEDBACK.add(body, user)


@admin.get("/feedback", response_model=FeedbackSummary)
async def feedback_summary() -> FeedbackSummary:
    """Share rated useful, counts by role and the latest 200 items, newest first."""
    return FEEDBACK.summary()
