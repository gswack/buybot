"""
Search routes using SerpAPI.

- POST /api/search/image  — uploads an image, searches via Google Lens,
                            returns visually matching products with live prices.
- POST /api/search/text   — accepts a text query, searches via Google Shopping,
                            returns matching products with live prices.

Both endpoints accept:
- country_code: 2-letter ISO country code from the browser's Geolocation API
                (e.g. "gb", "us", "fr"). Defaults to "us".
- memberships:  comma-separated list of membership IDs the user has enrolled in
                (e.g. "asos_student,zara_member"). Used to annotate results with
                applicable discounts.
"""

import asyncio
import io
import logging

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image

from app.config import settings
from app.memberships import MEMBERSHIP_PROGRAMS, apply_discounts
from app.scrapers.jack_kuba import search as jack_kuba_search
from app.scrapers.asos import search as asos_search

logger = logging.getLogger(__name__)
router = APIRouter()

SERPAPI_BASE = "https://serpapi.com/search"
MAX_UPLOAD_BYTES = 480_000  # SerpAPI limit is 500KB; keep a small buffer


def _compress_image(image_bytes: bytes) -> tuple[bytes, str]:
    """
    If image_bytes exceeds MAX_UPLOAD_BYTES, resize and re-compress it
    until it fits. Returns (compressed_bytes, content_type).
    Always outputs JPEG for consistent compression.
    """
    if len(image_bytes) <= MAX_UPLOAD_BYTES:
        return image_bytes, "image/jpeg"

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    quality = 85

    while quality >= 30:
        buf = io.BytesIO()
        # Scale down if still too large after compression
        scale = min(1.0, (MAX_UPLOAD_BYTES / len(image_bytes)) ** 0.5)
        if scale < 1.0:
            new_w = max(1, int(img.width * scale))
            new_h = max(1, int(img.height * scale))
            img = img.resize((new_w, new_h), Image.LANCZOS)

        img.save(buf, format="JPEG", quality=quality, optimize=True)
        compressed = buf.getvalue()
        if len(compressed) <= MAX_UPLOAD_BYTES:
            logger.info(
                "Image compressed: %d KB → %d KB (quality=%d)",
                len(image_bytes) // 1024,
                len(compressed) // 1024,
                quality,
            )
            return compressed, "image/jpeg"
        quality -= 10

    # Last resort: aggressive resize to thumbnail
    img = img.resize((800, 800), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=50, optimize=True)
    return buf.getvalue(), "image/jpeg"

CURRENCY_SYMBOLS = {"$": "USD", "£": "GBP", "€": "EUR", "₪": "ILS"}

# Map country code → currency, so prices make sense for the user's region
COUNTRY_CURRENCY: dict[str, str] = {
    "gb": "GBP", "ie": "GBP",
    "us": "USD", "ca": "USD",
    "de": "EUR", "fr": "EUR", "es": "EUR", "it": "EUR", "nl": "EUR",
    "il": "ILS",
}


def _parse_price(price_raw) -> tuple[float | None, str]:
    """
    Extract (price_float, currency_str) from whatever shape SerpAPI returns.
    Handles:
      - dict:   {"value": "$160*", "extracted_value": 160.0, "currency": "$"}
      - str:    "£29.99" or "29.99 GBP"
      - float:  29.99
      - None
    """
    if price_raw is None:
        return None, "GBP"

    if isinstance(price_raw, dict):
        value = price_raw.get("extracted_value") or price_raw.get("value")
        raw_currency = str(price_raw.get("currency") or "")
        currency = CURRENCY_SYMBOLS.get(raw_currency, raw_currency.upper() or "GBP")
        if isinstance(value, (int, float)):
            return float(value), currency
        price_raw = value  # fall through to string parsing e.g. "$160*"

    if isinstance(price_raw, (int, float)):
        return float(price_raw), "GBP"

    raw_str = str(price_raw)
    currency = "GBP"
    for symbol, code in CURRENCY_SYMBOLS.items():
        if symbol in raw_str:
            currency = code
            break
    for code in ("GBP", "USD", "EUR", "ILS"):
        if code in raw_str.upper():
            currency = code
            break
    cleaned = "".join(ch for ch in raw_str if ch.isdigit() or ch == ".")
    try:
        return float(cleaned) if cleaned else None, currency
    except ValueError:
        return None, currency


def _normalize_results(items: list[dict]) -> list[dict]:
    """Map SerpAPI result fields to a consistent shape for the frontend."""
    out = []
    for item in items:
        price_raw = item.get("price") or item.get("extracted_price")
        price, currency = _parse_price(price_raw)
        out.append({
            "id": item.get("position") or len(out) + 1,
            "store": item.get("source") or item.get("seller") or "Unknown",
            "name": item.get("title") or item.get("name") or "Unknown",
            "url": item.get("link") or item.get("product_link") or "#",
            "image_url": item.get("thumbnail") or item.get("image"),
            "price": price,
            "currency": currency,
            # membership fields — populated later by apply_discounts()
            "membership_id": None,
            "membership_name": None,
            "membership_description": None,
            "discount_pct": 0.0,
            "discounted_price": None,
        })
    return out


async def _call_serpapi(params: dict) -> dict:
    """Async GET to SerpAPI."""
    params["api_key"] = settings.serpapi_key
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(SERPAPI_BASE, params=params)
        if resp.status_code != 200:
            logger.error("SerpAPI GET error %s: %s", resp.status_code, resp.text)
            raise HTTPException(
                status_code=502,
                detail=f"SerpAPI returned {resp.status_code}: {resp.text[:500]}",
            )
        return resp.json()


async def _upload_image_to_serpapi(client: httpx.AsyncClient, image_bytes: bytes, content_type: str) -> str:
    """Upload image bytes to SerpAPI and return the image_id."""
    upload_resp = await client.post(
        "https://serpapi.com/image",
        data={"api_key": settings.serpapi_key},
        files={"image": ("image", image_bytes, content_type)},
    )
    if upload_resp.status_code != 200:
        logger.error("SerpAPI upload error %s: %s", upload_resp.status_code, upload_resp.text)
        raise HTTPException(
            status_code=502,
            detail=f"SerpAPI image upload failed: {upload_resp.text[:500]}",
        )
    upload_data = upload_resp.json()
    if "error" in upload_data:
        raise HTTPException(status_code=502, detail=f"SerpAPI upload error: {upload_data['error']}")
    return upload_data["image_id"]


def _extract_product_query(lens_data: dict) -> str | None:
    """
    Extract the best product search query from a Google Lens response.
    Tries several fields in order of specificity.
    """
    # Knowledge graph title is the most specific (e.g. "Nike Air Max 90")
    kg = lens_data.get("knowledge_graph") or {}
    if kg.get("title"):
        return kg["title"]

    # Top visual match title is usually the product name
    visual_matches = lens_data.get("visual_matches") or []
    if visual_matches:
        return visual_matches[0].get("title")

    # Organic results as last resort
    organic = lens_data.get("organic_results") or []
    if organic:
        return organic[0].get("title")

    return None


async def _call_serpapi_lens(image_bytes: bytes, content_type: str, country_code: str) -> dict:
    """
    Two-step Google Lens search:
    1. Upload image → get image_id
    2. Run Lens with image_id to identify the product
    Returns the raw Lens response.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        image_id = await _upload_image_to_serpapi(client, image_bytes, content_type)
        logger.info("SerpAPI image uploaded, image_id=%s, country=%s", image_id, country_code)

        search_resp = await client.get(
            SERPAPI_BASE,
            params={
                "engine": "google_lens",
                "image_id": image_id,
                "api_key": settings.serpapi_key,
                "hl": "en",
                "gl": country_code.lower(),
            },
        )
        if search_resp.status_code != 200:
            logger.error("SerpAPI Lens error %s: %s", search_resp.status_code, search_resp.text)
            raise HTTPException(
                status_code=502,
                detail=f"SerpAPI Lens search failed: {search_resp.text[:500]}",
            )
        return search_resp.json()


def _parse_memberships(raw: str) -> list[str]:
    """Parse comma-separated membership IDs, ignoring blanks."""
    if not raw:
        return []
    return [m.strip() for m in raw.split(",") if m.strip()]


async def _run_jack_kuba(query: str, top_k: int) -> list[dict]:
    """
    Run the Jack Kuba scraper and return normalised results.
    Jack Kuba products already carry scraped club/sale prices so we
    skip apply_discounts() for them — the data is already accurate.
    """
    try:
        return await jack_kuba_search(query, max_results=top_k)
    except Exception as exc:
        logger.warning("Jack Kuba scraper failed for %r: %s", query, exc)
        return []


async def _run_asos(query: str, country_code: str, top_k: int) -> list[dict]:
    """Run the Apify ASOS scraper. Returns [] if token not configured or on error."""
    try:
        return await asos_search(query, country_code=country_code, max_results=top_k)
    except Exception as exc:
        logger.warning("ASOS scraper failed for %r: %s", query, exc)
        return []


def _merge_results(shopping: list[dict], jack_kuba: list[dict], asos: list[dict]) -> list[dict]:
    """
    Merge all sources. Order: Jack Kuba first (most relevant for IL users),
    then ASOS, then Google Shopping. Re-number IDs for the frontend.
    """
    merged = jack_kuba + asos + shopping
    for i, r in enumerate(merged, start=1):
        r["id"] = i
    return merged


@router.post("/search/image")
async def search_by_image(
    file: UploadFile = File(...),
    country_code: str = Form(default="us"),
    memberships: str = Form(default=""),
):
    """
    Upload an image → Google Lens identifies the product →
    Google Shopping + Jack Kuba (if country=IL) run in parallel →
    results merged and membership discounts applied.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="file must be an image")

    image_bytes = await file.read()
    content_type = file.content_type or "image/jpeg"

    # Auto-compress if over SerpAPI's 500KB limit
    image_bytes, content_type = _compress_image(image_bytes)

    # Phase 1 — identify product via Google Lens
    lens_data = await _call_serpapi_lens(image_bytes, content_type, country_code)
    product_query = _extract_product_query(lens_data)
    logger.info("Lens identified product as: %r", product_query)

    # Phase 2 — run Google Shopping + Jack Kuba + ASOS in parallel
    shopping_items: list[dict] = []
    jack_kuba_items: list[dict] = []
    asos_items: list[dict] = []

    tasks = []
    is_israel = country_code.lower() == "il"

    if product_query:
        tasks.append(_call_serpapi({
            "engine": "google_shopping",
            "q": product_query,
            "hl": "en",
            "gl": country_code.lower(),
            "num": settings.top_k,
        }))
        if is_israel:
            tasks.append(_run_jack_kuba(product_query, settings.top_k))
        tasks.append(_run_asos(product_query, country_code, settings.top_k))

    if tasks:
        results_raw = await asyncio.gather(*tasks, return_exceptions=True)
        idx = 0
        # Google Shopping is always first
        if not isinstance(results_raw[idx], Exception):
            shopping_items = results_raw[idx].get("shopping_results") or []
            logger.info("Google Shopping returned %d results for %r in %s",
                        len(shopping_items), product_query, country_code)
        idx += 1
        # Jack Kuba is second only when is_israel
        if is_israel and len(results_raw) > idx and not isinstance(results_raw[idx], Exception):
            jack_kuba_items = results_raw[idx]
            logger.info("Jack Kuba returned %d results for %r", len(jack_kuba_items), product_query)
            idx += 1
        # ASOS is last
        if len(results_raw) > idx and not isinstance(results_raw[idx], Exception):
            asos_items = results_raw[idx]
            logger.info("ASOS returned %d results for %r", len(asos_items), product_query)

    # Fallback to Lens visual_matches if nothing found
    if not shopping_items and not jack_kuba_items and not asos_items:
        logger.info("No results from any source — falling back to Lens visual_matches")
        shopping_items = lens_data.get("visual_matches") or []

    shopping_results = _normalize_results(shopping_items[: settings.top_k])
    shopping_results = apply_discounts(shopping_results, _parse_memberships(memberships))
    asos_items = apply_discounts(asos_items, _parse_memberships(memberships))

    merged = _merge_results(shopping_results, jack_kuba_items, asos_items)
    return {
        "results": merged,
        "country_code": country_code,
        "identified_as": product_query,
    }


@router.post("/search/text")
async def search_by_text(
    query: str = Form(...),
    country_code: str = Form(default="us"),
    memberships: str = Form(default=""),
):
    """
    Text query → Google Shopping + Jack Kuba (if country=IL) in parallel →
    results merged and membership discounts applied.
    """
    if not query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")

    is_israel = country_code.lower() == "il"

    tasks: list = [_call_serpapi({
        "engine": "google_shopping",
        "q": query,
        "hl": "en",
        "gl": country_code.lower(),
        "num": settings.top_k,
    })]
    if is_israel:
        tasks.append(_run_jack_kuba(query, settings.top_k))
    tasks.append(_run_asos(query, country_code, settings.top_k))

    results_raw = await asyncio.gather(*tasks, return_exceptions=True)

    shopping_items: list[dict] = []
    jack_kuba_items: list[dict] = []
    asos_items: list[dict] = []

    idx = 0
    if not isinstance(results_raw[idx], Exception):
        shopping_items = results_raw[idx].get("shopping_results") or []
    idx += 1
    if is_israel and len(results_raw) > idx and not isinstance(results_raw[idx], Exception):
        jack_kuba_items = results_raw[idx]
        idx += 1
    if len(results_raw) > idx and not isinstance(results_raw[idx], Exception):
        asos_items = results_raw[idx]

    shopping_results = _normalize_results(shopping_items[: settings.top_k])
    shopping_results = apply_discounts(shopping_results, _parse_memberships(memberships))
    asos_items = apply_discounts(asos_items, _parse_memberships(memberships))

    merged = _merge_results(shopping_results, jack_kuba_items, asos_items)
    return {"results": merged, "country_code": country_code}


@router.get("/memberships")
async def list_memberships():
    """Return all available membership programs for the frontend selector."""
    return {
        "memberships": [
            {
                "id": p.id,
                "name": p.name,
                "store": p.store,
                "discount_pct": p.discount_pct,
                "description": p.description,
            }
            for p in MEMBERSHIP_PROGRAMS
        ]
    }
