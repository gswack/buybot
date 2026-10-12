"""
Panta Rei scraper — panta-rei.com

Israeli sportswear brand (Delta Galil), Magento store. Same engine as Jack Kuba.
The catalog is in Hebrew, so queries should be Hebrew where possible.

Price structure (from HTML inspection):
  - Price lives in <span class="price" data-price-amount="79.9">79.90 ₪</span>
  - Product link: <a class="product-item-link" href="...">name</a>
  - Image: <img class="product-image-photo" src="...">

Panta Rei has no public club/loyalty pricing exposed in search results,
so we only extract the regular (and sale, if present) price.
"""

import logging
import re
import urllib.parse

import httpx
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

STORE = "Panta Rei"
BASE_URL = "https://www.panta-rei.com"
SEARCH_URL = f"{BASE_URL}/catalogsearch/result/"
CURRENCY = "ILS"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _parse_shekel(text: str) -> float | None:
    """Extract a float from a shekel string like '79.90 ₪' or '1,298 ₪'."""
    if not text:
        return None
    cleaned = re.sub(r"[^\d.]", "", text.replace(",", ""))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _extract_prices(item: Tag) -> tuple[float | None, float | None]:
    """
    Extract (regular_price, sale_price) from a product item.
    Panta Rei uses data-price-amount on price spans. When an item is on sale,
    there are two distinct amounts: the higher is regular, the lower is sale.
    """
    amounts: list[float] = []

    # Prefer the structured data-price-amount attribute
    for span in item.select("span.price[data-price-amount], [data-price-amount]"):
        raw = span.get("data-price-amount")
        if raw:
            try:
                val = float(raw)
                if val > 0:
                    amounts.append(val)
            except (ValueError, TypeError):
                pass

    # Fallback: parse visible price text
    if not amounts:
        for span in item.select("span.price"):
            val = _parse_shekel(span.get_text(strip=True))
            if val and val > 0:
                amounts.append(val)

    if not amounts:
        return None, None

    amounts = sorted(set(amounts))
    if len(amounts) == 1:
        return amounts[0], None

    # Lowest is the effective/sale price, highest is the regular shelf price
    regular = amounts[-1]
    sale = amounts[0]
    # Only treat as a sale if meaningfully lower
    if sale < regular * 0.99:
        return regular, sale
    return regular, None


def _parse_product(item: Tag, position: int) -> dict | None:
    """Parse a single product item into the shared result dict shape."""
    # Panta Rei's theme uses a.product_link (not the Magento default
    # a.product-item-link). The product name lives in the link's title attribute.
    link_tag = item.select_one("a.product_link[href]") or item.select_one("a[href]")
    if not link_tag:
        return None

    url = link_tag.get("href") or "#"
    if url and not url.startswith("http"):
        url = f"{BASE_URL}{url}"

    # Name: prefer the title attribute (full name), fall back to link text
    name = ""
    for a in item.select("a.product_link"):
        if a.get("title"):
            name = a.get("title").strip()
            break
    if not name:
        name = link_tag.get_text(strip=True) or "Panta Rei item"

    img_tag = item.select_one("img.product-image-photo, img")
    image_url = img_tag.get("src") if img_tag else None

    regular_price, sale_price = _extract_prices(item)

    return {
        "id": f"pr_{position}",
        "store": STORE,
        "name": name,
        "url": url,
        "image_url": image_url,
        "price": regular_price,
        "currency": CURRENCY,
        "sale_price": sale_price,
        "club_price": None,
        "club_discount_pct": None,
        # membership fields for apply_discounts() compatibility
        "membership_id": None,
        "membership_name": None,
        "membership_description": None,
        "discount_pct": 0.0,
        "discounted_price": None,
    }


async def search(query: str, max_results: int = 10) -> list[dict]:
    """
    Search panta-rei.com for products matching `query`.
    Returns up to `max_results` parsed product dicts.
    """
    params = {"q": query}
    url = f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("Panta Rei scrape failed for query %r: %s", query, exc)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    items = soup.select("li.product-item, .product-item")

    if not items:
        logger.info("Panta Rei: no product items found for query %r", query)
        return []

    results = []
    for i, item in enumerate(items[:max_results], start=1):
        parsed = _parse_product(item, i)
        if parsed and parsed["price"] is not None:
            results.append(parsed)

    logger.info("Panta Rei: scraped %d products for query %r", len(results), query)
    return results
