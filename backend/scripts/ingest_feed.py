"""
Ingest a product feed (CSV, Google Shopping / Rakuten-style schema) into
the `products` table, embedding each product's main image with CLIP.

Why embed the IMAGE (not the title text) for each catalog row:
CLIP puts text and images in the SAME vector space, so a user's text
query ("red running shoe") can still match a product's IMAGE embedding
reasonably well — and a user's photo upload matches it directly and
more precisely. Embedding the image once per product lets one column
serve both input modes, rather than needing two embedding columns.

Expected CSV columns (standard Google Shopping / most affiliate feeds):
    id, title, price, currency, image_link, link, brand (optional)

Usage:
    python scripts/ingest_feed.py path/to/asos_feed.csv --store asos
"""

import argparse
import asyncio
import csv
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
print(sys.path)

from app.database import close_db_pool, get_pool, init_db_pool  # noqa: E402
from app.embeddings import embed_image, load_model  # noqa: E402

BATCH_LOG_EVERY = 25


async def fetch_image_bytes(client: httpx.AsyncClient, url: str) -> bytes | None:
    try:
        resp = await client.get(url, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        return resp.content
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        print(f"  ! failed to fetch image {url}: {exc}")
        return None


def parse_price(raw: str) -> float | None:
    """Handles values like '29.99 GBP' or '£29.99' or '29.99'."""
    if not raw:
        return None
    cleaned = "".join(ch for ch in raw if ch.isdigit() or ch == ".")
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def parse_currency(raw: str, fallback: str = "GBP") -> str:
    if not raw:
        return fallback
    for code in ("GBP", "USD", "EUR", "ILS"):
        if code in raw.upper():
            return code
    return fallback


async def ingest(csv_path: Path, store: str) -> None:
    load_model()
    await init_db_pool()
    pool = get_pool()

    inserted = 0
    skipped = 0

    async with httpx.AsyncClient() as client:
        with csv_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for i, row in enumerate(reader, start=1):
                title = (row.get("title") or "").strip()
                image_url = (row.get("image_link") or "").strip()
                product_url = (row.get("link") or "").strip()
                raw_price = row.get("price") or ""

                if not title or not image_url or not product_url:
                    skipped += 1
                    continue

                image_bytes = await fetch_image_bytes(client, image_url)
                if image_bytes is None:
                    skipped += 1
                    continue

                try:
                    embedding = embed_image(image_bytes)
                except Exception as exc:  # noqa: BLE001 — log and continue on bad images
                    print(f"  ! failed to embed image for '{title}': {exc}")
                    skipped += 1
                    continue

                price = parse_price(raw_price)
                currency = parse_currency(raw_price)

                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO products (store, name, url, image_url, price, currency, embedding)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """,
                        store,
                        title,
                        product_url,
                        image_url,
                        price,
                        currency,
                        embedding,
                    )

                inserted += 1
                if i % BATCH_LOG_EVERY == 0:
                    print(f"  ...{i} rows processed ({inserted} inserted, {skipped} skipped)")

    await close_db_pool()
    print(f"Done. Inserted {inserted}, skipped {skipped}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a product feed into the products table")
    parser.add_argument("csv_path", type=Path, help="Path to the feed CSV file")
    parser.add_argument("--store", default="asos", help="Store name to tag these products with")
    args = parser.parse_args()

    if not args.csv_path.exists():
        print(f"File not found: {args.csv_path}")
        sys.exit(1)

    asyncio.run(ingest(args.csv_path, args.store))


if __name__ == "__main__":
    main()