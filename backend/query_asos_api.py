import requests


def query_asos_api(url: str) -> dict | None:
    """
    Queries the ASOS API for products based on the provided URL and returns the response data.

    args:
        url (str): The URL of the ASOS API endpoint to query.
    """

    params = {
        "q": "nike shoes",
        "store": "US",
        "lang": "en-US",
        "currency": "USD",
        "offset": "0",
        "limit": "72"
    }

    headers = {
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json"
    }

    try:
        print(f"Sending request to ASOS API: {url} with params: {params}")

        response = requests.get(url, headers=headers, params=params, timeout=(5, 99))
        response.raise_for_status()

        if response.status_code == 200:
            print(response.json())
            data = response.json()
            prices = dict()
            for item in data.get("products", []):
                print(item)
                name = item.get("name")
                price = item.get("price", {}).get("current", {}).get("text")
                print(f"• {name} ---> {price}")
                prices[name] = price
            return prices
                
        else:
            print(f"Request blocked or failed with status code: {response.status_code}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"An error occurred while querying the ASOS API: {e}")
        return None


if __name__ == "__main__":
    url = "https://www.asos.com/api/product/search/v2/search?query=nike%20shoes&store=US&lang=en-US&currency=USD&offset=0&limit=72"
    query_asos_api(url)
