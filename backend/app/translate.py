"""
Lightweight translation helper using Google's public translate endpoint.
No API key required. Used to translate English product names (from Google Lens)
into Hebrew so Israeli store scrapers (Panta Rei, Jack Kuba) can match them.

Results are cached in-memory to avoid repeat calls for the same text.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

GTX_URL = "https://translate.googleapis.com/translate_a/single"

# Simple in-memory cache: (text, target) → translated
_cache: dict[tuple[str, str], str] = {}


import re as _re

# Hebrew niqqud (vowel points) and cantillation marks — U+0591..U+05C7.
# Store catalogs are written without them, so we strip them for matching.
_NIQQUD = _re.compile(r"[\u0591-\u05C7]")


def _strip_niqqud(text: str) -> str:
    return _NIQQUD.sub("", text)


def _is_mostly_hebrew(text: str) -> bool:
    """Return True if the text already contains Hebrew characters."""
    hebrew = sum(1 for ch in text if "\u0590" <= ch <= "\u05FF")
    letters = sum(1 for ch in text if ch.isalpha())
    return letters > 0 and hebrew / letters > 0.3


async def translate(text: str, target: str = "iw", source: str = "auto") -> str:
    """
    Translate `text` into `target` language (default Hebrew 'iw').
    Returns the original text on any failure, or if it's already in Hebrew.
    """
    if not text or not text.strip():
        return text

    # Skip if already Hebrew
    if target in ("iw", "he") and _is_mostly_hebrew(text):
        return text

    cache_key = (text, target)
    if cache_key in _cache:
        return _cache[cache_key]

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                GTX_URL,
                params={"client": "gtx", "sl": source, "tl": target, "dt": "t", "q": text},
            )
            if resp.status_code != 200:
                logger.warning("Translate failed %s for %r", resp.status_code, text)
                return text
            data = resp.json()
            # data[0] is a list of translated segments: [[translated, original, ...], ...]
            translated = "".join(seg[0] for seg in data[0] if seg and seg[0])
            translated = _strip_niqqud(translated.strip()) or text
    except Exception as exc:
        logger.warning("Translate error for %r: %s", text, exc)
        return text

    _cache[cache_key] = translated
    logger.info("Translated %r → %r", text, translated)
    return translated
