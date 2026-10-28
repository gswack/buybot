"""
Membership program definitions.

Each entry describes a store membership, what discount it gives,
and which store names (as returned by SerpAPI) it applies to.

To add a new program:
1. Add an entry to MEMBERSHIP_PROGRAMS
2. Add the store name variants to `store_aliases`
"""

from dataclasses import dataclass


@dataclass
class MembershipProgram:
    id: str                   # unique key used in API requests
    name: str                 # display name
    store: str                # canonical store name shown in UI
    store_aliases: list[str]  # lowercase substrings to match SerpAPI's "source" field
    discount_pct: float       # percentage off (e.g. 10.0 = 10%)
    description: str          # shown in the UI tooltip


MEMBERSHIP_PROGRAMS: list[MembershipProgram] = [
    MembershipProgram(
        id="asos_premier",
        name="ASOS Premier",
        store="ASOS",
        store_aliases=["asos"],
        discount_pct=0.0,  # Premier is free delivery, not a price discount
        description="Free unlimited next-day delivery on all orders",
    ),
    MembershipProgram(
        id="asos_student",
        name="ASOS Student Discount",
        store="ASOS",
        store_aliases=["asos"],
        discount_pct=10.0,
        description="10% off all ASOS orders with a valid student email",
    ),
    MembershipProgram(
        id="zara_member",
        name="Zara Member",
        store="Zara",
        store_aliases=["zara"],
        discount_pct=0.0,
        description="Early access to sales and new collections",
    ),
    MembershipProgram(
        id="zara_student",
        name="Zara Student Discount",
        store="Zara",
        store_aliases=["zara"],
        discount_pct=10.0,
        description="10% off at Zara with a valid student ID",
    ),
    MembershipProgram(
        id="jack_kuba_club",
        name="Jack Kuba Club",
        store="Jack Kuba",
        store_aliases=["jack kuba", "jackkuba", "jack-kuba"],
        discount_pct=10.0,
        description="10% off all Jack Kuba orders for club members (מועדון לקוחות)",
    ),
]

# Fast lookup: membership id → program
PROGRAMS_BY_ID: dict[str, MembershipProgram] = {p.id: p for p in MEMBERSHIP_PROGRAMS}


def apply_discounts(results: list[dict], membership_ids: list[str]) -> list[dict]:
    """
    For each result, check if any of the user's memberships apply to that store.
    If so, annotate the result with the best applicable discount.
    """
    if not membership_ids:
        return results

    active_programs = [
        PROGRAMS_BY_ID[mid] for mid in membership_ids if mid in PROGRAMS_BY_ID
    ]

    for result in results:
        store_lower = (result.get("store") or "").lower()
        best_discount = 0.0
        best_program = None

        for program in active_programs:
            if any(alias in store_lower for alias in program.store_aliases):
                if program.discount_pct > best_discount:
                    best_discount = program.discount_pct
                    best_program = program

        if best_program:
            result["membership_id"] = best_program.id
            result["membership_name"] = best_program.name
            result["membership_description"] = best_program.description
            result["discount_pct"] = best_program.discount_pct
            # Calculate discounted price
            if result.get("price") is not None and best_discount > 0:
                result["discounted_price"] = round(
                    result["price"] * (1 - best_discount / 100), 2
                )
            else:
                result["discounted_price"] = None
        else:
            result["membership_id"] = None
            result["membership_name"] = None
            result["membership_description"] = None
            result["discount_pct"] = 0.0
            result["discounted_price"] = None

    return results
