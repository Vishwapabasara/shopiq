"""
PricePulse — Google Shopping competitor price discovery via SerpAPI.
"""
import re
import asyncio
import logging
import httpx

logger = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search"

_STRIP_WORDS = {
    # sizes
    "xs", "sm", "md", "lg", "xl", "xxl", "2xl", "3xl", "s", "m", "l",
    "small", "medium", "large", "xsmall", "xlarge",
    # colors
    "black", "white", "navy", "blue", "red", "green", "grey", "gray",
    "pink", "beige", "brown", "purple", "yellow", "orange", "gold", "silver",
    "cream", "ivory", "teal", "coral", "mint", "rose", "mauve",
    # generic modifiers
    "new", "best", "top", "sale", "free", "premium", "pro", "plus", "deluxe",
    "classic", "signature", "limited", "edition", "special",
}


def build_search_query(title: str, product_type: str = "", vendor: str = "") -> str:
    """
    Build a clean, generic search query from a Shopify product title.
    Strips variant info, sizes, colors, and brand-specific words.
    """
    # Drop everything after an em-dash, en-dash, or slash-separated variant
    base = re.split(r'\s*[—–]\s*', title)[0]
    # Drop content in parentheses (e.g. "(Pack of 3)")
    base = re.sub(r'\([^)]*\)', '', base)
    # Tokenise and filter stopwords + single chars
    tokens = re.split(r'[\s/,]+', base.lower())
    tokens = [t for t in tokens if t and t not in _STRIP_WORDS and len(t) > 1]
    # Keep at most 5 descriptive tokens for best shopping signal
    query = " ".join(tokens[:5])
    # Append product_type if it adds context not already present
    if product_type:
        pt = product_type.lower().strip()
        if pt and pt not in query:
            query = f"{query} {pt}"
    return query.strip()


def _extract_price(raw: dict) -> float | None:
    """Extract a float price from a SerpAPI shopping result dict."""
    # SerpAPI sometimes provides extracted_price directly
    ep = raw.get("extracted_price")
    if isinstance(ep, (int, float)) and ep > 0:
        return float(ep)
    # Fall back to parsing the price string
    price_str = raw.get("price", "")
    match = re.search(r'[\d,]+\.?\d*', price_str.replace(",", ""))
    if match:
        try:
            return float(match.group())
        except ValueError:
            pass
    return None


async def fetch_competitor_prices(query: str, api_key: str) -> list[dict]:
    """
    Search Google Shopping via SerpAPI and return structured competitor prices.
    Returns a list of {competitor, url, price, currency, availability}.
    """
    params = {
        "engine": "google_shopping",
        "q": query,
        "api_key": api_key,
        "num": 10,
        "gl": "us",
        "hl": "en",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(SERPAPI_URL, params=params)
        if resp.status_code != 200:
            logger.warning(f"SerpAPI HTTP {resp.status_code} for '{query}'")
            return []
        data = resp.json()
    except Exception as exc:
        logger.warning(f"SerpAPI request failed for '{query}': {exc}")
        return []

    results = []
    for r in data.get("shopping_results", [])[:6]:
        price = _extract_price(r)
        if not price or price <= 0:
            continue
        results.append({
            "competitor": r.get("source") or r.get("seller") or "Unknown",
            "url": r.get("link", ""),
            "price": round(price, 2),
            "currency": "USD",
            "availability": "out_of_stock" if r.get("out_of_stock") else "in_stock",
        })
    return results


def classify_price_position(our_price: float, competitor_prices: list[dict]) -> tuple[str, float | None, float | None, float | None]:
    """
    Returns (status, min_price, avg_price, price_gap_pct).
    status: 'undercut' | 'competitive' | 'overpriced' | 'no_data'
    price_gap_pct: positive = we're more expensive than cheapest competitor
    """
    if not competitor_prices:
        return "no_data", None, None, None
    prices = [p["price"] for p in competitor_prices if p["price"] > 0]
    if not prices:
        return "no_data", None, None, None
    min_p = min(prices)
    avg_p = round(sum(prices) / len(prices), 2)
    gap_pct = round((our_price - min_p) / min_p * 100, 1)

    if gap_pct > 10:
        status = "overpriced"
    elif gap_pct > 3:
        status = "undercut"
    elif gap_pct < -5:
        status = "competitive"   # we're the cheapest
    else:
        status = "competitive"

    return status, round(min_p, 2), avg_p, gap_pct


def suggest_price(our_price: float, min_comp: float, avg_comp: float, status: str) -> float | None:
    """
    Generate a smart repricing suggestion.
    - overpriced: match just above average (stay a little premium)
    - undercut: match just below the cheapest to win
    - competitive: no change needed
    """
    if status == "overpriced":
        # Suggest avg × 1.02 — slightly above market average (maintains slight premium)
        suggestion = round(avg_comp * 1.02, 2)
        if suggestion < our_price:
            return suggestion
    if status == "undercut":
        # Suggest min × 0.98 — just under cheapest competitor to win on price
        suggestion = round(min_comp * 0.98, 2)
        if suggestion < our_price:
            return suggestion
    return None
