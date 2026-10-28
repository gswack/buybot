import csv
import json
from playwright.sync_api import sync_playwright

from constants import URL2

extracted_products = []


def extract_prices_from_json(data, url):
    """Parses JSON data and appends product records to extracted_products list."""
    if isinstance(data, dict) and "products" in data:
        print(f"Num of products found: {len(data['products'])}")
        for item in data["products"]:
            name = item.get("name", "Unknown Product").strip()
            price_info = item.get("price", {})
            current_price = (
                price_info.get("current", {}).get("text")
                or price_info.get("raw", {}).get("text")
                or "N/A"
            ).strip()

            extracted_products.append({"name": name, "price": current_price, "url": url})
            print(f"• {name} ---> {current_price}")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    def handle_response(response):
        MIN_PRODUCT_COUNT = 10  # Main search grids always return well above 10 items

        if response.request.resource_type not in ("xhr", "fetch"):
            return

        try:
            if response.status == 200 and "json" in response.headers.get("content-type", ""):
                data = response.json()
                products = data.get("products", [])

                # Ignore small widget payloads (< 10 items)
                if len(products) >= MIN_PRODUCT_COUNT:
                    print(f"[✓] Main product payload found ({len(products)} items)")
                    extract_prices_from_json(data, extracted_products)
                else:
                    print(f"[!] Ignored small payload ({len(products)} items) from {response.url}")
        except Exception:
            pass
        # if response.request.resource_type not in ("xhr", "fetch"):
        #     return

        # try:
        #     content_type = response.headers.get("content-type", "")

        #     if "json" in content_type and response.status == 200:
        #         data = response.json()

        #     if isinstance(data, dict) and "products" in data:
        #         print("\n=== PRODUCT RESPONSE ===")
        #         print("URL:", response.url)
        #         print("Top-level keys:", list(data.keys()))
        #         print("Number of products:", len(data["products"]))
        #     if isinstance(data, dict) and "products" in data:
        #         print(
        #             f"PRODUCT JSON: {response.request.method} "
        #             f"{response.status} {response.url}"
        #         )
        #         print(f"Products: {len(data['products'])}")

        #         extract_prices_from_json(data, response.url)

        # except Exception as e:
        #     print(f"[!] Error occurred while processing response: {e}")

    page.on("response", handle_response)

    try:
        page.goto(URL2, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(5_000)
    except Exception as e:
        print(f"[!] Navigation timed out or encountered an issue, but continuing: {e}")

    # Export collected data to CSV
    if extracted_products:
        output_filename = "asos_products.csv"
        with open(output_filename, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=["name", "price", "url"])
            writer.writeheader()
            writer.writerows(extracted_products)
        print(f"\n[✓] Successfully saved {len(extracted_products)} items to {output_filename}")
    else:
        print("\n[!] No products were extracted to save.")

    input("Press Enter to close...")
    browser.close()
