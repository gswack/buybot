"""
ASOS scraper via Apify — scrapyx/asos-products-scraper

ASOS blocks direct server-to-server HTTP requests (Akamai CDN).
Apify runs the scraper from cloud IPs with proper browser TLS fingerprinting,
bypassing the block. We call Apify's synchronous run endpoint which waits
for the actor to finish and streams results back in one response.

Apify actor: scrapyx/asos-products-scraper
Docs: https://apify.com/scrapyx/asos-products-scraper

ASOS store codes:
  uk  → GBP   us  → USD   de  → EUR   fr  → EUR
  il  → ILS  (Israeli storefront, currency ILS)

Country → ASOS store mapping:
  il → COM (ASOS doesn't have a dedicated IL store; uses the international
            COM storefront with ILS currency)
  gb → uk
  us → us
  default → COM
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

STORE = "ASOS"
ACTOR_ID = "scrapyx~asos-products-scraper"
APIFY_RUN_SYNC_URL = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"

# Map 2-letter country codes to ASOS store codes and currencies
COUNTRY_TO_STORE: dict[str, tuple[str, str]] = {
    "il": ("COM", "ILS"),
    "gb": ("UK",  "GBP"),
    "ie": ("UK",  "GBP"),
    "us": ("US",  "USD"),
    "ca": ("US",  "USD"),
    "de": ("DE",  "EUR"),
    "fr": ("FR",  "EUR"),
    "es": ("ES",  "EUR"),
    "it": ("IT",  "EUR"),
    "nl": ("NL",  "EUR"),
    "au": ("AU",  "AUD"),
}


def _parse_product(item: dict, position: int) -> dict | None:
    """
    Normalise a single Apify ASOS product record into the shared result shape.
    Returns None for non-product records (SEARCH_SUMMARY, ERROR).
    """
    if item.get("recordType") != "PRODUCT":
        return None

    name = item.get("name") or item.get("productName") or "Unknown"
    brand = item.get("brandName") or ""
    full_name = f"{brand} {name}".strip() if brand and brand.lower() not in name.lower() else name

    url = item.get("productUrl") or item.get("url") or "#"
    # Ensure absolute URL
    if url and not url.startswith("http"):
        url = f"https://www.asos.com{url}"

    # Images — Apify returns a list or a single imageUrl
    images = item.get("images") or []
    image_url = images[0] if images else item.get("imageUrl") or item.get("image")
    # ASOS image URLs may need the base prepended
    if image_url and not image_url.startswith("http"):
        image_url = f"https://images.asos-media.com/{image_url}"

    price = item.get("price")
    previous_price = item.get("previousPrice")  # original price when marked down
    currency = item.get("currency") or "GBP"

    # Normalise price to float
    try:
        price = float(price) if price is not None else None
    except (TypeError, ValueError):
        price = None
    try:
        previous_price = float(previous_price) if previous_price is not None else None
    except (TypeError, ValueError):
        previous_price = None

    is_marked_down = item.get("isMarkedDown", False)
    sale_price = price if is_marked_down and previous_price else None
    regular_price = previous_price if is_marked_down and previous_price else price

    return {
        "id": f"asos_{item.get('productId', position)}",
        "store": STORE,
        "name": full_name,
        "url": url,
        "image_url": image_url,
        "price": regular_price,
        "currency": currency,
        "sale_price": sale_price,
        "club_price": None,
        "club_discount_pct": None,
        # membership fields — populated by apply_discounts() if user has asos membership
        "membership_id": None,
        "membership_name": None,
        "membership_description": None,
        "discount_pct": 0.0,
        "discounted_price": None,
    }


async def search(query: str, country_code: str = "gb", max_results: int = 10) -> list[dict]:
    """
    Search ASOS via Apify and return up to max_results normalised product dicts.
    Returns [] silently if APIFY_API_TOKEN is not set or on any error.
    """
    if not settings.apify_api_token:
        logger.info("ASOS scraper skipped — APIFY_API_TOKEN not configured")
        return []

    asos_store, currency = COUNTRY_TO_STORE.get(country_code.lower(), ("COM", "USD"))

    actor_input = {
        "mode": "search",
        "store": asos_store.lower(),
        "keywords": [query],
        "pageLimit": min(max_results, 48),  # one page max for speed
        "maxPages": 1,
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                APIFY_RUN_SYNC_URL,
                json=actor_input,
                headers={"Authorization": f"Bearer {settings.apify_api_token}"},
                params={"format": "json", "clean": "true"},
            )
            if resp.status_code != 201:
                logger.error("Apify ASOS error %s: %s", resp.status_code, resp.text[:300])
                return []

            items = resp.json()

    except httpx.TimeoutException:
        logger.error("Apify ASOS request timed out for query %r", query)
        return []
    except Exception as exc:
        logger.error("Apify ASOS unexpected error for query %r: %s", query, exc)
        return []

    results = []
    for i, item in enumerate(items, start=1):
        parsed = _parse_product(item, i)
        if parsed:
            results.append(parsed)
        if len(results) >= max_results:
            break

    logger.info("ASOS (Apify): returned %d products for query %r in store %s",
                len(results), query, asos_store)
    return results
