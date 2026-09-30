from playwright.sync_api import sync_playwright

from constants import URL


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    def handle_response(response):
        resource_type = response.request.resource_type

        if resource_type not in ("xhr", "fetch"):
            return

        try:
            content_type = response.headers.get("content-type", "")

            if "json" in content_type:
                body = response.text()

                if "products" in body or '"price"' in body:
                    print("\n========== POTENTIAL PRODUCT API ==========")
                    print("STATUS:", response.status)
                    print("METHOD:", response.request.method)
                    print("URL:", response.url)
                    print("CONTENT-TYPE:", content_type)
                    print("BODY:", body[:2000])

        except Exception:
            pass

    page.on("response", handle_response)

    page.goto(URL, wait_until="networkidle", timeout=30_000)
    page.wait_for_timeout(5_000)

    input("Press Enter to close...")
    browser.close()