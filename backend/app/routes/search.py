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
import re

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image

from app.config import settings
from app.memberships import MEMBERSHIP_PROGRAMS, apply_discounts
from app.scrapers.jack_kuba import search as jack_kuba_search
from app.scrapers.asos import search as asos_search
from app.scrapers.panta_rei import search as panta_rei_search
from app.translate import translate
from app.currency import get_rates_to, convert_results

# Map country code → preferred display currency
COUNTRY_CURRENCY_TARGET: dict[str, str] = {
    "il": "ILS",
    "gb": "GBP",
    "ie": "GBP",
    "us": "USD",
    "ca": "CAD",
    "de": "EUR", "fr": "EUR", "es": "EUR", "it": "EUR", "nl": "EUR",
    "au": "AUD",
}

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


def _build_query_with_filters(base_query: str, size: str, color: str) -> str:
    """
    Append size and color to a product query string when provided.
    e.g. "salomon snowclog" + size="42" + color="Black"
      → "salomon snowclog size 42 Black"
    """
    parts = [base_query.strip()]
    if color:
        parts.append(color.strip())
    if size:
        parts.append(f"size {size.strip()}")
    return " ".join(parts)


async def _apply_currency(results: list[dict], country_code: str) -> list[dict]:
    """Convert all result prices to the user's local currency if needed."""
    target = COUNTRY_CURRENCY_TARGET.get(country_code.lower())
    if not target:
        return results
    rates = await get_rates_to(target)
    return convert_results(results, target, rates)


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


async def _run_panta_rei(query: str, top_k: int) -> list[dict]:
    """Run the Panta Rei scraper (Israeli sportswear). Returns [] on error."""
    try:
        return await panta_rei_search(query, max_results=top_k)
    except Exception as exc:
        logger.warning("Panta Rei scraper failed for %r: %s", query, exc)
        return []


# Store/brand names to strip from a query before searching Hebrew catalogs.
_BRAND_NOISE = re.compile(
    r"\b(panta[\s-]?rei|jack[\s-]?kuba|asos|zara|shein|nike|adidas|puma|"
    r"mountain\s+warehouse|under\s+armour|reebok|new\s+balance|"
    r"princess\s+polly|quinbie|h&m|hollister|forever\s*21|boohoo|"
    r"pretty\s*little\s*thing|urban\s+outfitters|aloruh|"
    r"men'?s|women'?s|mens|womens|unisex|kids'?|boys'?|girls'?)\b",
    re.IGNORECASE,
)
# Product codes like LA01244, LM93V, SKU numbers
_CODE_NOISE = re.compile(r"\b[A-Z]{1,3}\d{2,}[A-Z0-9]*\b")

# Known garment nouns mapped to reliable Hebrew search terms.
# Ordered MOST SPECIFIC first — "t-shirt" wins over "top" when both appear.
# Mapping to Hebrew directly avoids ambiguous machine translation
# (e.g. "top" → "ראש"/head instead of the garment sense).
# Each entry: (english_noun, specific_hebrew, broad_hebrew)
# The BROAD term is a fallback for stores with strict search that only match
# generic words (e.g. Panta Rei matches "חולצה" but not "חולצת טי שירט").
_GARMENT_MAP: list[tuple[str, str, str]] = [
    ("running shirt", "חולצת ריצה", "חולצה"),
    ("running pants", "מכנסי ריצה", "מכנסיים"),
    ("sports bra", "חזיית ספורט", "חזייה"),
    ("t-shirt", "חולצת טי שירט", "חולצה"),
    ("tshirt", "חולצת טי שירט", "חולצה"),
    ("tee", "חולצת טי שירט", "חולצה"),
    ("sweatshirt", "סווטשירט", "חולצה"),
    ("hoodie", "קפוצ'ון", "חולצה"),
    ("sweater", "סוודר", "חולצה"),
    ("jacket", "ז'קט", "מעיל"),
    ("coat", "מעיל", "מעיל"),
    ("leggings", "טייץ", "מכנסיים"),
    ("tights", "טייץ", "מכנסיים"),
    ("trousers", "מכנסיים", "מכנסיים"),
    ("pants", "מכנסיים", "מכנסיים"),
    ("shorts", "מכנסיים קצרים", "מכנסיים"),
    ("dress", "שמלה", "שמלה"),
    ("skirt", "חצאית", "חצאית"),
    ("blouse", "חולצה", "חולצה"),
    ("swimsuit", "בגד ים", "בגד ים"),
    ("bikini", "ביקיני", "בגד ים"),
    ("socks", "גרביים", "גרביים"),
    ("bra", "חזייה", "חזייה"),
    ("shirt", "חולצה", "חולצה"),
    ("top", "חולצה", "חולצה"),
]


def _clean_query_for_stores(query: str) -> str:
    """
    Clean a Lens-identified title into a concise English search term for
    external store links (Shein, Zara). Unlike _clean_query_for_local, this
    keeps descriptive words (e.g. "lace short sleeve top") rather than reducing
    to a single garment noun — store search engines handle multi-word queries.

    Strips brand names, product codes, and anything after a '|' separator.
    e.g. "Quinbie Lace Short Sleeve Top Black | Princess Polly"
         → "lace short sleeve top black"
    """
    if not query:
        return ""
    # Drop everything after a store/brand separator
    base = re.split(r"[|–—]", query)[0]
    cleaned = _BRAND_NOISE.sub(" ", base)
    cleaned = _CODE_NOISE.sub(" ", cleaned)
    # Keep letters/numbers/spaces only
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    # Safety cap — keep it reasonably short
    words = cleaned.split()
    if len(words) > 6:
        cleaned = " ".join(words[:6])
    return cleaned or query


def _clean_query_for_local(query: str) -> tuple[str, str | None, str | None]:
    """
    Reduce a Lens-identified title to a clean garment description.
    Returns (cleaned_text, specific_hebrew_or_None, broad_hebrew_or_None).

    If a known garment type is recognised, we return reliable Hebrew terms
    directly — bypassing ambiguous machine translation (e.g. "top" → "ראש").
    The broad term is used for stores with strict search (Panta Rei).
    e.g. "...Short Sleeve Top - T-Shirt" → ("t-shirt", "חולצת טי שירט", "חולצה")
    """
    full_lower = query.lower()

    # Match the most specific garment noun across the whole title
    for noun, specific, broad in _GARMENT_MAP:
        if noun in full_lower:
            return noun, specific, broad

    # No known garment — fall back to generic cleaning
    base = re.split(r"[|–—]| - ", query)[0]
    cleaned = _BRAND_NOISE.sub(" ", base)
    cleaned = _CODE_NOISE.sub(" ", cleaned)
    cleaned = re.sub(r"[^\w\s\u0590-\u05FF]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    words = cleaned.split()
    if len(words) > 4:
        cleaned = " ".join(words[:4])

    return (cleaned or query), None, None


# Hebrew tokens that indicate an athletic/sport item, and which store
# specialises in sportswear. Used to boost the right store for sport queries.
_SPORT_TOKENS = {"ריצה", "ספורט", "אימון", "טייץ", "אירובי", "כושר", "מאש"}
_SPORT_STORES = {"Panta Rei"}

# Garment category tokens — a shirt query shouldn't surface bras/underwear.
# Keyed by the category a query belongs to; value is the set of name tokens
# that mean "this is a DIFFERENT category" and should be penalised.
_SHIRT_QUERY_TOKENS = {"חולצה", "חולצת", "שירט", "טי"}
_WRONG_CATEGORY_FOR_SHIRT = {
    "חזייה", "חזיית", "תחתון", "תחתונים", "ברלט", "בגד",  # bras / underwear / swimwear
    "שינה", "פיג'מה", "פיגמה", "חלוק", "לילה",            # sleepwear
    "גרב", "גרביים", "גרביון",                             # socks
    "מכנס", "מכנסי", "מכנסיים",                            # pants
}


def _relevance_score(result: dict, query_tokens: set[str]) -> float:
    """
    Score how well a result's name matches the search query tokens.
    Higher is better. Applies:
      - token overlap + exact-phrase bonus
      - sportswear store boost for athletic queries
      - heavy penalty for wrong-category items (bras/underwear on a shirt query)
    """
    name = (result.get("name") or "").lower()
    if not name or not query_tokens:
        return 0.0

    name_tokens = set(re.findall(r"[\w\u0590-\u05FF]+", name))
    if not name_tokens:
        return 0.0

    # Base: fraction of query tokens found in the product name
    overlap = len(query_tokens & name_tokens)
    score = overlap / len(query_tokens)

    # Bonus: exact substring of the full query phrase
    query_phrase = " ".join(query_tokens)
    if query_phrase and query_phrase in name:
        score += 0.5

    # Store-category weighting for athletic queries
    query_is_sport = bool(query_tokens & _SPORT_TOKENS)
    if query_is_sport and result.get("store") in _SPORT_STORES:
        score += 1.0

    # Wrong-category penalty: if the query is for a shirt/top but the item is a
    # bra, underwear, sleepwear, socks, or pants — push it far down.
    query_is_shirt = bool(query_tokens & _SHIRT_QUERY_TOKENS)
    if query_is_shirt and (name_tokens & _WRONG_CATEGORY_FOR_SHIRT):
        score -= 2.0

    return score


def _rank_by_relevance(results: list[dict], search_query: str) -> list[dict]:
    """Sort results by relevance to the search query (descending)."""
    query_tokens = set(re.findall(r"[\w\u0590-\u05FF]+", search_query.lower()))
    return sorted(
        results,
        key=lambda r: _relevance_score(r, query_tokens),
        reverse=True,
    )


def _interleave_by_store(results: list[dict], search_query: str) -> list[dict]:
    """
    Rank by relevance, then interleave across stores so no single store
    monopolises the top of the list. Within each store, relevance order is kept.
    Items with a clearly negative score (wrong category) are dropped entirely.
    """
    query_tokens = set(re.findall(r"[\w\u0590-\u05FF]+", search_query.lower()))

    # Group by store, keeping only non-negative-scoring items, sorted by score
    by_store: dict[str, list[tuple[float, dict]]] = {}
    for r in results:
        s = _relevance_score(r, query_tokens)
        if s <= 0:
            continue  # drop wrong-category / zero-match items
        by_store.setdefault(r.get("store", "?"), []).append((s, r))

    for store in by_store:
        by_store[store].sort(key=lambda x: x[0], reverse=True)

    # Order stores by their single best-scoring item (best store leads)
    store_order = sorted(
        by_store.keys(),
        key=lambda st: by_store[st][0][0] if by_store[st] else 0,
        reverse=True,
    )

    # Round-robin interleave
    interleaved: list[dict] = []
    idx = 0
    while True:
        added = False
        for store in store_order:
            items = by_store[store]
            if idx < len(items):
                interleaved.append(items[idx][1])
                added = True
        if not added:
            break
        idx += 1

    return interleaved


async def _run_israel_scrapers(query: str, top_k: int) -> list[dict]:
    """
    Run all Israel-only store scrapers (Jack Kuba, Panta Rei) concurrently.
    These stores have Hebrew-only catalogs, so the English query from Google
    Lens is cleaned (brand/code stripped) then translated to Hebrew first.

    Results from both stores are then ranked by relevance to the query, so the
    best-matching item surfaces first regardless of which store it came from.
    """
    cleaned, specific_he, broad_he = _clean_query_for_local(query)
    if specific_he:
        # Known garment → use reliable mapped Hebrew terms directly
        jk_query = specific_he
        pr_query = broad_he or specific_he
    else:
        # Unknown garment → fall back to machine translation (same for both)
        translated = await translate(cleaned, target="iw") or cleaned
        jk_query = pr_query = translated

    print(f">>> IL scrapers: {query!r} → JK={jk_query!r}, PR={pr_query!r}")

    # Jack Kuba handles specific terms; Panta Rei needs the broad term.
    jk, pr = await asyncio.gather(
        _run_jack_kuba(jk_query, top_k),
        _run_panta_rei(pr_query, top_k),
    )
    print(f">>> IL scrapers returned: Jack Kuba={len(jk)}, Panta Rei={len(pr)}")

    # Interleave by store (drops wrong-category items), best store leads.
    combined = _interleave_by_store(jk + pr, jk_query)
    print(f">>> After filter+interleave: {len(combined)} results")
    return combined


async def _run_asos(query: str, country_code: str, top_k: int) -> list[dict]:
    """Run the Apify ASOS scraper. Returns [] if token not configured or on error."""
    try:
        return await asos_search(query, country_code=country_code, max_results=top_k)
    except Exception as exc:
        logger.warning("ASOS scraper failed for %r: %s", query, exc)
        return []


def _merge_results(shopping: list[dict], local_stores: list[dict], asos: list[dict],
                   search_query: str = "") -> list[dict]:
    """
    Merge all sources. If a search_query is provided, rank by relevance
    across all sources so the best match appears first. Otherwise, local IL
    stores first, then ASOS, then Google Shopping. Re-number IDs.
    """
    merged = local_stores + asos + shopping
    if search_query:
        merged = _rank_by_relevance(merged, search_query)
    for i, r in enumerate(merged, start=1):
        r["id"] = i
    return merged


@router.post("/search/identify")
async def identify_image(
    file: UploadFile = File(...),
    country_code: str = Form(default="us"),
):
    """
    Phase 1 of image search.
    Uploads image to Google Lens, identifies the product, classifies it,
    and returns the product name + available sizes/colors.
    Does NOT run any store searches — that is Phase 2 (POST /search/image).
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="file must be an image")

    image_bytes = await file.read()
    content_type = file.content_type or "image/jpeg"
    image_bytes, content_type = _compress_image(image_bytes)

    lens_data = await _call_serpapi_lens(image_bytes, content_type, country_code)
    product_query = _extract_product_query(lens_data)
    logger.info("Identify: Lens identified %r", product_query)

    # Classify to get the right size options
    from app.routes.classify import classify_product, SHOE_SIZES, CLOTHING_SIZES, COLORS
    product_type = classify_product(product_query or "")
    sizes = SHOE_SIZES if product_type == "shoe" else CLOTHING_SIZES if product_type == "clothing" else []

    return {
        "identified_as": product_query,
        "product_type": product_type,
        "sizes": sizes,
        "colors": COLORS,
        # Cleaned English term for external store links (Shein, Zara)
        "search_term": _clean_query_for_stores(product_query or ""),
    }


@router.post("/search/image")
async def search_by_image(
    file: UploadFile = File(...),
    country_code: str = Form(default="us"),
    memberships: str = Form(default=""),
    size: str = Form(default=""),
    color: str = Form(default=""),
):
    """
    Upload an image → Google Lens identifies the product →
    Google Shopping + Jack Kuba (if country=IL) + ASOS run in parallel →
    results merged and membership discounts applied.
    Optional size and color filters are appended to all search queries.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="file must be an image")

    image_bytes = await file.read()
    content_type = file.content_type or "image/jpeg"
    image_bytes, content_type = _compress_image(image_bytes)

    # Phase 1 — identify product via Google Lens
    lens_data = await _call_serpapi_lens(image_bytes, content_type, country_code)
    product_query = _extract_product_query(lens_data)
    logger.info("Lens identified product as: %r (size=%r, color=%r)", product_query, size, color)

    # Build filtered query
    filtered_query = _build_query_with_filters(product_query or "", size, color)

    # Phase 2 — run Google Shopping + local IL stores + ASOS in parallel
    shopping_items: list[dict] = []
    local_items: list[dict] = []
    asos_items: list[dict] = []

    tasks = []
    is_israel = country_code.lower() == "il"

    if filtered_query.strip():
        tasks.append(_call_serpapi({
            "engine": "google_shopping",
            "q": filtered_query,
            "hl": "en",
            "gl": country_code.lower(),
            "num": settings.top_k,
        }))
        if is_israel:
            # IL scrapers get only the base product name — color/size in English
            # break the Hebrew catalog search and cause 500s on long queries.
            tasks.append(_run_israel_scrapers(product_query or "", settings.top_k))
        tasks.append(_run_asos(filtered_query, country_code, settings.top_k))

    if tasks:
        results_raw = await asyncio.gather(*tasks, return_exceptions=True)
        idx = 0
        if not isinstance(results_raw[idx], Exception):
            shopping_items = results_raw[idx].get("shopping_results") or []
            logger.info("Google Shopping returned %d results for %r in %s",
                        len(shopping_items), filtered_query, country_code)
        idx += 1
        if is_israel and len(results_raw) > idx and not isinstance(results_raw[idx], Exception):
            local_items = results_raw[idx]
            logger.info("IL stores returned %d results for %r", len(local_items), filtered_query)
            idx += 1
        if len(results_raw) > idx and not isinstance(results_raw[idx], Exception):
            asos_items = results_raw[idx]
            logger.info("ASOS returned %d results for %r", len(asos_items), filtered_query)

    if not shopping_items and not local_items and not asos_items:
        logger.info("No results — falling back to Lens visual_matches")
        shopping_items = lens_data.get("visual_matches") or []

    shopping_results = _normalize_results(shopping_items[: settings.top_k])
    shopping_results = apply_discounts(shopping_results, _parse_memberships(memberships))
    local_items = apply_discounts(local_items, _parse_memberships(memberships))
    asos_items = apply_discounts(asos_items, _parse_memberships(memberships))

    # local_items are already relevance-ranked inside _run_israel_scrapers.
    # Keep them first (most relevant for IL users), then ASOS, then Shopping.
    merged = _merge_results(shopping_results, local_items, asos_items)
    merged = await _apply_currency(merged, country_code)
    return {
        "results": merged,
        "country_code": country_code,
        "identified_as": product_query,
        "search_term": _clean_query_for_stores(product_query or ""),
        "size": size or None,
        "color": color or None,
    }


@router.post("/search/text")
async def search_by_text(
    query: str = Form(...),
    country_code: str = Form(default="us"),
    memberships: str = Form(default=""),
    size: str = Form(default=""),
    color: str = Form(default=""),
):
    """
    Text query → Google Shopping + local IL stores (if country=IL) + ASOS in parallel →
    results merged and membership discounts applied.
    Optional size and color filters appended to the query.
    """
    if not query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")

    filtered_query = _build_query_with_filters(query, size, color)
    is_israel = country_code.lower() == "il"

    tasks: list = [_call_serpapi({
        "engine": "google_shopping",
        "q": filtered_query,
        "hl": "en",
        "gl": country_code.lower(),
        "num": settings.top_k,
    })]
    if is_israel:
        tasks.append(_run_israel_scrapers(filtered_query, settings.top_k))
    tasks.append(_run_asos(filtered_query, country_code, settings.top_k))

    results_raw = await asyncio.gather(*tasks, return_exceptions=True)

    shopping_items: list[dict] = []
    local_items: list[dict] = []
    asos_items: list[dict] = []

    idx = 0
    if not isinstance(results_raw[idx], Exception):
        shopping_items = results_raw[idx].get("shopping_results") or []
    idx += 1
    if is_israel and len(results_raw) > idx and not isinstance(results_raw[idx], Exception):
        local_items = results_raw[idx]
        idx += 1
    if len(results_raw) > idx and not isinstance(results_raw[idx], Exception):
        asos_items = results_raw[idx]

    shopping_results = _normalize_results(shopping_items[: settings.top_k])
    shopping_results = apply_discounts(shopping_results, _parse_memberships(memberships))
    local_items = apply_discounts(local_items, _parse_memberships(memberships))
    asos_items = apply_discounts(asos_items, _parse_memberships(memberships))

    merged = _merge_results(shopping_results, local_items, asos_items)
    merged = await _apply_currency(merged, country_code)
    return {
        "results": merged,
        "country_code": country_code,
        "size": size or None,
        "color": color or None,
    }


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
