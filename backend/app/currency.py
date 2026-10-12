"""
Currency conversion using the Frankfurter API (https://frankfurter.dev).
Free, no API key required, powered by ECB data. Updated daily.

Rates are cached in-memory for 6 hours to avoid hammering the API.
"""

import logging
import time

import httpx

logger = logging.getLogger(__name__)

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest"
CACHE_TTL = 6 * 60 * 60  # 6 hours

# Cache: {"expires": float, "rates": {from_currency: {to_currency: rate}}}
_rate_cache: dict = {}

# Currencies we care about converting from
SOURCE_CURRENCIES = ["USD", "GBP", "EUR", "AUD"]


async def _fetch_rates(target: str) -> dict[str, float]:
    """
    Fetch exchange rates from Frankfurter for all source currencies → target.
    Returns {source_currency: rate} e.g. {"USD": 3.72, "GBP": 4.05, "EUR": 4.50}
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                FRANKFURTER_URL,
                params={"symbols": target, "base": ",".join(SOURCE_CURRENCIES)},
            )
            if resp.status_code != 200:
                logger.error("Frankfurter error %s: %s", resp.status_code, resp.text[:200])
                return {}
            data = resp.json()
            # Frankfurter returns {base: {"rates": {target: rate}}} when multiple bases
            # But with a single ?base= it returns {rates: {target: rate}}
            # We need to call once per base currency
            return {data["base"]: data["rates"].get(target, 1.0)}
    except Exception as exc:
        logger.error("Frankfurter fetch failed: %s", exc)
        return {}


async def get_rates_to(target: str) -> dict[str, float]:
    """
    Get conversion rates from multiple currencies to target.
    Returns {source_currency: rate}, e.g. {"USD": 3.72, "GBP": 4.05}
    Cached for 6 hours.
    """
    cache_key = target.upper()
    entry = _rate_cache.get(cache_key)
    if entry and entry["expires"] > time.time():
        return entry["rates"]

    # Fetch each source currency → target
    import asyncio
    tasks = [_fetch_single_rate(src, target) for src in SOURCE_CURRENCIES]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    rates: dict[str, float] = {}
    for src, result in zip(SOURCE_CURRENCIES, results):
        if isinstance(result, float):
            rates[src] = result

    if rates:
        _rate_cache[cache_key] = {"expires": time.time() + CACHE_TTL, "rates": rates}
        logger.info("Fetched rates to %s: %s", target, rates)

    return rates


async def _fetch_single_rate(source: str, target: str) -> float:
    """Fetch the rate for one currency pair."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                FRANKFURTER_URL,
                params={"base": source, "symbols": target},
            )
            if resp.status_code != 200:
                return 1.0
            data = resp.json()
            return float(data["rates"].get(target, 1.0))
    except Exception:
        return 1.0


def convert_price(
    price: float | None,
    from_currency: str,
    to_currency: str,
    rates: dict[str, float],
) -> tuple[float | None, str]:
    """
    Convert a price to the target currency using pre-fetched rates.
    Returns (converted_price, to_currency) or (price, from_currency) if rate unavailable.
    """
    if price is None:
        return None, from_currency
    if from_currency.upper() == to_currency.upper():
        return price, from_currency
    rate = rates.get(from_currency.upper())
    if not rate:
        return price, from_currency
    return round(price * rate, 2), to_currency.upper()


def convert_results(results: list[dict], target_currency: str, rates: dict[str, float]) -> list[dict]:
    """
    Convert all price fields in a results list to target_currency.
    Modifies in place and returns the list.
    """
    for r in results:
        orig_currency = r.get("currency", "GBP")

        if r.get("price") is not None:
            r["price"], r["currency"] = convert_price(r["price"], orig_currency, target_currency, rates)

        if r.get("sale_price") is not None:
            r["sale_price"], _ = convert_price(r["sale_price"], orig_currency, target_currency, rates)

        if r.get("club_price") is not None:
            r["club_price"], _ = convert_price(r["club_price"], orig_currency, target_currency, rates)

        if r.get("discounted_price") is not None:
            r["discounted_price"], _ = convert_price(r["discounted_price"], orig_currency, target_currency, rates)

    return results
