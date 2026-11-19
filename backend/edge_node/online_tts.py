"""Online Bangla speech for browsers that have no Bangla voice of their own (desktop Chrome, plain Windows).

The farmer app first uses the device's own Bangla voice (Microsoft Edge and Chrome on Android have one). Only when
there is none does it ask this node, which has the answer read by an online speech service:
  1. Google Translate's Bangla voice, in chunks of at most 180 characters cut at sentence ends (measured: Rahim's 693-
     character answer, 4 chunks, 2.9 s, 4 of 4 answered);
  2. if Google fails, Microsoft's neural bn-BD voices through the open-source `edge-tts` library (better sounding, but it
     throttles requests close together and answered only part of them in testing).
The text leaves the node: personal details are scrubbed first, nothing else is sent, and Offline edge mode never calls
it. Switch it off with KNX_ONLINE_TTS=off.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from collections import OrderedDict

import httpx

from guardrails.pii_scrubber import PII_SCRUBBER

ENABLED = os.getenv("KNX_ONLINE_TTS", "on").strip().lower() not in {"0", "off", "false", "no"}
MAX_CHARS = 1_500
CHUNK_CHARS = 180   # Google's endpoint takes about 200 characters a request
GOOGLE_URL = "https://translate.google.com/translate_tts"
MS_VOICES = ("bn-BD-NabanitaNeural", "bn-BD-PradeepNeural")
TIMEOUT_S = 12.0
_CACHE: OrderedDict[str, bytes] = OrderedDict()   # the same answer is often played twice; keep the last few in memory
_CACHE_SIZE = 48


class SpeechUnavailable(Exception):
    """The online voice is switched off on this node."""


def chunks(text: str, limit: int = CHUNK_CHARS) -> list[str]:
    """Sentence-sized pieces of at most `limit` characters (a long sentence is cut at its last space)."""
    out: list[str] = []
    current = ""
    for part in text.replace("।", "।\n").replace(";", ";\n").split("\n"):
        part = part.strip()
        if len(part) > limit and current:   # keep reading order: what came before goes out first
            out.append(current)
            current = ""
        while len(part) > limit:
            cut = part.rfind(" ", 0, limit)
            cut = cut if cut > 0 else limit
            out.append(part[:cut].strip())
            part = part[cut:].strip()
        if not part:
            continue
        if current and len(current) + 1 + len(part) > limit:
            out.append(current)
            current = part
        else:
            current = f"{current} {part}".strip()
    if current:
        out.append(current)
    return out


async def _google(text: str) -> bytes:
    audio = bytearray()
    async with httpx.AsyncClient(timeout=TIMEOUT_S, headers={"User-Agent": "Mozilla/5.0"}) as client:
        for piece in chunks(text):
            response = await client.get(GOOGLE_URL, params={"ie": "UTF-8", "q": piece, "tl": "bn", "client": "tw-ob"})
            response.raise_for_status()
            if not response.headers.get("content-type", "").startswith("audio/"):
                raise RuntimeError("Google's speech service answered without audio")
            audio.extend(response.content)   # MP3 frames from consecutive pieces play back as one stream
    return bytes(audio)


async def _microsoft(text: str) -> bytes:
    import edge_tts   # optional: only the fallback needs it

    last: Exception | None = None
    for attempt, voice in enumerate(MS_VOICES):
        if attempt:
            await asyncio.sleep(1.5)   # it throttles requests close together
        audio = bytearray()
        try:
            async for chunk in edge_tts.Communicate(text, voice=voice, rate="-5%").stream():
                if chunk["type"] == "audio":
                    audio.extend(chunk["data"])
            if audio:
                return bytes(audio)
        except Exception as exc:   # NoAudioReceived, a dropped socket
            last = exc
    raise RuntimeError("Microsoft's speech service answered without audio") from last


async def bangla_speech(text: str) -> bytes:
    """MP3 audio of `text` in Bangla; cached by the scrubbed text. Raises when every service fails."""
    if not ENABLED:
        raise SpeechUnavailable("The online Bangla voice is switched off on this node (KNX_ONLINE_TTS).")
    clean = PII_SCRUBBER.scrub(text).anonymized_text.strip()[:MAX_CHARS]
    key = hashlib.sha256(clean.encode()).hexdigest()
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return _CACHE[key]
    try:
        audio = await asyncio.wait_for(_google(clean), timeout=3 * TIMEOUT_S)
    except Exception as google_error:
        try:
            audio = await asyncio.wait_for(_microsoft(clean), timeout=3 * TIMEOUT_S)
        except Exception as ms_error:
            raise RuntimeError(f"Google: {type(google_error).__name__}; Microsoft: {type(ms_error).__name__}") from ms_error
    _CACHE[key] = audio
    while len(_CACHE) > _CACHE_SIZE:
        _CACHE.popitem(last=False)
    return audio


if __name__ == "__main__":   # self-check: python -m edge_node.online_tts (from backend/)
    for sample in ("ক" * 50 + "। " + "খ " * 120 + "। শেষ।", "এক। দুই; তিন।", "x" * 400, ""):
        parts = chunks(sample)
        assert all(0 < len(p) <= CHUNK_CHARS for p in parts), parts
        assert "".join(parts).replace(" ", "") == sample.replace(" ", ""), parts   # nothing lost, order kept
    print("online_tts.py: all checks passed")
