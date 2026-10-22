"""Presidio-compatible PII firewall for Bangladeshi farmer conversations.

Recognisers (each emits Presidio-style ``entity_type / start / end / score``):

* ``MFS_WALLET``    bKash / Nagad / Rocket / Upay wallet numbers (phone-shaped, keyword-anchored)
* ``BANK_ACCOUNT``  bank account numbers after an account keyword (English or Bangla)
* ``BD_PHONE``      +880 / 880 / 0 prefixed mobile numbers, operator prefix 013-019
* ``BD_NID``        National ID numbers in the 10, 13 and 17 digit formats
* ``PERSON``        self-introduced names ("আমার নাম করিম", "my name is Karim")

Bangla digits (০-৯) are detected exactly like ASCII digits: the text is
transliterated digit-for-digit into a same-length shadow copy, so match offsets
apply to the original string unchanged.

Original values never leave the process: they are kept in an in-memory
``PIIVault`` keyed by a vault id so a local settlement service can restore the
text (tokens are replaced in order of appearance).
"""

from __future__ import annotations

import hashlib
import re
import threading
import uuid
from collections import Counter
from dataclasses import dataclass

from pydantic import BaseModel, Field

_BANGLA_TO_ASCII = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

TOKENS: dict[str, str] = {
    "MFS_WALLET": "<MFS_WALLET_REDACTED>",
    "BANK_ACCOUNT": "<BANK_ACCOUNT_REDACTED>",
    "BD_PHONE": "<BD_PHONE_REDACTED>",
    "BD_NID": "<BD_NID_REDACTED>",
    "PERSON": "<PERSON_REDACTED>",
}

_PHONE_CORE = r"(?:\+?88[\s-]?)?0[\s-]?1[3-9]\d{2}[\s-]?\d{3}[\s-]?\d{3}"
_MFS_PATTERN = re.compile(
    r"(?i)(?:bkash|b-kash|বিকাশ|nagad|নগদ|rocket|রকেট|upay|উপায়)"
    r"[\s:#\-–]*(?:(?:personal|agent|wallet|account|acc|a/c|no\.?|number|নম্বর|নাম্বার|নং|পার্সোনাল|এজেন্ট)[\s:#\-–]*)*"
    r"(?P<value>" + _PHONE_CORE + r"\d?)(?!\d)"
)
_BANK_PATTERN = re.compile(
    r"(?i)(?:a/c|acc(?:ount)?|bank\s*account|হিসাব|ব্যাংক\s*হিসাব|অ্যাকাউন্ট)"
    r"(?:\s*(?:no\.?|number|নং|নম্বর))?"
    r"[\s:#\-–]*(?P<value>\d[\d\- ]{8,22}\d)(?!\d)"
)
_PHONE_PATTERN = re.compile(r"(?<![\d+])(?P<value>" + _PHONE_CORE + r")(?!\d)")
_NID_PATTERN = re.compile(r"(?<!\d)(?P<value>\d{17}|\d{13}|\d{10})(?!\d)")
_NID_CONTEXT = re.compile(r"(?i)(nid|national\s*id|এনআইডি|জাতীয়\s*পরিচয়|পরিচয়পত্র|smart\s*card)")
_PERSON_PATTERN = re.compile(
    r"(?i)(?:আমার\s+নাম|আমি\s+মোঃ|my\s+name\s+is|i\s+am)\s+(?P<value>(?:মোঃ\s*|md\.?\s*)?[^\s,।.!?০-৯\d]{2,20})"
)

# Higher priority wins when spans overlap; ties go to the higher score, then the longer span.
_PRIORITY: dict[str, int] = {"MFS_WALLET": 5, "BANK_ACCOUNT": 4, "BD_PHONE": 3, "BD_NID": 2, "PERSON": 1}


class ScrubbedEntity(BaseModel):
    entity_type: str
    start: int = Field(description="Start offset in the original text.")
    end: int = Field(description="End offset (exclusive) in the original text.")
    score: float = Field(ge=0, le=1)
    token: str
    masked_preview: str = Field(description="Partially masked value for audit, never the full value.")
    fingerprint: str = Field(description="SHA-256 prefix of the normalised value, for de-duplication.")
    recognizer: str


class ScrubResult(BaseModel):
    anonymized_text: str
    entities: list[ScrubbedEntity]
    entity_counts: dict[str, int]
    vault_id: str | None = Field(description="Reversible vault handle; None when nothing was redacted.")
    pii_found: bool


@dataclass(frozen=True, slots=True)
class _Candidate:
    entity_type: str
    start: int
    end: int
    score: float
    recognizer: str


def _mask(value: str) -> str:
    digits = re.sub(r"\D", "", value.translate(_BANGLA_TO_ASCII))
    if len(digits) >= 6:
        return f"{digits[:3]}{'*' * (len(digits) - 5)}{digits[-2:]}"
    return value[:1] + "*" * max(1, len(value) - 1)


def _fingerprint(entity_type: str, value: str) -> str:
    normalised = re.sub(r"[\s\-+]", "", value.translate(_BANGLA_TO_ASCII)).lower()
    return hashlib.sha256(f"{entity_type}:{normalised}".encode()).hexdigest()[:16]


class PIIVault:
    """In-memory reversible mapping from redaction tokens back to original values."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, list[tuple[str, str]]] = {}

    def store(self, entries: list[tuple[str, str]]) -> str:
        vault_id = f"VLT-{uuid.uuid4().hex[:12].upper()}"
        with self._lock:
            self._entries[vault_id] = entries
        return vault_id

    def restore(self, vault_id: str, anonymized_text: str) -> str:
        with self._lock:
            entries = self._entries.get(vault_id)
        if entries is None:
            raise KeyError(f"unknown vault id {vault_id}")
        restored = anonymized_text
        for token, original in entries:
            restored = restored.replace(token, original, 1)
        return restored

    def purge(self, vault_id: str) -> bool:
        with self._lock:
            return self._entries.pop(vault_id, None) is not None


class BanglaPIIScrubber:
    """Regex + context recogniser stack emitting Presidio ``RecognizerResult``-shaped entities."""

    def __init__(self, vault: PIIVault | None = None, min_score: float = 0.5) -> None:
        self.vault = vault or PIIVault()
        self.min_score = min_score

    def analyze(self, text: str) -> list[_Candidate]:
        shadow = text.translate(_BANGLA_TO_ASCII)
        found: list[_Candidate] = []
        for match in _MFS_PATTERN.finditer(shadow):
            found.append(_Candidate("MFS_WALLET", match.start("value"), match.end("value"), 0.95, "MfsKeywordRecognizer"))
        for match in _BANK_PATTERN.finditer(shadow):
            found.append(_Candidate("BANK_ACCOUNT", match.start("value"), match.end("value"), 0.85, "BankKeywordRecognizer"))
        for match in _PHONE_PATTERN.finditer(shadow):
            found.append(_Candidate("BD_PHONE", match.start("value"), match.end("value"), 0.85, "BdMobileRecognizer"))
        for match in _NID_PATTERN.finditer(shadow):
            value = match.group("value")
            window = shadow[max(0, match.start() - 30) : match.start()]
            score = 0.9 if _NID_CONTEXT.search(window) else 0.6
            if len(value) == 17 and not 1900 <= int(value[:4]) <= 2030:
                score -= 0.2  # 17-digit NIDs start with the holder's birth year
            if len(value) == 13 and value.startswith("8801") and score < 0.9:
                continue  # 880-prefixed mobile number without the leading '+'
            found.append(_Candidate("BD_NID", match.start("value"), match.end("value"), round(score, 2), "BdNidRecognizer"))
        for match in _PERSON_PATTERN.finditer(text):
            found.append(_Candidate("PERSON", match.start("value"), match.end("value"), 0.7, "SelfIntroductionRecognizer"))
        return self._resolve_overlaps([c for c in found if c.score >= self.min_score])

    @staticmethod
    def _resolve_overlaps(candidates: list[_Candidate]) -> list[_Candidate]:
        ordered = sorted(candidates, key=lambda c: (-_PRIORITY[c.entity_type], -c.score, -(c.end - c.start)))
        kept: list[_Candidate] = []
        for candidate in ordered:
            if all(candidate.end <= k.start or candidate.start >= k.end for k in kept):
                kept.append(candidate)
        return sorted(kept, key=lambda c: c.start)

    def scrub(self, text: str) -> ScrubResult:
        candidates = self.analyze(text)
        pieces: list[str] = []
        cursor = 0
        entities: list[ScrubbedEntity] = []
        vault_entries: list[tuple[str, str]] = []
        for c in candidates:
            original = text[c.start : c.end]
            token = TOKENS[c.entity_type]
            pieces.append(text[cursor : c.start])
            pieces.append(token)
            cursor = c.end
            vault_entries.append((token, original))
            entities.append(
                ScrubbedEntity(
                    entity_type=c.entity_type,
                    start=c.start,
                    end=c.end,
                    score=c.score,
                    token=token,
                    masked_preview=_mask(original),
                    fingerprint=_fingerprint(c.entity_type, original),
                    recognizer=c.recognizer,
                )
            )
        pieces.append(text[cursor:])
        return ScrubResult(
            anonymized_text="".join(pieces),
            entities=entities,
            entity_counts=dict(Counter(e.entity_type for e in entities)),
            vault_id=self.vault.store(vault_entries) if vault_entries else None,
            pii_found=bool(entities),
        )


PII_SCRUBBER = BanglaPIIScrubber()
