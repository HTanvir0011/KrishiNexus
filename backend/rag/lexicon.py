"""Bangla / dialect / Banglish lexicon shared by retrieval, HyDE rewriting and memory.

Maps informal farmer speech (Standard Bangla, Rangpuri, Bogura Varendri, Sylheti and
romanised Banglish) onto canonical English agronomic concepts, crops and districts so
lexical (BM25) and dense retrieval work over an English-language knowledge base.
"""

from __future__ import annotations

import re
from collections import Counter

from schemas.mcp_models import Crop

BANGLA_TO_ASCII_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

# Surface form (Bangla, dialect or Banglish) -> canonical English concept tokens.
CONCEPT_LEXICON: dict[str, str] = {
    # storage and spoilage
    "কোল্ড স্টোরেজ": "cold storage", "কোল্ডস্টোরেজ": "cold storage", "হিমাগার": "cold storage",
    "হিমঘর": "cold storage", "cold storage": "cold storage", "himagar": "cold storage",
    "তাপমাত্রা": "temperature", "টেম্পারেচার": "temperature", "ঠান্ডা": "temperature cooling",
    "আর্দ্রতা": "humidity", "আদ্রতা": "humidity", "ভাপ": "humidity",
    "পচবে": "rot spoilage", "পচে": "rot spoilage", "পচা": "rot spoilage", "পচি": "rot spoilage",
    "পচন": "rot spoilage", "নষ্ট": "spoilage loss", "pocha": "rot spoilage", "poche": "rot spoilage",
    "রাখলে": "store storage", "রাখমু": "store storage", "রাখুম": "store storage", "রাখতাম": "store storage",
    "রাখব": "store storage", "মজুদ": "store storage",
    # selling and markets
    "বেচব": "sell market", "বেচমু": "sell market", "বেচুম": "sell market", "ব্যাচমু": "sell market",
    "বেচতাম": "sell market", "বেচি": "sell market", "বিক্রি": "sell market", "বেচা": "sell market",
    "becbo": "sell market", "bechbo": "sell market", "bikri": "sell market",
    "দাম": "price", "বাজারদর": "price", "dam": "price", "koto": "price", "কত টাকা": "price",
    "সিন্ডিকেট": "syndicate intermediary", "ফড়িয়া": "faria intermediary", "ফরিয়া": "faria intermediary",
    "দালাল": "intermediary middleman", "আড়তদার": "aratdar intermediary", "আড়ৎ": "arat wholesale",
    "আড়ত": "arat wholesale", "পাইকার": "paiker wholesale", "বেপারী": "bepari intermediary",
    "বাজার": "market", "হাট": "market haat",
    "কোটা": "quota", "ব্যবসায়ী": "trader", "ভাড়া": "tariff fee",
    "জায়গা": "space", "জায়গা": "space",
    # credit
    "ঋণ": "credit loan", "লোন": "credit loan", "টাকা ধার": "credit loan", "কর্জ": "credit loan",
    # disease and chemicals
    "ধসা": "late blight", "নাবি ধসা": "late blight", "মড়ক": "late blight disease", "ব্লাইট": "blight",
    "রোগ": "disease", "পোকা": "pest insect", "কীটনাশক": "pesticide", "বিষ": "pesticide",
    "ছত্রাকনাশক": "fungicide", "ফরমালিন": "formalin", "কার্বাইড": "calcium carbide",
    "dhosha": "late blight", "dhosa": "late blight", "nabi dhosha": "late blight", "blight": "blight",
    "rog": "disease", "poka": "pest insect", "bish": "pesticide", "oshudh": "pesticide fungicide",
    "oshud": "pesticide fungicide", "ঔষধ": "pesticide fungicide", "ওষুধ": "pesticide fungicide",
    # flood and weather
    "বন্যা": "flood", "ঢল": "flash flood", "পাহাড়ি ঢল": "flash flood", "পানি আইতাছে": "flood water rising",
    "বাঁধ": "embankment", "বাধ": "embankment", "বৃষ্টি": "rain", "ঝড়": "storm",
    "ধান কাটা": "harvest", "কাটমু": "harvest", "কাটব": "harvest",
    # transport
    "ট্রাক": "truck transport", "গাড়ি": "transport", "পরিবহন": "transport",
}

DIALECT_MARKERS: dict[str, tuple[str, ...]] = {
    "Rangpuri": ("বাহে", "কোনঠে", "মুই", "হামরা", "হামার", "কাইল", "নাগবে", "পচি যাইবে", "যাইবে"),
    "Bogura (Varendri)": ("ক্যাংকা", "লিবে", "ব্যাচমু", "হামাক", "কোটে", "কতিবা"),
    "Sylheti": ("কিতা", "অখন", "বেচতাম", "আইতাছে", "খিতা", "ফানি", "হকল", "বাড়িত"),
    "Banglish": ("alu", "aloo", "koto", "dam", "becbo", "bechbo", "kothay", "pocha"),
}

DIALECT_NORMALIZATION: dict[str, str] = {
    "কোনঠে": "কোথায়", "কোটে": "কোথায়", "মুই": "আমি", "হামরা": "আমরা", "হামার": "আমাদের",
    "কাইল": "কাল", "নাগবে": "লাগবে", "পচি যাইবে": "পচে যাবে", "যাইবে": "যাবে", "ক্যাংকা": "কেমন",
    "লিবে": "নেবে", "ব্যাচমু": "বেচব", "বেচমু": "বেচব", "বেচুম": "বেচব", "কিতা": "কী", "খিতা": "কী",
    "অখন": "এখন", "বেচতাম": "বেচব", "আইতাছে": "আসছে", "ফানি": "পানি", "হকল": "সকল", "রাখমু": "রাখব",
    "রাখুম": "রাখব", "কাটমু": "কাটব", "বাহে": "",
}

CROP_TERMS: dict[str, Crop] = {
    "কার্ডিনাল": Crop.CARDINAL_POTATO, "cardinal": Crop.CARDINAL_POTATO,
    "ডায়মন্ড": Crop.DIAMANT_POTATO, "ডায়মন্ট": Crop.DIAMANT_POTATO, "diamant": Crop.DIAMANT_POTATO,
    "আলু": Crop.CARDINAL_POTATO, "alu": Crop.CARDINAL_POTATO, "aloo": Crop.CARDINAL_POTATO, "potato": Crop.CARDINAL_POTATO,
    "কাঁচা মরিচ": Crop.GREEN_CHILI, "মরিচ": Crop.GREEN_CHILI, "morich": Crop.GREEN_CHILI, "chili": Crop.GREEN_CHILI,
    "chilli": Crop.GREEN_CHILI, "বেগুন": Crop.BRINJAL, "begun": Crop.BRINJAL, "brinjal": Crop.BRINJAL,
    "eggplant": Crop.BRINJAL, "বোরো": Crop.BORO_RICE, "ধান": Crop.BORO_RICE, "boro": Crop.BORO_RICE,
    "paddy": Crop.BORO_RICE, "rice": Crop.BORO_RICE,
}

DISTRICT_TERMS: dict[str, str] = {
    "মুন্সিগঞ্জ": "Munshiganj", "munshiganj": "Munshiganj", "বিক্রমপুর": "Munshiganj",
    "বগুড়া": "Bogura", "বগুরা": "Bogura", "bogura": "Bogura", "bogra": "Bogura",
    "রংপুর": "Rangpur", "rangpur": "Rangpur", "ঠাকুরগাঁও": "Thakurgaon", "thakurgaon": "Thakurgaon",
    "কুড়িগ্রাম": "Kurigram", "kurigram": "Kurigram", "যশোর": "Jessore", "jessore": "Jessore", "jashore": "Jessore",
    "সুনামগঞ্জ": "Sunamganj", "sunamganj": "Sunamganj", "কিশোরগঞ্জ": "Kishoreganj", "kishoreganj": "Kishoreganj",
    "নেত্রকোনা": "Netrokona", "netrokona": "Netrokona", "সিলেট": "Sylhet", "sylhet": "Sylhet",
    "কারওয়ান বাজার": "Dhaka Karwan Bazar", "কাওরান বাজার": "Dhaka Karwan Bazar", "ঢাকা": "Dhaka Karwan Bazar",
    "dhaka": "Dhaka Karwan Bazar", "karwan bazar": "Dhaka Karwan Bazar", "মিরপুর": "Dhaka Mirpur",
    "কক্সবাজার": "Cox's Bazar", "cox's bazar": "Cox's Bazar",
}

_TOKEN_RE = re.compile(r"[ঀ-৿]+|[a-z0-9]+(?:\.[0-9]+)?", re.IGNORECASE)


def _contains(text: str, term: str) -> bool:
    if term.isascii():
        return re.search(rf"\b{re.escape(term)}\b", text) is not None
    return term in text


def normalize_dialect(text: str) -> str:
    out = text
    for dialect_form, standard in sorted(DIALECT_NORMALIZATION.items(), key=lambda kv: -len(kv[0])):
        out = out.replace(dialect_form, standard)
    return re.sub(r"\s{2,}", " ", out).strip()


def detect_dialect(text: str) -> tuple[str, dict[str, int]]:
    lowered = text.lower()
    scores = {name: sum(_contains(lowered, m) for m in markers) for name, markers in DIALECT_MARKERS.items()}
    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        has_bangla = any("ঀ" <= ch <= "৿" for ch in text)
        return ("Standard Bangla" if has_bangla else "English"), scores
    return best, scores


def concepts_in(text: str) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for surface, concept in sorted(CONCEPT_LEXICON.items(), key=lambda kv: -len(kv[0])):
        if _contains(lowered, surface.lower()):
            found.extend(concept.split())
    return list(dict.fromkeys(found))


def detect_crop(text: str) -> Crop | None:
    lowered = text.lower()
    for term, crop in sorted(CROP_TERMS.items(), key=lambda kv: -len(kv[0])):
        if _contains(lowered, term.lower()):
            return crop
    return None


def detect_district(text: str) -> str | None:
    lowered = text.lower()
    for term, district in sorted(DISTRICT_TERMS.items(), key=lambda kv: -len(kv[0])):
        if _contains(lowered, term.lower()):
            return district
    return None


def tokenize(text: str, expand_concepts: bool = True) -> list[str]:
    """Lowercased word tokens (Bangla digits as ASCII) plus English concept expansions."""
    normalized = text.translate(BANGLA_TO_ASCII_DIGITS).lower()
    tokens = _TOKEN_RE.findall(normalized)
    if expand_concepts:
        tokens.extend(concepts_in(text))
        crop = detect_crop(text)
        if crop is not None:
            tokens.extend(crop.value.lower().split())
    return tokens


def token_counts(text: str) -> Counter[str]:
    return Counter(tokenize(text))
