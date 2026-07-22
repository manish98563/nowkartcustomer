"""Static UI grouping config: which Shopify collection handles should appear
under which Home-screen section heading / product rail. Handles are tried in
order; any that don't exist on the live store are skipped gracefully so the
UI never breaks even if a merchant hasn't created every collection yet.
"""

CATEGORY_GROUPS: dict[str, list[str]] = {
    "Snacks & Drinks": ["snacks", "beverages", "frozen", "dairy"],
    "Grocery & Kitchen": ["staples-grains", "spices-masalas", "condiments", "ready2eat"],
    "Fresh Essentials": ["fresh-produce", "dairy", "ready2eat"],
    "Asian Foods": ["asian-foods", "asian-groceries", "asian-imports", "asian-food"],
}

# For each rail, the first matching existing collection handle is used as the
# product source; if none exist yet, we fall back to a sitewide sorted query.
RAIL_COLLECTIONS: dict[str, list[str]] = {
    "Best Sellers": ["best-sellers", "bestsellers", "best-seller"],
    "New Arrivals": ["new-arrivals", "new-arrival", "new"],
}
