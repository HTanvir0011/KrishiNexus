"""Bangla dialect voice pipeline: speech-to-text, dialect normalisation, entity extraction and SSML.

Speech-to-text runs on-device with ``faster-whisper`` when ``KNX_WHISPER_MODEL`` names a Whisper
checkpoint (for example a ``shhossain/whisper_bangla_models`` conversion) and the package is installed.
Without it the node accepts typed Bangla/Banglish text or one of five recorded-farmer presets.

The normaliser maps Rangpuri, Bogura (Varendri), Sylheti, Chittagonian and Standard Bangla speech onto
agronomic entities: number words ("দশ মণ", "একশো পঁচিশ টাকা") become numbers only when attached to a
unit or price, local units (mon/maund = 40 kg, bosta = 50 kg, ser, palla; acre/bigha/shotok land areas)
become kilograms, local varieties map to crops, and local middleman terms are recognised.
Responses are rendered as SSML with IPA phoneme hints for rural text-to-speech playback.
"""

from __future__ import annotations

import base64
import binascii
import importlib.util
import io
import os
import re
from typing import Any, Literal
from xml.sax.saxutils import escape, quoteattr

from pydantic import BaseModel, ConfigDict, Field

from guardrails.pii_scrubber import PII_SCRUBBER
from mcp_servers import bd_geo
from mcp_servers.base import ToolExecutionError
from rag.lexicon import concepts_in, detect_crop, detect_dialect, detect_district, normalize_dialect
from schemas.mcp_models import Crop

WHISPER_REFERENCE = "shhossain/whisper_bangla_models (Whisper fine-tunes for Bangla)"
_DIGITS_BN = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
_DIGITS_ASCII = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

DialectName = Literal["Rangpuri", "Bogura (Varendri)", "Sylheti", "Chittagonian", "Standard Bangla", "Banglish", "English"]


class VoicePreset(BaseModel):
    preset_id: str
    title: str
    dialect: DialectName
    farmer_id: str
    district: str
    upazila: str
    audio_duration_s: float
    transcript: str


VOICE_PRESETS: dict[str, VoicePreset] = {p.preset_id: p for p in (
    VoicePreset(preset_id="rangpur_potato_distress", title="Rangpuri potato distress sale", dialect="Rangpuri",
                farmer_id="FARM-RAN-212", district="Rangpur", upazila="Mithapukur", audio_duration_s=14.2,
                transcript="বাহে, মুই মিঠাপুকুরের রহিম মিয়া, মোবাইল ০১৭১৫৫৫৬৬৭৭। হামার ঘরত দশ মণ লাল পাকরি আলু আছে। "
                           "ফড়িয়া কয় বারো টাকা কেজি দিবে। এলা বেচমু না হিমাগারত থুমু? আলু পচি যাইবে কিনা চিন্তাত আছোঁ।"),
    VoicePreset(preset_id="bogura_chili_syndicate", title="Bogura green chili syndicate", dialect="Bogura (Varendri)",
                farmer_id="FARM-BOG-318", district="Bogura", upazila="Sariakandi", audio_duration_s=11.6,
                transcript="হামি সারিয়াকান্দির করিম, দুই মণ কাঁচা মরিচ তুলিছি। পাইকার পঞ্চাশ টাকা কেজি দিবার চায়, অথচ "
                           "ঢাকাত মরিচ একশো পঁচিশ টাকা। সিন্ডিকেট ছাড়া ক্যাংকা করি সরাসরি ব্যাচমু?"),
    VoicePreset(preset_id="sunamganj_haor_flood", title="Sunamganj haor flash-flood Boro", dialect="Sylheti",
                farmer_id="FARM-SUN-077", district="Sunamganj", upazila="Tahirpur", audio_duration_s=12.8,
                transcript="আমি তাহিরপুরর কৃষক আব্দুল, আমার নম্বর ০১৮১২৩৪৫৬৭৮। হাওরো বোরো ধান পাকি গেছে, পাহাড়ি ঢল "
                           "আইতাছে হুনছি। চাইর একর জমির ধান কিতা করমু? অখন কাটমু নি?"),
    VoicePreset(preset_id="munshiganj_cold_storage", title="Munshiganj cold-storage quota", dialect="Standard Bangla",
                farmer_id="FARM-MUN-045", district="Munshiganj", upazila="Tongibari", audio_duration_s=13.5,
                transcript="আমি টঙ্গিবাড়ীর কৃষক, আমার পঞ্চাশ মণ ডায়মন্ড আলু আছে। হিমাগারে জায়গা পাচ্ছি না, সব জায়গা "
                           "ব্যবসায়ীরা নিয়ে নিয়েছে। বেপারী চৌদ্দ টাকা কেজি বলছে। সমিতির মাধ্যমে হিমাগারে জায়গা পাওয়া যাবে?"),
    VoicePreset(preset_id="jessore_brinjal_pooling", title="Jessore brinjal truck pooling", dialect="Standard Bangla",
                farmer_id="FARM-JES-129", district="Jessore", upazila="Jhikargacha", audio_duration_s=10.9,
                transcript="ঝিকরগাছা থেকে বলছি, আমার আট মণ বেগুন আছে। একা ট্রাক ভাড়া করলে পোষায় না। পাশের গ্রামের "
                           "চাষিদের সাথে মিলে ঢাকায় পাঠাতে চাই, আড়তদার বত্রিশ টাকা দিচ্ছে।"),
)}

# ---------------------------------------------------------------------------
# Dialect vocabulary
# ---------------------------------------------------------------------------

CHITTAGONIAN_MARKERS = ("আঁই", "আঁরা", "কিল্লাই", "অনে", "গরিবার", "গরির", "বেচিত")
VOICE_NORMALIZATION: dict[str, str] = {
    # Rangpuri
    "থুমু": "রাখব", "এলা": "এখন", "চিন্তাত": "চিন্তায়", "ঘরত": "ঘরে", "হিমাগারত": "হিমাগারে", "আছোঁ": "আছি", "কয়": "বলে",
    "দিবে": "দেবে",
    # Bogura (Varendri)
    "হামি": "আমি", "তুলিছি": "তুলেছি", "ক্যাংকা করি": "কীভাবে", "দিবার": "দিতে", "ঢাকাত": "ঢাকায়",
    # Sylheti
    "তাহিরপুরর": "তাহিরপুরের", "হাওরো": "হাওরে", "পাকি গেছে": "পেকে গেছে", "চাইর": "চার", "হুনছি": "শুনেছি", "নি?": "কি?",
    "করমু": "করব",
    # Chittagonian
    "আঁই": "আমি", "আঁরা": "আমরা", "কিল্লাই": "কেন", "অনে": "আপনি", "গরিবার": "করতে", "গরির": "করছি", "বেচিত": "বেচতে",
}
LOCAL_CROP_TERMS: dict[str, Crop] = {
    "লাল পাকরি": Crop.CARDINAL_POTATO, "শিল বিলাতি": Crop.CARDINAL_POTATO, "লাল আলু": Crop.CARDINAL_POTATO,
    "গোল আলু": Crop.CARDINAL_POTATO, "সাদা আলু": Crop.DIAMANT_POTATO, "ডায়মন্ড": Crop.DIAMANT_POTATO,
    "লঙ্কা": Crop.GREEN_CHILI, "ঝাল": Crop.GREEN_CHILI, "মরিচ": Crop.GREEN_CHILI, "বাইগন": Crop.BRINJAL, "বাগুন": Crop.BRINJAL,
    "বুরো": Crop.BORO_RICE,
}
MIDDLEMAN_TERMS: dict[str, str] = {
    "ফড়িয়া": "Faria", "ফরিয়া": "Faria", "দালাল": "Faria", "বেপারী": "Bepari", "ব্যাপারী": "Bepari", "পাইকার": "Paiker",
    "আড়তদার": "Aratdar", "আড়ৎদার": "Aratdar", "মহাজন": "Mohajon (trader-lender)", "কয়াল": "Koyal (market weighman)",
}
WEIGHT_UNITS_KG: dict[str, float] = {
    "মণ": 40.0, "মন": 40.0, "mon": 40.0, "maund": 40.0, "বস্তা": 50.0, "bosta": 50.0, "কেজি": 1.0, "kg": 1.0,
    "টন": 1000.0, "ton": 1000.0, "সের": 0.933, "পাল্লা": 5.0,
}
AREA_UNITS_HA: dict[str, float] = {"একর": 0.4047, "acre": 0.4047, "বিঘা": 0.1338, "bigha": 0.1338, "শতক": 0.004047,
                                   "ডেসিমাল": 0.004047}
YIELD_T_PER_HA: dict[Crop, float] = {Crop.BORO_RICE: 4.2, Crop.CARDINAL_POTATO: 22.0, Crop.DIAMANT_POTATO: 22.0,
                                     Crop.GREEN_CHILI: 9.0, Crop.BRINJAL: 18.0}
UPAZILA_BN: dict[str, str] = {
    "মিঠাপুকুর": "Mithapukur", "বদরগঞ্জ": "Badarganj", "কাউনিয়া": "Kaunia", "সারিয়াকান্দি": "Sariakandi", "শিবগঞ্জ": "Shibganj",
    "শেরপুর": "Sherpur", "কাহালু": "Kahaloo", "গাবতলী": "Gabtali", "শাজাহানপুর": "Shajahanpur", "তাহিরপুর": "Tahirpur",
    "ধর্মপাশা": "Dharmapasha", "জামালগঞ্জ": "Jamalganj", "দিরাই": "Derai", "শাল্লা": "Shalla", "ইটনা": "Itna",
    "মিঠামইন": "Mithamain", "অষ্টগ্রাম": "Austagram", "নিকলী": "Nikli", "খালিয়াজুরী": "Khaliajuri", "মোহনগঞ্জ": "Mohanganj",
    "মদন": "Madan", "টঙ্গিবাড়ী": "Tongibari", "সিরাজদিখান": "Sirajdikhan", "শ্রীনগর": "Sreenagar", "লৌহজং": "Lohajang",
    "ঝিকরগাছা": "Jhikargacha", "চৌগাছা": "Chaugachha", "মণিরামপুর": "Manirampur", "রাণীশংকৈল": "Ranisankail",
    "বালিয়াডাঙ্গী": "Baliadangi", "হরিপুর": "Haripur", "উলিপুর": "Ulipur", "চিলমারী": "Chilmari",
}

NUMBER_WORDS: dict[str, int] = {
    "এক": 1, "দুই": 2, "দু": 2, "তিন": 3, "চার": 4, "পাঁচ": 5, "ছয়": 6, "সাত": 7, "আট": 8, "নয়": 9, "দশ": 10, "এগারো": 11,
    "বারো": 12, "তেরো": 13, "চৌদ্দ": 14, "পনেরো": 15, "ষোলো": 16, "সতেরো": 17, "আঠারো": 18, "উনিশ": 19, "বিশ": 20,
    "একুশ": 21, "বাইশ": 22, "তেইশ": 23, "চব্বিশ": 24, "পঁচিশ": 25, "ছাব্বিশ": 26, "সাতাশ": 27, "আঠাশ": 28, "ঊনত্রিশ": 29,
    "ত্রিশ": 30, "একত্রিশ": 31, "বত্রিশ": 32, "তেত্রিশ": 33, "চৌত্রিশ": 34, "পঁয়ত্রিশ": 35, "ছত্রিশ": 36, "সাঁইত্রিশ": 37,
    "আটত্রিশ": 38, "ঊনচল্লিশ": 39, "চল্লিশ": 40, "পঁয়তাল্লিশ": 45, "পঞ্চাশ": 50, "পঞ্চান্ন": 55, "ষাট": 60, "পঁয়ষট্টি": 65,
    "সত্তর": 70, "পঁচাত্তর": 75, "আশি": 80, "পঁচাশি": 85, "নব্বই": 90, "পঁচানব্বই": 95, "একশো": 100, "একশ": 100,
}
_UNIT_AFTER_NUMBER = ("মণ", "মন", "কেজি", "টাকা", "একর", "বিঘা", "শতক", "টন", "বস্তা", "সের", "পাল্লা", "ডেসিমাল")


def _word_value(token: str) -> tuple[int, str] | None:
    """(value, kind) for a number word; kind is 'unit', 'hundred' (x100) or 'thousand' (x1000)."""
    if token in NUMBER_WORDS:
        return NUMBER_WORDS[token], "unit"
    for suffix in ("শো", "শ"):
        if token.endswith(suffix) and token[: -len(suffix)] in NUMBER_WORDS:
            return NUMBER_WORDS[token[: -len(suffix)]] * 100, "unit"
    if token == "হাজার":
        return 1000, "thousand"
    return None


def digitize_numbers(text: str) -> str:
    """Replace Bangla number-word runs by Bangla digits when they quantify a unit or price."""
    tokens = re.split(r"(\s+)", text)
    out: list[str] = []
    i = 0
    while i < len(tokens):
        if not tokens[i].strip():
            out.append(tokens[i])
            i += 1
            continue
        j, total, current, consumed = i, 0, 0, False
        while j < len(tokens):
            word = tokens[j].strip()
            if not word:
                j += 1
                continue
            parsed = _word_value(word)
            if parsed is None:
                break
            value, kind = parsed
            if kind == "thousand":
                total += max(current, 1) * 1000
                current = 0
            else:
                current += value
            consumed = True
            j += 1
        next_word = next((t.strip() for t in tokens[j:] if t.strip()), "")
        if consumed and next_word.startswith(_UNIT_AFTER_NUMBER):
            out.append(str(total + current).translate(_DIGITS_BN))
            while j > i and not tokens[j - 1].strip():
                j -= 1
            i = j
        else:
            out.append(tokens[i])
            i += 1
    return "".join(out)


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


class VoiceEntities(BaseModel):
    crop: Crop | None
    crop_local_term: str | None
    quantity_kg: float | None
    quantity_expression: str | None
    district: str | None
    upazila: str | None
    offered_faria_price_bdt: float | None
    middleman_role: str | None
    intent: str
    concepts: list[str]


class TranscriptionResult(BaseModel):
    source: Literal["preset", "text", "audio"]
    preset_id: str | None
    stt_backend: str
    stt_model_reference: str
    dialect: str
    dialect_scores: dict[str, int]
    dialect_hint_used: bool
    farmer_id: str | None
    raw_transcript: str
    scrubbed_transcript: str
    pii_entities: list[str]
    normalized_text: str
    entities: VoiceEntities
    asr_confidence: float
    audio_duration_s: float | None


class PronunciationEntry(BaseModel):
    term: str
    ipa: str
    romanized: str


class VoiceScript(BaseModel):
    text_bn: str
    ssml: str
    voice: str
    pronunciation_guide: list[PronunciationEntry]
    estimated_duration_s: float


PHONETIC_GUIDE: dict[str, tuple[str, str]] = {
    "ফড়িয়া": ("pʰɔɽija", "phoriya"), "হিমাগার": ("ɦimaɡaɾ", "himagar"), "আড়তদার": ("aɽɔt̪d̪aɾ", "arotdar"),
    "সিন্ডিকেট": ("sindikeʈ", "syndicate"), "সনদ": ("ʃɔnɔd̪", "shonod"), "ঋণ": ("ɾin", "rin"),
    "কার্ডিনাল": ("kaɾɖinal", "cardinal"), "কম্বাইন": ("kɔmbain", "combine"), "হাওর": ("ɦaoɾ", "haor"),
    "উৎপাদন": ("ut̪pad̪ɔn", "utpadon"), "যৌথ": ("dʒout̪ʰo", "jowtho"),
}


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

_WHISPER: Any = None


def _transcribe_audio(audio_base64: str) -> tuple[str, str, float, float | None]:
    model_name = os.getenv("KNX_WHISPER_MODEL")
    if not model_name or importlib.util.find_spec("faster_whisper") is None:
        raise ToolExecutionError(
            "Audio transcription needs an on-device Whisper model: pip install faster-whisper and set KNX_WHISPER_MODEL "
            "(e.g. a CTranslate2 conversion of a whisper_bangla_models checkpoint). Send 'text' or 'preset_id' instead."
        )
    data = audio_base64.split(",", 1)[1] if audio_base64.startswith("data:") else audio_base64
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ToolExecutionError("audio_base64 is not valid base64.") from exc
    global _WHISPER
    from faster_whisper import WhisperModel

    if _WHISPER is None:
        _WHISPER = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, info = _WHISPER.transcribe(io.BytesIO(raw), language="bn", beam_size=5)
    text = " ".join(segment.text.strip() for segment in segments)
    return text, f"faster-whisper:{model_name} (int8, CPU)", float(info.language_probability), float(info.duration)


def _detect_dialect(text: str, hint: str | None) -> tuple[str, dict[str, int], bool]:
    dialect, scores = detect_dialect(text)
    scores = {**scores, "Chittagonian": sum(m in text for m in CHITTAGONIAN_MARKERS)}
    if scores["Chittagonian"] > max(v for k, v in scores.items() if k != "Chittagonian"):
        dialect = "Chittagonian"
    if hint:
        return hint, scores, True
    return dialect, scores, False


def _quantity(text: str, crop: Crop | None) -> tuple[float | None, str | None]:
    ascii_text = text.translate(_DIGITS_ASCII)
    units = "|".join(sorted((re.escape(u) for u in WEIGHT_UNITS_KG), key=len, reverse=True))
    weight = re.search(rf"(\d+(?:\.\d+)?)\s*({units})(?!\s*(?:টাকা|দাম))", ascii_text, re.IGNORECASE)
    if weight and not re.match(r"\s*(?:টাকা)", ascii_text[weight.end():]):
        unit = weight.group(2).lower()
        if not (unit in ("কেজি", "kg") and re.search(r"টাকা\s*$", ascii_text[: weight.start()])):
            return round(float(weight.group(1)) * WEIGHT_UNITS_KG[unit], 1), weight.group(0)
    areas = "|".join(sorted((re.escape(u) for u in AREA_UNITS_HA), key=len, reverse=True))
    area = re.search(rf"(\d+(?:\.\d+)?)\s*({areas})", ascii_text, re.IGNORECASE)
    if area and crop is not None:
        hectares = float(area.group(1)) * AREA_UNITS_HA[area.group(2).lower()]
        return round(hectares * YIELD_T_PER_HA[crop] * 1000, 0), f"{area.group(0)} (estimated harvest at {YIELD_T_PER_HA[crop]} t/ha)"
    return None, None


def _offer(text: str) -> tuple[float | None, str | None]:
    ascii_text = text.translate(_DIGITS_ASCII)
    roles = "|".join(sorted(MIDDLEMAN_TERMS, key=len, reverse=True))
    match = re.search(rf"({roles})[^।?!\d]{{0,30}}?(\d+(?:\.\d+)?)\s*টাকা", ascii_text)
    if match:
        return float(match.group(2)), MIDDLEMAN_TERMS[match.group(1)]
    any_price = re.search(r"(\d+(?:\.\d+)?)\s*টাকা\s*(?:কেজি|মণ)?", ascii_text)
    return (float(any_price.group(1)), None) if any_price else (None, None)


def _intent(concepts: list[str], text: str) -> str:
    c = set(concepts)
    if c & {"flood", "flash", "embankment"}:
        return "FLOOD_EMERGENCY_HARVEST"
    if re.search(r"মিলে|সমিতি|একসাথে|যৌথ|ট্রাক", text) and "store" not in c and "cold" not in c:
        return "TRUCK_POOLING"
    if ("cold" in c or "store" in c) and re.search(r"জায়গা|কোটা|quota", text):
        return "STORAGE_ACCESS"
    if c & {"syndicate", "intermediary"} and re.search(r"সরাসরি|ছাড়া", text):
        return "SYNDICATE_BYPASS"
    if "sell" in c and ("store" in c or "cold" in c):
        return "SELL_OR_STORE"
    if "price" in c:
        return "PRICE_CHECK"
    return "GENERAL_ADVISORY"


class BanglaVoicePipeline:
    def transcribe_and_normalize(self, preset_id: str | None = None, text: str | None = None, audio_base64: str | None = None,
                                 dialect_hint: str | None = None) -> TranscriptionResult:
        preset = None
        if preset_id:
            preset = VOICE_PRESETS.get(preset_id)
            if preset is None:
                raise ToolExecutionError(f"Unknown voice preset '{preset_id}'. Available: {', '.join(VOICE_PRESETS)}.")
            raw, source, backend, confidence, duration = preset.transcript, "preset", "recorded farmer preset transcript", 0.94, preset.audio_duration_s
        elif text:
            raw, source, backend, confidence, duration = text, "text", "typed text (no STT)", 1.0, None
        elif audio_base64:
            raw, backend, confidence, duration = _transcribe_audio(audio_base64)
            source = "audio"
        else:
            raise ToolExecutionError("Provide preset_id, text or audio_base64.")

        dialect, scores, hinted = _detect_dialect(raw, dialect_hint or (preset.dialect if preset else None))
        scrub = PII_SCRUBBER.scrub(raw)
        normalized = scrub.anonymized_text
        for dialect_form, standard in sorted(VOICE_NORMALIZATION.items(), key=lambda kv: -len(kv[0])):
            normalized = normalized.replace(dialect_form, standard)
        normalized = re.sub(r"^[\s,।]+", "", digitize_numbers(normalize_dialect(normalized)))

        local_term = next((t for t in sorted(LOCAL_CROP_TERMS, key=len, reverse=True) if t in normalized), None)
        crop = detect_crop(normalized) if local_term is None else LOCAL_CROP_TERMS[local_term]
        if local_term in ("মরিচ",) or (crop is not None and local_term is None):
            local_term = None
        upazila_name = next((en for bn, en in UPAZILA_BN.items() if bn in raw), None)
        district = preset.district if preset else None
        if upazila_name:
            district = bd_geo.resolve_upazila(upazila_name).district
        district = district or detect_district(normalized)
        quantity, expression = _quantity(normalized, crop)
        offer, role = _offer(normalized)
        concepts = concepts_in(normalized)
        return TranscriptionResult(
            source=source, preset_id=preset.preset_id if preset else None, stt_backend=backend,
            stt_model_reference=WHISPER_REFERENCE, dialect=dialect, dialect_scores=scores, dialect_hint_used=hinted,
            farmer_id=preset.farmer_id if preset else None, raw_transcript=raw, scrubbed_transcript=scrub.anonymized_text,
            pii_entities=[e.entity_type for e in scrub.entities], normalized_text=normalized,
            entities=VoiceEntities(
                crop=crop, crop_local_term=local_term, quantity_kg=quantity, quantity_expression=expression,
                district=district, upazila=upazila_name or (preset.upazila if preset else None), offered_faria_price_bdt=offer,
                middleman_role=role, intent=_intent(concepts, normalized), concepts=concepts,
            ),
            asr_confidence=round(confidence, 3), audio_duration_s=duration,
        )

    @staticmethod
    def build_ssml(text_bn: str, rate: str = "90%") -> VoiceScript:
        sentences = [s.strip() for s in re.split(r"(?<=[।?!])\s*", text_bn) if s.strip()]
        guide = [PronunciationEntry(term=t, ipa=ipa, romanized=rom) for t, (ipa, rom) in PHONETIC_GUIDE.items() if t in text_bn]

        def mark(sentence: str) -> str:
            rendered = escape(sentence)
            for term, (ipa, _) in PHONETIC_GUIDE.items():
                rendered = rendered.replace(term, f'<phoneme alphabet="ipa" ph={quoteattr(ipa)}>{term}</phoneme>', 1)
            return re.sub(r"([০-৯][০-৯,.]*)", r'<say-as interpret-as="cardinal">\1</say-as>', rendered)

        body = '<break time="400ms"/>'.join(f"<s>{mark(s)}</s>" for s in sentences)
        ssml = f'<speak version="1.1" xml:lang="bn-BD"><prosody rate="{rate}" pitch="-2%"><p>{body}</p></prosody></speak>'
        return VoiceScript(text_bn=text_bn, ssml=ssml, voice="bn-BD neural voice, slowed for rural playback",
                           pronunciation_guide=guide, estimated_duration_s=round(len(text_bn) / 12.5 + 0.4 * len(sentences), 1))


VOICE_PIPELINE = BanglaVoicePipeline()
