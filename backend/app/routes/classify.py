"""
Lightweight product type classifier.

Determines whether an identified product is a shoe, clothing, or unknown
based on keyword matching against the Lens-identified product name.
This drives the dynamic size selector on the frontend.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

# ── Keyword lists ──────────────────────────────────────────────────────────────

SHOE_KEYWORDS = {
    # English
    "shoe", "shoes", "sneaker", "sneakers", "trainer", "trainers",
    "boot", "boots", "heel", "heels", "sandal", "sandals", "loafer",
    "loafers", "slipper", "slippers", "mule", "mules", "clog", "clogs",
    "stiletto", "pump", "pumps", "oxford", "derby", "espadrille",
    "wedge", "platform", "flip flop", "flip-flop",
    # Hebrew
    "נעל", "נעליים", "סניקרס", "נעלי ספורט", "מגף", "מגפיים",
    "סנדל", "סנדלים", "כפכף", "כפכפים",
}

CLOTHING_KEYWORDS = {
    # English
    "shirt", "t-shirt", "tee", "top", "blouse", "dress", "skirt",
    "trousers", "pants", "jeans", "shorts", "jacket", "coat", "blazer",
    "hoodie", "sweatshirt", "sweater", "jumper", "cardigan", "vest",
    "bra", "underwear", "lingerie", "leggings", "tights", "socks",
    "pyjama", "pajama", "swimwear", "bikini", "bodysuit", "suit",
    "overalls", "dungarees", "romper", "playsuit", "kaftan",
    # Hebrew
    "חולצה", "שמלה", "חצאית", "מכנסיים", "ג׳ינס", "ז׳קט", "מעיל",
    "חזייה", "תחתון", "תחתונים", "לגינס", "גרביים", "בגד ים",
    "פיג׳מה", "סווטשירט", "קרדיגן",
}

SHOE_SIZES = [str(s) for s in range(35, 48)]   # EU 35–47
CLOTHING_SIZES = ["XS", "S", "M", "L", "XL", "XXL", "XXXL"]

COLORS = [
    "Black", "White", "Grey", "Navy", "Blue", "Red",
    "Green", "Beige", "Brown", "Pink", "Yellow", "Purple",
    "Orange", "Khaki", "Cream", "Burgundy",
]


# ── Classifier ─────────────────────────────────────────────────────────────────

def classify_product(identified_as: str) -> str:
    """
    Returns "shoe", "clothing", or "unknown" based on keyword matching.
    Case-insensitive. Matches on word boundaries using simple substring check
    against the lowercased product name.
    """
    if not identified_as:
        return "unknown"

    lower = identified_as.lower()

    for kw in SHOE_KEYWORDS:
        if kw in lower:
            return "shoe"

    for kw in CLOTHING_KEYWORDS:
        if kw in lower:
            return "clothing"

    return "unknown"


# ── Endpoint ───────────────────────────────────────────────────────────────────

class ClassifyRequest(BaseModel):
    identified_as: str


class ClassifyResponse(BaseModel):
    product_type: str        # "shoe" | "clothing" | "unknown"
    sizes: list[str]         # available size options for this type
    colors: list[str]        # always the same predefined list


@router.post("/classify", response_model=ClassifyResponse)
async def classify(body: ClassifyRequest):
    """
    Called by the frontend after Google Lens identifies a product.
    Returns the product type and the relevant size options to display.
    """
    product_type = classify_product(body.identified_as)
    sizes = SHOE_SIZES if product_type == "shoe" else CLOTHING_SIZES
    return ClassifyResponse(
        product_type=product_type,
        sizes=sizes,
        colors=COLORS,
    )
