"""
Coupon code endpoint.

POST /api/coupons
  Body: {"stores": ["ASOS", "Jack Kuba", ...]}
  Returns: {"coupons": {"ASOS": [...], "Jack Kuba": [...]}}

Each coupon entry:
  {
    "code":        "SAVE10",
    "description": "10% off your order at ASOS",
    "source":      "retailmenot.com",
    "source_url":  "https://www.retailmenot.com/...",
    "is_trusted":  true
  }
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.coupons import fetch_coupons_for_stores

router = APIRouter()


class CouponsRequest(BaseModel):
    stores: list[str]


@router.post("/coupons")
async def get_coupons(body: CouponsRequest):
    """
    Fetch active coupon codes for a list of store names.
    Results are cached per store for 4 hours to conserve SerpAPI credits.
    """
    if not body.stores:
        return {"coupons": {}}

    # Limit to 5 unique stores per request to cap credit usage
    unique_stores = list(dict.fromkeys(s.strip() for s in body.stores if s.strip()))[:5]
    coupons = await fetch_coupons_for_stores(unique_stores)
    return {"coupons": coupons}
