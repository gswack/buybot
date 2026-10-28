"""
Coupon code finder using SerpAPI Google Search.

Strategy: search Google for "<store> coupon code <month> <year>" which surfaces
results from coupon aggregator sites (RetailMeNot, Honey, CouponFollow) and
publicly indexed Instagram/influencer posts.

Caching: results are cached in-memory per store for 4 hours to avoid burning
SerpAPI credits on repeated searches for the same store.
"""

import logging
import re
import time
from datetime import datetime

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

SERPAPI_BASE = "https://serpapi.com/search"
CACHE_TTL_SECONDS = 4 * 60 * 60  # 4 hours

# In-memory cache: store_key → {"expires": float, "coupons": list[dict]}
_cache: dict[str, dict] = {}

# Patterns that strongly suggest a coupon code in text
# A candidate code token: starts with a letter, 4-20 uppercase alphanumeric chars
CODE_TOKEN = r"[A-Z][A-Z0-9]{3,19}"

# Codes that appear after a trigger phrase. Handles stacked triggers like
# "Promo Code BLOOM", "Coupon Code NEWBIE", "codes like GOLDENHOUR",
# "promo code: FAVE". One or more trigger/filler words, then the code.
CONTEXT_CODE_PATTERN = re.compile(
    r"(?:(?:code|coupon|promo|voucher)s?|like|is|are|use|with|:|->|=)"  # trigger
    r"(?:\s+(?:(?:code|coupon|promo|voucher)s?|like|is|are|:|->|=))*"   # more triggers/fillers
    r"\s+"
    r"(" + CODE_TOKEN + r")",
    re.IGNORECASE,
)

# A mixed alpha-then-digit code anywhere, e.g. EXTRA10, SAVE15, GET20OFF.
# These are almost always real codes even without a trigger word nearby.
MIXED_CODE_PATTERN = re.compile(r"(?<![A-Z0-9])([A-Z]{2,}[0-9]{1,4}[A-Z0-9]{0,6})(?![A-Z0-9])")

# Common English words that must never be treated as codes
EXCLUDED_TOKENS = {
    "HTTP", "HTTPS", "HTML", "JSON", "FREE", "SALE", "SHOP", "SAVE",
    "CODE", "CODES", "DEAL", "DEALS", "BEST", "TODAY", "MORE", "PLUS",
    "VIEW", "CLICK", "HERE", "LINK", "PROMO", "OFFER", "OFFERS",
    "DISCOUNT", "DISCOUNTS", "GET", "ASOS", "ZARA", "NIKE", "NEXT",
    "WITH", "YOUR", "ORDER", "WHEN", "COUPON", "COUPONS", "SAVINGS",
    "TIPS", "SHOPPERS", "ACTIVELY", "SHARING", "VOUCHER", "VOUCHERS",
    "STUDENT", "EXTRA", "FROM", "THIS", "THAT", "THESE", "ONLY",
}

# Coupon aggregator domains we trust most
TRUSTED_DOMAINS = {
    "retailmenot.com", "honey.com", "coupons.com", "couponfollow.com",
    "vouchercodes.co.uk", "dealspotr.com", "groupon.com",
    "instagram.com", "linktr.ee",
}


def _cache_key(store: str) -> str:
    return store.lower().strip()


def _is_cached(store: str) -> bool:
    key = _cache_key(store)
    entry = _cache.get(key)
    return entry is not None and entry["expires"] > time.time()


def _get_cached(store: str) -> list[dict]:
    return _cache[_cache_key(store)]["coupons"]


def _set_cache(store: str, coupons: list[dict]) -> None:
    _cache[_cache_key(store)] = {
        "expires": time.time() + CACHE_TTL_SECONDS,
        "coupons": coupons,
    }


def _extract_codes_from_text(text: str) -> list[str]:
    """
    Pull real coupon codes from a snippet using two high-precision strategies:
    1. An UPPERCASE token that follows a trigger word (code/coupon/promo/voucher).
       Real codes are written in uppercase, so we require the captured token to be
       uppercase — this filters out filler like "code is valid".
    2. Mixed alpha-digit tokens anywhere (EXTRA10, SAVE15) — rarely false positives.

    This avoids grabbing every capitalized word in the snippet.
    """
    found: list[str] = []

    # Strategy 1 — codes after a trigger phrase.
    # The capture is validated as genuinely uppercase (code-like) afterwards.
    for m in CONTEXT_CODE_PATTERN.findall(text):
        code = m.strip()
        # Must be all-uppercase in the original text to count as a code
        if code.isupper() and len(code) >= 4 and code not in EXCLUDED_TOKENS:
            found.append(code)

    # Strategy 2 — mixed alpha-digit codes anywhere
    for m in MIXED_CODE_PATTERN.findall(text.upper()):
        if m not in EXCLUDED_TOKENS:
            found.append(m)

    # De-dupe preserving order
    seen = set()
    result = []
    for c in found:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result


def _parse_coupon_results(organic_results: list[dict], store: str) -> list[dict]:
    """
    Extract structured coupon data from SerpAPI organic search results.
    Each result may contain multiple codes in its snippet.
    """
    coupons = []
    seen_codes: set[str] = set()

    for result in organic_results[:8]:  # top 8 results only
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        link = result.get("link", "")
        source = result.get("displayed_link", link)

        combined_text = f"{title} {snippet}"
        codes = _extract_codes_from_text(combined_text)

        for code in codes:
            if code in seen_codes:
                continue
            seen_codes.add(code)

            is_trusted = any(domain in link.lower() for domain in TRUSTED_DOMAINS)

            coupons.append({
                "code": code,
                "description": snippet[:120] if snippet else title[:120],
                "source": source,
                "source_url": link,
                "is_trusted": is_trusted,
            })

    # Sort: trusted sources first
    coupons.sort(key=lambda c: (0 if c["is_trusted"] else 1))
    return coupons[:6]  # return at most 6 codes per store


async def fetch_coupons_for_store(store: str) -> list[dict]:
    """
    Fetch active coupon codes for a store using SerpAPI Google Search.
    Results are cached for 4 hours.
    Returns a list of coupon dicts: {code, description, source, source_url, is_trusted}
    """
    if _is_cached(store):
        logger.info("Coupons cache hit for %r", store)
        return _get_cached(store)

    now = datetime.now()
    month_year = now.strftime("%B %Y")  # e.g. "October 2026"
    search_query = f'"{store}" coupon code {month_year}'

    logger.info("Searching coupons for %r: %r", store, search_query)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                SERPAPI_BASE,
                params={
                    "engine": "google",
                    "q": search_query,
                    "num": 10,
                    "hl": "en",
                    "api_key": settings.serpapi_key,
                },
            )
            if resp.status_code != 200:
                logger.error("SerpAPI coupon search error %s: %s", resp.status_code, resp.text[:200])
                return []

            data = resp.json()
            organic = data.get("organic_results") or []
            coupons = _parse_coupon_results(organic, store)

    except Exception as exc:
        logger.error("Coupon search failed for %r: %s", store, exc)
        return []

    _set_cache(store, coupons)
    logger.info("Found %d coupons for %r", len(coupons), store)
    return coupons


async def fetch_coupons_for_stores(stores: list[str]) -> dict[str, list[dict]]:
    """
    Fetch coupons for multiple stores concurrently.
    Deduplicates store names and skips cached entries without an API call.
    Returns {store_name: [coupon, ...]}
    """
    import asyncio

    unique_stores = list({s.strip() for s in stores if s.strip()})
    tasks = [fetch_coupons_for_store(store) for store in unique_stores]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output: dict[str, list[dict]] = {}
    for store, result in zip(unique_stores, results):
        if isinstance(result, Exception):
            logger.error("Coupon fetch failed for %r: %s", store, result)
            output[store] = []
        else:
            output[store] = result

    return output
