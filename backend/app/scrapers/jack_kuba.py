"""
Jack Kuba scraper — jack-kuba.co.il

Scrapes the search results page and extracts structured product data
including regular price, club (loyalty) member price, and sale price.

Price structure per product (from HTML inspection):
  - Regular price:  <span class="price">857 ₪</span>  (first price span)
  - Sale price:     <span class="price max-price">342.80 ₪</span>  (when on sale)
  - Club label:     <span class="loyalty-price-label price-label">למועדון</span>
  - Club price:     <span class="price max-price">771.30 ₪</span>  (after club label)

The page also embeds JSON per product with:
  "loyalty_price": 771.3, "regular_price": 857
which we use as a more reliable fallback.
"""

import json
import logging
import re
import urllib.parse

import httpx
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

STORE = "Jack Kuba"
BASE_URL = "https://jack-kuba.co.il"
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
    """Extract a float from a shekel string like '771.30 ₪' or '1,298 ₪'."""
    if not text:
        return None
    cleaned = re.sub(r"[^\d.]", "", text.replace(",", ""))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _extract_json_prices(item: Tag) -> tuple[float | None, float | None]:
    """
    Extract regular_price and loyalty_price from the embedded Magento JSON
    inside a <script> tag within the product item.
    Returns (regular_price, loyalty_price).
    """
    for script in item.find_all("script"):
        text = script.string or ""
        # Look for loyalty_price in the JSON blob
        if "loyalty_price" not in text:
            continue
        # Extract the first occurrence of regular_price and loyalty_price
        reg_match = re.search(r'"regular_price"\s*:\s*([\d.]+)', text)
        loy_match = re.search(r'"loyalty_price"\s*:\s*([\d.]+)', text)
        try:
            regular = float(reg_match.group(1)) if reg_match else None
            loyalty = float(loy_match.group(1)) if loy_match else None
            return regular, loyalty
        except (ValueError, AttributeError):
            continue
    return None, None


def _parse_product(item: Tag, position: int) -> dict | None:
    """
    Parse a single <li class="product-item"> into a result dict.
    Returns None if essential fields (name, url) are missing.
    """
    # --- Name & URL ---
    link_tag = item.select_one("a.product-item-link")
    if not link_tag:
        return None
    name = link_tag.get_text(strip=True)
    url = link_tag.get("href") or "#"

    # --- Thumbnail ---
    img_tag = item.select_one("img.product-image-photo")
    image_url = img_tag.get("src") if img_tag else None

    # --- Prices from HTML spans ---
    # First price span = "lowest price" (finalPrice / sale price if on sale)
    # Regular price = second span with class "price" (not max-price)
    # Club price = span.price.max-price that follows span.loyalty-price-label

    price_spans = item.select("span.price")
    final_price: float | None = None
    regular_price: float | None = None

    if price_spans:
        final_price = _parse_shekel(price_spans[0].get_text(strip=True))
    if len(price_spans) >= 2:
        regular_price = _parse_shekel(price_spans[1].get_text(strip=True))

    # Club price: look for the loyalty label then grab the next price span
    club_price: float | None = None
    club_discount_pct: float | None = None
    loyalty_label = item.select_one("span.loyalty-price-label")
    if loyalty_label:
        # The club price span follows the label in the DOM
        next_price = loyalty_label.find_next("span", class_="price")
        if next_price:
            club_price = _parse_shekel(next_price.get_text(strip=True))
        # Discount percentage
        pct_tag = item.select_one("span.loyalty-price-loyalty-discounted")
        if pct_tag:
            pct_text = re.sub(r"[^\d.]", "", pct_tag.get_text(strip=True))
            try:
                club_discount_pct = float(pct_text) if pct_text else None
            except ValueError:
                pass

    # --- Fallback: JSON prices (more reliable for edge cases) ---
    json_regular, json_loyalty = _extract_json_prices(item)
    if regular_price is None and json_regular:
        regular_price = json_regular
    if club_price is None and json_loyalty:
        club_price = json_loyalty

    # Determine if final_price is a sale (meaningfully lower than regular)
    sale_price: float | None = None
    if (
        regular_price is not None
        and final_price is not None
        and final_price < regular_price * 0.99  # at least 1% discount
        and (club_price is None or abs(final_price - club_price) > 1)
    ):
        sale_price = final_price

    return {
        "id": f"jk_{position}",
        "store": STORE,
        "name": name,
        "url": url,
        "image_url": image_url,
        "price": regular_price or final_price,
        "currency": CURRENCY,
        "club_price": club_price,
        "club_discount_pct": club_discount_pct,
        "sale_price": sale_price,
        # membership fields for apply_discounts() compatibility
        "membership_id": "jack_kuba_club" if club_price else None,
        "membership_name": "Jack Kuba Club" if club_price else None,
        "membership_description": "10% off for club members (מועדון לקוחות)" if club_price else None,
        "discount_pct": club_discount_pct or 0.0,
        "discounted_price": club_price,  # pre-filled from scraped data
    }


async def search(query: str, max_results: int = 10) -> list[dict]:
    """
    Search jack-kuba.co.il for products matching `query`.
    Returns up to `max_results` parsed product dicts.
    """
    params = {"q": query}
    url = f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("Jack Kuba scrape failed for query %r: %s", query, exc)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    items = soup.select("li.product-item")

    if not items:
        logger.info("Jack Kuba: no product items found for query %r", query)
        return []

    results = []
    for i, item in enumerate(items[:max_results], start=1):
        parsed = _parse_product(item, i)
        if parsed:
            results.append(parsed)

    logger.info("Jack Kuba: scraped %d products for query %r", len(results), query)
    return results
