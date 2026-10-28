import csv
import json
from urllib.parse import quote
from playwright.sync_api import sync_playwright

from constants import URL


ASOS_SEARCH_URL = "https://www.asos.com/search/?q="
ASOS_PRODUCT_API = "/api/product/catalogue/v3/products"


def extract_product_price(data):
    """Extracts price info from ASOS product JSON."""
    product = data.get("product", {})
    price = product.get("price", {})

    current = price.get("current", {}).get("text", "N/A")
    previous = price.get("previous", {}).get("text", "N/A")
    discount = price.get("discount", {}).get("text", "")

    return f"Now {current}\nWas {previous} {discount}".strip()


def save_price(item_name: str):
    encoded = quote(item_name)
    search_url = f"{ASOS_SEARCH_URL}{encoded}"

    print(f"[INFO] Searching ASOS for: {item_name}")
    print(f"[INFO] URL: {search_url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        price_result = None

        def handle_response(response):
            nonlocal price_result

            try:
                url = response.url

                # PRODUCT PAGE API
                if ASOS_PRODUCT_API in url and response.status == 200:
                    data = response.json()
                    price_result = extract_product_price(data)
                    print("\n[✓] PRICE EXTRACTED FROM PRODUCT PAGE:")
                    print(price_result)
            except Exception:
                pass

        page.on("response", handle_response)

        # STEP 1 — Go to search page
        page.goto(search_url, wait_until="domcontentloaded")

        # STEP 2 — Click first product result
        try:
            page.wait_for_selector('[data-auto-id="productTile"]', timeout=8000)
            page.locator('[data-auto-id="productTile"]').first.click()
        except Exception:
            print("[!] No product tiles found.")
            browser.close()
            return

        # STEP 3 — Wait for product API to fire
        page.wait_for_timeout(5000)

        if price_result:
            print("\n[✓] FINAL RESULT:")
            print(price_result)
        else:
            print("\n[!] No price data captured from product page API.")

        input("Press Enter to close...")
        browser.close()

if __name__ == "__main__":
    SEARCH_ITEM = "River Island Bandeau hybrid maxi dress in brown"
    item = "Rare London exclusive sequin bandeau maxi dress in silver"
    # item = "ASOS DESIGN drape bandeau maxi dress"
    # 1. Define the search item here (or pass it dynamically)
    # SEARCH_ITEM = "River Island Bandeau hybrid maxi dress in brown"


    # # Build the formatted ASOS search URL automatically
    # ENCODED_QUERY = quote(item)
    # print(f"Encoded search query: {ENCODED_QUERY}")
    # TARGET_URL = f"{URL}search/?q={ENCODED_QUERY}"
    # print(f"Constructed ASOS search URL: {TARGET_URL}")

    extracted_products = []
    save_price(item)
    # pass