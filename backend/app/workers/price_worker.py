import asyncio
import logging
from datetime import datetime
from bson import ObjectId
from celery import Task

from app.workers.celery_app import celery_app
from app.config import settings
from app.utils.crypto import decrypt_token
from app.utils.shopify_client import fetch_all_products
from app.utils.price_scraper import (
    build_search_query,
    fetch_competitor_prices,
    classify_price_position,
    suggest_price,
)

logger = logging.getLogger(__name__)

MAX_PRODUCTS = 60   # cap per run to stay within API limits


def _generate_insights(products: list) -> list[str]:
    insights = []
    undercut = [p for p in products if p["status"] == "undercut"]
    overpriced = [p for p in products if p["status"] == "overpriced"]
    competitive = [p for p in products if p["status"] == "competitive"]
    no_data = [p for p in products if p["status"] == "no_data"]

    total_checked = len([p for p in products if p["status"] != "no_data"])
    if total_checked == 0:
        insights.append("No competitor data found — check that your SERPAPI_KEY is configured.")
        return insights

    comp_pct = round(len(competitive) / total_checked * 100) if total_checked else 0
    insights.append(
        f"{comp_pct}% of your checked products are competitively priced against live market data."
    )

    if overpriced:
        top = max(overpriced, key=lambda p: p.get("price_gap_pct") or 0)
        insights.append(
            f"{len(overpriced)} product{'s are' if len(overpriced) != 1 else ' is'} significantly overpriced. "
            f'"{top["title"]}" is {top["price_gap_pct"]:.0f}% above the cheapest competitor.'
        )

    if undercut:
        top = max(undercut, key=lambda p: p.get("price_gap_pct") or 0)
        insights.append(
            f"{len(undercut)} product{'s are' if len(undercut) != 1 else ' is'} being undercut. "
            f'Adjusting "{top["title"]}" alone could recover lost conversions.'
        )

    if no_data:
        insights.append(
            f"{len(no_data)} product{'s' if len(no_data) != 1 else ''} returned no competitor matches — "
            "these may be highly unique or branded items."
        )

    # Competitor frequency
    competitor_counts: dict[str, int] = {}
    for p in products:
        for c in p.get("competitor_prices", []):
            name = c["competitor"]
            competitor_counts[name] = competitor_counts.get(name, 0) + 1
    if competitor_counts:
        top_competitor = max(competitor_counts, key=competitor_counts.get)  # type: ignore[arg-type]
        insights.append(
            f'"{top_competitor}" appears most frequently across your catalogue '
            f"({competitor_counts[top_competitor]} products) — your primary market benchmark."
        )

    return insights


def get_sync_db():
    from pymongo import MongoClient
    client = MongoClient(settings.MONGO_URI)
    return client.get_default_database()


@celery_app.task(bind=True, name='app.workers.price_worker.analyze_prices_task')
def analyze_prices_task(self: Task, analysis_id: str, shop_domain: str, encrypted_token: str):
    logger.info(f"💰 Price analysis task started: {analysis_id}")
    try:
        db = get_sync_db()
        db.price_analyses.update_one(
            {"_id": ObjectId(analysis_id)},
            {"$set": {"status": "running", "updated_at": datetime.utcnow()}}
        )
        access_token = decrypt_token(encrypted_token)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                _analyze_async(analysis_id, shop_domain, access_token, db)
            )
            logger.info(f"✅ Price analysis {analysis_id} complete")
            return result
        finally:
            loop.close()
    except Exception as exc:
        logger.exception(f"❌ Price analysis {analysis_id} failed: {exc}")
        try:
            db.price_analyses.update_one(
                {"_id": ObjectId(analysis_id)},
                {"$set": {"status": "failed", "error_message": str(exc)}}
            )
        except Exception:
            pass
        raise


async def _analyze_async(analysis_id: str, shop_domain: str, access_token: str, db):
    if settings.DEV_MODE:
        logger.info("🧪 DEV MODE: using mock price data")
        results = _build_mock_results()
    else:
        api_key = settings.SERPAPI_KEY
        if not api_key:
            raise ValueError(
                "SERPAPI_KEY is not configured. Add it to your Railway environment variables."
            )
        logger.info(f"🛍️ Fetching products for {shop_domain}…")
        raw_products = await fetch_all_products(shop_domain, access_token)
        logger.info(f"✅ {len(raw_products)} products fetched, analysing up to {MAX_PRODUCTS}")
        results = await _compute_analysis(raw_products[:MAX_PRODUCTS], api_key, analysis_id, db)

    db.price_analyses.update_one(
        {"_id": ObjectId(analysis_id)},
        {"$set": {
            **results,
            "status": "complete",
            "completed_at": datetime.utcnow(),
        }}
    )
    return {"analysis_id": analysis_id, "total_products": results["total_products"]}


async def _compute_analysis(raw_products: list, api_key: str, analysis_id: str, db) -> dict:
    products_out = []

    for i, product in enumerate(raw_products):
        pid = str(product.get("id", ""))
        title = product.get("title", "")
        handle = product.get("handle", "")
        product_type = product.get("product_type", "")
        vendor = product.get("vendor", "")
        images = product.get("images", [])
        image_url = images[0].get("src") if images else None

        # Use the first active variant's price as "our price"
        variants = product.get("variants", [])
        if not variants:
            continue
        our_price = float(variants[0].get("price") or 0)
        if our_price <= 0:
            continue

        query = build_search_query(title, product_type, vendor)

        # Respect SerpAPI rate limits
        await asyncio.sleep(0.5)
        competitor_prices = await fetch_competitor_prices(query, api_key)

        status, min_comp, avg_comp, gap_pct = classify_price_position(our_price, competitor_prices)
        suggestion = suggest_price(our_price, min_comp or our_price, avg_comp or our_price, status)

        products_out.append({
            "product_id": pid,
            "title": title,
            "handle": handle,
            "image_url": image_url,
            "our_price": our_price,
            "search_query": query,
            "competitor_prices": competitor_prices,
            "min_competitor_price": min_comp,
            "avg_competitor_price": avg_comp,
            "price_gap_pct": gap_pct,
            "suggested_price": suggestion,
            "status": status,
            "competitors_count": len(competitor_prices),
        })

        # Update progress
        db.price_analyses.update_one(
            {"_id": ObjectId(analysis_id)},
            {"$set": {"products_analyzed": i + 1}}
        )

    return _aggregate(products_out)


def _aggregate(products: list) -> dict:
    insights = _generate_insights(products)

    # Competitor frequency map
    competitor_freq: dict[str, int] = {}
    for p in products:
        for c in p.get("competitor_prices", []):
            name = c["competitor"]
            competitor_freq[name] = competitor_freq.get(name, 0) + 1
    top_competitors = sorted(competitor_freq.items(), key=lambda x: x[1], reverse=True)[:8]

    return {
        "total_products": len(products),
        "products_analyzed": len(products),
        "products_undercut": len([p for p in products if p["status"] == "undercut"]),
        "products_competitive": len([p for p in products if p["status"] == "competitive"]),
        "products_overpriced": len([p for p in products if p["status"] == "overpriced"]),
        "products_no_data": len([p for p in products if p["status"] == "no_data"]),
        "avg_price_gap_pct": round(
            sum(p["price_gap_pct"] or 0 for p in products if p["price_gap_pct"] is not None)
            / max(1, len([p for p in products if p["price_gap_pct"] is not None])), 1
        ),
        "currency": "USD",
        "products": products,
        "top_competitors": [{"name": n, "count": c} for n, c in top_competitors],
        "insights": insights,
    }


def _build_mock_results() -> dict:
    """Pre-computed demo data for DEV_MODE and seed-demo endpoint."""
    products = [
        # ── OVERPRICED (we're much more expensive than market) ─────────────────
        {
            "product_id": "pp001", "title": "Wireless Noise-Cancelling Headphones",
            "handle": "wireless-noise-cancelling-headphones", "image_url": None,
            "our_price": 129.0, "search_query": "wireless noise cancelling headphones",
            "competitor_prices": [
                {"competitor": "Amazon", "url": "", "price": 79.99, "currency": "USD", "availability": "in_stock"},
                {"competitor": "Best Buy", "url": "", "price": 84.99, "currency": "USD", "availability": "in_stock"},
                {"competitor": "Walmart", "url": "", "price": 74.99, "currency": "USD", "availability": "in_stock"},
                {"competitor": "Newegg", "url": "", "price": 89.99, "currency": "USD", "availability": "in_stock"},
            ],
            "min_competitor_price": 74.99, "avg_competitor_price": 82.49,
            "price_gap_pct": 72.0, "suggested_price": 84.14,
            "status": "overpriced", "competitors_count": 4,
        },
        {
            "product_id": "pp002", "title": "Stainless Steel Insulated Water Bottle",
            "handle": "stainless-steel-water-bottle", "image_url": None,
            "our_price": 55.0, "search_query": "stainless steel insulated water bottle",
            "competitor_prices": [
                {"competitor": "Amazon", "url": "", "price": 28.99, "currency": "USD", "availability": "in_stock"},
                {"competitor": "Target", "url": "", "price": 32.99, "currency": "USD", "availability": "in_stock"},
                {"competitor": "REI", "url": "", "price": 34.95, "currency": "USD", "availability": "in_stock"},
            ],
            "min_competitor_price": 28.99, "avg_competitor_price": 32.31,
            "price_gap_pct": 89.7, "suggested_price": 32.96,
            "status": "overpriced", "competitors_count": 3,
        },
        {
            "product_id": "pp003", "title": "Yoga Mat",
            "handle": "yoga-mat", "image_url": None,
            "our_price": 89.0, "search_query": "yoga mat",
            "competitor_prices": [
                {"competitor": "Amazon", "url": "", "price": 45.99, "currency": "USD", "availability": "in_stock"},
                {"competitor": "Lululemon", "url": "", "price": 78.0, "currency": "USD", "availability": "in_stock"},
                {"competitor": "Target", "url": "", "price": 39.99, "currency": "USD", "availability": "in_stock"},
                {"competitor": "Dick's Sporting Goods", "url": "", "price": 49.99, "currency": "USD", "availability": "in_stock"},
            ],
            "min_competitor_price": 39.99, "avg_competitor_price": 53.49,
            "price_gap_pct": 122.5, "suggested_price": 54.56,
            "status": "overpriced", "competitors_count": 4,
        },
        # ── UNDERCUT (competitors slightly cheaper) ───────────────────────────
        {
            "product_id": "pp004", "title": "Slim Fit Oxford Shirt",
            "handle": "slim-fit-oxford-shirt", "image_url": None,
            "our_price": 89.0, "search_query": "slim fit oxford shirt",
            "competitor_prices": [
                {"competitor": "ASOS", "url": "", "price": 82.0, "currency": "USD", "availability": "in_stock"},
                {"competitor": "H&M", "url": "", "price": 79.99, "currency": "USD", "availability": "in_stock"},
                {"competitor": "Uniqlo", "url": "", "price": 85.0, "currency": "USD", "availability": "in_stock"},
            ],
            "min_competitor_price": 79.99, "avg_competitor_price": 82.33,
            "price_gap_pct": 11.3, "suggested_price": 80.68,
            "status": "undercut", "competitors_count": 3,
        },
        {
            "product_id": "pp005", "title": "Running Leggings",
            "handle": "running-leggings", "image_url": None,
            "our_price": 75.0, "search_query": "running leggings",
            "competitor_prices": [
                {"competitor": "Amazon", "url": "", "price": 68.99, "currency": "USD", "availability": "in_stock"},
                {"competitor": "Gymshark", "url": "", "price": 65.0, "currency": "USD", "availability": "in_stock"},
                {"competitor": "Under Armour", "url": "", "price": 69.99, "currency": "USD", "availability": "in_stock"},
            ],
            "min_competitor_price": 65.0, "avg_competitor_price": 67.99,
            "price_gap_pct": 15.4, "suggested_price": 66.65,
            "status": "undercut", "competitors_count": 3,
        },
        # ── COMPETITIVE (well priced) ─────────────────────────────────────────
        {
            "product_id": "pp006", "title": "Merino Wool Sweater",
            "handle": "merino-wool-sweater", "image_url": None,
            "our_price": 95.0, "search_query": "merino wool sweater",
            "competitor_prices": [
                {"competitor": "Everlane", "url": "", "price": 98.0, "currency": "USD", "availability": "in_stock"},
                {"competitor": "Amazon", "url": "", "price": 92.0, "currency": "USD", "availability": "in_stock"},
                {"competitor": "Nordstrom", "url": "", "price": 110.0, "currency": "USD", "availability": "in_stock"},
            ],
            "min_competitor_price": 92.0, "avg_competitor_price": 100.0,
            "price_gap_pct": 3.3, "suggested_price": None,
            "status": "competitive", "competitors_count": 3,
        },
        {
            "product_id": "pp007", "title": "Leather Notebook A5",
            "handle": "leather-notebook-a5", "image_url": None,
            "our_price": 42.0, "search_query": "leather notebook a5",
            "competitor_prices": [
                {"competitor": "Etsy", "url": "", "price": 44.99, "currency": "USD", "availability": "in_stock"},
                {"competitor": "Amazon", "url": "", "price": 39.99, "currency": "USD", "availability": "in_stock"},
                {"competitor": "Paper Source", "url": "", "price": 48.0, "currency": "USD", "availability": "in_stock"},
            ],
            "min_competitor_price": 39.99, "avg_competitor_price": 44.33,
            "price_gap_pct": 5.0, "suggested_price": None,
            "status": "competitive", "competitors_count": 3,
        },
        {
            "product_id": "pp008", "title": "Organic Cotton Tote Bag",
            "handle": "organic-cotton-tote-bag", "image_url": None,
            "our_price": 35.0, "search_query": "organic cotton tote bag",
            "competitor_prices": [
                {"competitor": "Etsy", "url": "", "price": 32.0, "currency": "USD", "availability": "in_stock"},
                {"competitor": "Amazon", "url": "", "price": 36.99, "currency": "USD", "availability": "in_stock"},
                {"competitor": "Redbubble", "url": "", "price": 38.0, "currency": "USD", "availability": "in_stock"},
            ],
            "min_competitor_price": 32.0, "avg_competitor_price": 35.66,
            "price_gap_pct": 9.4, "suggested_price": None,
            "status": "competitive", "competitors_count": 3,
        },
        {
            "product_id": "pp009", "title": "Bamboo Water Bottle",
            "handle": "bamboo-water-bottle", "image_url": None,
            "our_price": 45.0, "search_query": "bamboo water bottle",
            "competitor_prices": [
                {"competitor": "Amazon", "url": "", "price": 42.99, "currency": "USD", "availability": "in_stock"},
                {"competitor": "Etsy", "url": "", "price": 47.0, "currency": "USD", "availability": "in_stock"},
            ],
            "min_competitor_price": 42.99, "avg_competitor_price": 44.99,
            "price_gap_pct": 4.7, "suggested_price": None,
            "status": "competitive", "competitors_count": 2,
        },
        {
            "product_id": "pp010", "title": "Natural Soy Candle Set",
            "handle": "natural-soy-candle-set", "image_url": None,
            "our_price": 28.0, "search_query": "natural soy candle set",
            "competitor_prices": [
                {"competitor": "Etsy", "url": "", "price": 24.99, "currency": "USD", "availability": "in_stock"},
                {"competitor": "Amazon", "url": "", "price": 29.99, "currency": "USD", "availability": "in_stock"},
                {"competitor": "Target", "url": "", "price": 25.99, "currency": "USD", "availability": "in_stock"},
            ],
            "min_competitor_price": 24.99, "avg_competitor_price": 26.99,
            "price_gap_pct": 12.0, "suggested_price": None,
            "status": "competitive", "competitors_count": 3,
        },
        {
            "product_id": "pp011", "title": "Linen Throw Pillow",
            "handle": "linen-throw-pillow", "image_url": None,
            "our_price": 55.0, "search_query": "linen throw pillow",
            "competitor_prices": [
                {"competitor": "Wayfair", "url": "", "price": 52.0, "currency": "USD", "availability": "in_stock"},
                {"competitor": "IKEA", "url": "", "price": 49.99, "currency": "USD", "availability": "in_stock"},
                {"competitor": "Amazon", "url": "", "price": 58.0, "currency": "USD", "availability": "in_stock"},
            ],
            "min_competitor_price": 49.99, "avg_competitor_price": 53.33,
            "price_gap_pct": 10.0, "suggested_price": None,
            "status": "competitive", "competitors_count": 3,
        },
        # ── NO DATA ───────────────────────────────────────────────────────────
        {
            "product_id": "pp012", "title": "Artisan Soap Collection — Lavender & Oat",
            "handle": "artisan-soap-lavender-oat", "image_url": None,
            "our_price": 18.0, "search_query": "artisan soap collection",
            "competitor_prices": [],
            "min_competitor_price": None, "avg_competitor_price": None,
            "price_gap_pct": None, "suggested_price": None,
            "status": "no_data", "competitors_count": 0,
        },
        {
            "product_id": "pp013", "title": "Hand-Poured Beeswax Pillar Candle",
            "handle": "hand-poured-beeswax-pillar", "image_url": None,
            "our_price": 32.0, "search_query": "beeswax pillar candle",
            "competitor_prices": [],
            "min_competitor_price": None, "avg_competitor_price": None,
            "price_gap_pct": None, "suggested_price": None,
            "status": "no_data", "competitors_count": 0,
        },
    ]

    return _aggregate(products)
