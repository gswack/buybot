import json
from urllib.parse import quote
from playwright.sync_api import sync_playwright

ASOS_SEARCH_API = "api/product/search/v2/search"


def extract_price_from_search(data):
    """Extract price info from ASOS search API JSON."""
    products = data.get("products", [])
    if not products:
        return None

    first = products[0]
    price = first.get("price", {})

    current = price.get("current", {}).get("text", "N/A")
    previous = price.get("previous", {}).get("text", "N/A")
    discount = price.get("discount", {}).get("text", "")

    return {
        "name": first.get("name"),
        "id": first.get("id"),
        "now": current,
        "was": previous,
        "discount": discount
    }


def save_price(item_name: str):
    encoded = quote(item_name)
    search_url = f"https://www.asos.com/search/?q={encoded}"

    print(f"[INFO] Searching ASOS for: {item_name}")
    print(f"[INFO] URL: {search_url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)

        result = None

        def handle_response(response):
            nonlocal result
            url = response.url

            if ASOS_SEARCH_API in url and response.status == 200:
                data = response.json()
                result = extract_price_from_search(data)

        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
        page.on("response", handle_response)
        page.goto(search_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        if result:
            print("\n[✓] PRICE FOUND:")
            print(json.dumps(result, indent=2))
        else:
            print("\n[!] No price data captured.")

        input("Press Enter to close...")
        browser.close()


if __name__ == "__main__":
    item = "Nike Training one Dri-Fit"
    save_price(item)
