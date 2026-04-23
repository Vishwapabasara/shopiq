import math
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from bson import ObjectId
from celery import Task

from app.workers.celery_app import celery_app
from app.config import settings
from app.utils.crypto import decrypt_token
from app.utils.shopify_client import fetch_products_for_stock, fetch_orders_for_stock

logger = logging.getLogger(__name__)

LEAD_TIME_DAYS = 7
URGENT_DAYS = 14
MONITOR_DAYS = 30
DEAD_VELOCITY = 0.033   # < 1 sale per month


def _classify(daily_velocity: float, days_to_stockout) -> str:
    if daily_velocity < DEAD_VELOCITY:
        return "dead_stock"
    if days_to_stockout is None or days_to_stockout <= URGENT_DAYS:
        return "urgent"
    if days_to_stockout <= MONITOR_DAYS:
        return "monitor"
    return "healthy"


def _revenue_at_risk(price: float, velocity: float, days_to_stockout) -> float:
    if velocity == 0 or days_to_stockout is None:
        return 0.0
    if days_to_stockout >= URGENT_DAYS:
        return 0.0
    lost_days = max(0.0, URGENT_DAYS - days_to_stockout)
    return round(price * velocity * lost_days, 2)


def _velocity_trend(current: float, prev: float) -> str:
    if prev == 0 and current == 0:
        return "stable"
    if prev == 0:
        return "rising"
    if current == 0:
        return "falling"
    ratio = current / prev
    if ratio >= 1.15:
        return "rising"
    if ratio <= 0.85:
        return "falling"
    return "stable"


def _generate_insights(products, total_rar, dead_value, capital_efficiency):
    insights = []
    urgent = [p for p in products if p["status"] == "urgent"]
    dead = [p for p in products if p["status"] == "dead_stock"]

    if urgent:
        avg_days = round(
            sum(p["days_to_stockout"] or 0 for p in urgent) / len(urgent), 1
        )
        insights.append(
            f"{len(urgent)} SKU{'s' if len(urgent) != 1 else ''} face stockout within "
            f"{avg_days} days on average — reorder immediately to protect revenue."
        )
    else:
        insights.append("No SKUs are at urgent risk of stockout — stock levels are well managed.")

    if total_rar > 0:
        top = max(urgent, key=lambda p: p["revenue_at_risk"])
        insights.append(
            f"${total_rar:,.0f} in revenue is at risk over the next {URGENT_DAYS} days. "
            f'"{top["title"]}" is your most critical item (${top["revenue_at_risk"]:,.0f} at risk).'
        )

    if dead_value > 500:
        insights.append(
            f"${dead_value:,.0f} in capital is locked in dead or slow-moving stock. "
            "Consider discounting, bundling, or running a flash sale to free up cash flow."
        )

    if capital_efficiency < 60:
        insights.append(
            f"Capital efficiency is {capital_efficiency:.0f}% — more than a third of your "
            "inventory investment is in products not generating returns."
        )
    elif capital_efficiency < 80:
        insights.append(
            f"Capital efficiency is {capital_efficiency:.0f}% — moderate. "
            "Clearing dead stock would improve your inventory ROI."
        )
    else:
        insights.append(
            f"Capital efficiency is {capital_efficiency:.0f}% — healthy. "
            "Most of your inventory investment is actively generating sales."
        )

    rising = [p for p in products if p["velocity_trend"] == "rising" and p["status"] != "dead_stock"]
    if rising:
        top_r = max(rising, key=lambda p: p["daily_velocity"])
        insights.append(
            f'"{top_r["title"]}" demand is accelerating — ensure sufficient stock to capitalise.'
        )

    return insights


def get_sync_db():
    from pymongo import MongoClient
    client = MongoClient(settings.MONGO_URI)
    return client.get_default_database()


@celery_app.task(bind=True, name='app.workers.stock_worker.analyze_stock_task')
def analyze_stock_task(self: Task, analysis_id: str, shop_domain: str, encrypted_token: str):
    logger.info(f"📦 Stock analysis task started: {analysis_id}")
    try:
        db = get_sync_db()
        db.stock_analyses.update_one(
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
            logger.info(f"✅ Stock analysis {analysis_id} complete")
            return result
        finally:
            loop.close()

    except Exception as exc:
        logger.exception(f"❌ Stock analysis {analysis_id} failed: {exc}")
        try:
            db.stock_analyses.update_one(
                {"_id": ObjectId(analysis_id)},
                {"$set": {"status": "failed", "error_message": str(exc)}}
            )
        except Exception:
            pass
        raise


async def _analyze_async(analysis_id: str, shop_domain: str, access_token: str, db):
    if settings.DEV_MODE:
        logger.info("🧪 DEV MODE: using mock stock data")
        results = _build_mock_results()
    else:
        logger.info(f"📦 Fetching products & orders for {shop_domain}…")
        products_raw = await fetch_products_for_stock(shop_domain, access_token)
        orders_raw = await fetch_orders_for_stock(shop_domain, access_token)
        logger.info(f"✅ {len(products_raw)} products, {len(orders_raw)} orders fetched")
        results = _compute_analysis(products_raw, orders_raw)

    db.stock_analyses.update_one(
        {"_id": ObjectId(analysis_id)},
        {"$set": {
            **results,
            "status": "complete",
            "completed_at": datetime.utcnow(),
        }}
    )
    return {"analysis_id": analysis_id, "total_skus": results["total_skus"]}


def _compute_analysis(products_raw: list, orders_raw: list) -> dict:
    now = datetime.now(timezone.utc)
    cutoff_30d = now - timedelta(days=30)
    cutoff_60d = now - timedelta(days=60)

    # variant_id → {sold_30d, sold_prev30d}
    variant_sales: dict[str, dict] = defaultdict(lambda: {"sold_30d": 0, "sold_prev30d": 0})

    for order in orders_raw:
        created_raw = order.get("created_at", "")
        try:
            created = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
        except Exception:
            continue
        for li in order.get("line_items", []):
            vid = str(li.get("variant_id") or "")
            if not vid:
                continue
            qty = int(li.get("quantity") or 0)
            if created >= cutoff_30d:
                variant_sales[vid]["sold_30d"] += qty
            elif created >= cutoff_60d:
                variant_sales[vid]["sold_prev30d"] += qty

    products_out = []
    for product in products_raw:
        pid = str(product.get("id", ""))
        title = product.get("title", "")
        handle = product.get("handle", "")
        images = product.get("images", [])
        image_url = images[0].get("src") if images else None

        for variant in product.get("variants", []):
            vid = str(variant.get("id", ""))
            if variant.get("inventory_management") != "shopify":
                continue
            inv_qty = max(0, int(variant.get("inventory_quantity") or 0))
            price = float(variant.get("price") or 0)
            if price == 0:
                continue

            sales = variant_sales.get(vid, {"sold_30d": 0, "sold_prev30d": 0})
            sold_30d = sales["sold_30d"]
            sold_prev30d = sales["sold_prev30d"]
            velocity = round(sold_30d / 30, 3)
            prev_velocity = round(sold_prev30d / 30, 3)

            days_to_stockout = None
            if velocity > 0:
                days_to_stockout = round(inv_qty / velocity, 1)

            status = _classify(velocity, days_to_stockout)
            rar = _revenue_at_risk(price, velocity, days_to_stockout)
            trend = _velocity_trend(velocity, prev_velocity)

            reorder_qty = 0
            if status in ("urgent", "monitor"):
                target = velocity * (LEAD_TIME_DAYS + 30)
                reorder_qty = max(0, int(math.ceil((target - inv_qty) / 5)) * 5)

            variant_title = variant.get("title") or None
            if variant_title == "Default Title":
                variant_title = None

            full_title = f"{title} — {variant_title}" if variant_title else title

            products_out.append({
                "product_id": pid,
                "variant_id": vid,
                "title": full_title,
                "variant_title": variant_title,
                "handle": handle,
                "image_url": image_url,
                "sku": variant.get("sku") or "",
                "inventory_qty": inv_qty,
                "units_sold_30d": sold_30d,
                "units_sold_prev30d": sold_prev30d,
                "daily_velocity": velocity,
                "velocity_trend": trend,
                "days_to_stockout": days_to_stockout,
                "price": price,
                "revenue_at_risk": rar,
                "status": status,
                "abc_class": "C",   # filled in below
                "reorder_qty": reorder_qty,
            })

    # ABC classification by 30-day revenue contribution
    total_revenue_30d = sum(p["daily_velocity"] * p["price"] * 30 for p in products_out) or 1
    products_out.sort(key=lambda p: p["daily_velocity"] * p["price"], reverse=True)
    cumulative = 0.0
    for p in products_out:
        rev = p["daily_velocity"] * p["price"] * 30
        cumulative += rev / total_revenue_30d
        if cumulative <= 0.70:
            p["abc_class"] = "A"
        elif cumulative <= 0.90:
            p["abc_class"] = "B"
        else:
            p["abc_class"] = "C"

    # Sort: urgent → monitor → dead_stock → healthy
    order_map = {"urgent": 0, "monitor": 1, "dead_stock": 2, "healthy": 3}
    products_out.sort(key=lambda p: (order_map.get(p["status"], 9), -(p["revenue_at_risk"] or 0)))

    # Aggregate stats
    urgent_products = [p for p in products_out if p["status"] == "urgent"]
    dead_products = [p for p in products_out if p["status"] == "dead_stock"]

    total_rar = round(sum(p["revenue_at_risk"] for p in products_out), 2)
    dead_value = round(sum(p["inventory_qty"] * p["price"] for p in dead_products), 2)
    total_inv_value = round(sum(p["inventory_qty"] * p["price"] for p in products_out), 2)
    capital_efficiency = round((total_inv_value - dead_value) / total_inv_value * 100, 1) if total_inv_value else 0.0

    at_risk_days = [p["days_to_stockout"] for p in urgent_products if p["days_to_stockout"] is not None]
    avg_days = round(sum(at_risk_days) / len(at_risk_days), 1) if at_risk_days else 0.0

    insights = _generate_insights(products_out, total_rar, dead_value, capital_efficiency)

    return {
        "total_skus": len(products_out),
        "skus_urgent": len([p for p in products_out if p["status"] == "urgent"]),
        "skus_healthy": len([p for p in products_out if p["status"] == "healthy"]),
        "skus_monitor": len([p for p in products_out if p["status"] == "monitor"]),
        "skus_dead_stock": len([p for p in products_out if p["status"] == "dead_stock"]),
        "total_revenue_at_risk": total_rar,
        "dead_stock_value": dead_value,
        "total_inventory_value": total_inv_value,
        "capital_efficiency": capital_efficiency,
        "currency": "USD",
        "avg_days_to_stockout": avg_days,
        "products": products_out[:100],
        "insights": insights,
        "orders_analyzed": 0,
    }


def _build_mock_results() -> dict:
    """Pre-computed demo results for DEV_MODE and seed-demo endpoint."""
    products = [
        # ── URGENT ──────────────────────────────────────────────────────────────
        {
            "product_id": "p001", "variant_id": "v001",
            "title": "Running Leggings — Navy / S",
            "variant_title": "Navy / S", "handle": "running-leggings",
            "image_url": None, "sku": "RL-NVY-S",
            "inventory_qty": 1, "units_sold_30d": 45, "units_sold_prev30d": 38,
            "daily_velocity": 1.5, "velocity_trend": "rising",
            "days_to_stockout": 0.7, "price": 75.0,
            "revenue_at_risk": 997.5, "status": "urgent",
            "abc_class": "A", "reorder_qty": 50,
        },
        {
            "product_id": "p002", "variant_id": "v002",
            "title": "Slim Fit Oxford Shirt — White / M",
            "variant_title": "White / M", "handle": "slim-fit-oxford-shirt",
            "image_url": None, "sku": "SHIRT-WM",
            "inventory_qty": 3, "units_sold_30d": 36, "units_sold_prev30d": 30,
            "daily_velocity": 1.2, "velocity_trend": "rising",
            "days_to_stockout": 2.5, "price": 89.0,
            "revenue_at_risk": 845.5, "status": "urgent",
            "abc_class": "A", "reorder_qty": 60,
        },
        {
            "product_id": "p003", "variant_id": "v003",
            "title": "Wireless Earbuds Pro",
            "variant_title": None, "handle": "wireless-earbuds-pro",
            "image_url": None, "sku": "EAR-PRO-BLK",
            "inventory_qty": 5, "units_sold_30d": 27, "units_sold_prev30d": 25,
            "daily_velocity": 0.9, "velocity_trend": "stable",
            "days_to_stockout": 5.5, "price": 129.0,
            "revenue_at_risk": 694.8, "status": "urgent",
            "abc_class": "A", "reorder_qty": 30,
        },
        {
            "product_id": "p004", "variant_id": "v004",
            "title": "Bamboo Water Bottle — 750ml",
            "variant_title": "750ml", "handle": "bamboo-water-bottle",
            "image_url": None, "sku": "WATER-750",
            "inventory_qty": 4, "units_sold_30d": 18, "units_sold_prev30d": 14,
            "daily_velocity": 0.6, "velocity_trend": "rising",
            "days_to_stockout": 6.7, "price": 45.0,
            "revenue_at_risk": 215.7, "status": "urgent",
            "abc_class": "B", "reorder_qty": 25,
        },
        {
            "product_id": "p005", "variant_id": "v005",
            "title": "Organic Cotton Tote Bag",
            "variant_title": None, "handle": "organic-cotton-tote-bag",
            "image_url": None, "sku": "TOTE-ORG",
            "inventory_qty": 2, "units_sold_30d": 21, "units_sold_prev30d": 18,
            "daily_velocity": 0.7, "velocity_trend": "stable",
            "days_to_stockout": 2.8, "price": 35.0,
            "revenue_at_risk": 147.0, "status": "urgent",
            "abc_class": "B", "reorder_qty": 30,
        },
        # ── MONITOR ─────────────────────────────────────────────────────────────
        {
            "product_id": "p006", "variant_id": "v006",
            "title": "Silk Scrunchie Pack — Pink",
            "variant_title": "Pink", "handle": "silk-scrunchie-pack",
            "image_url": None, "sku": "SCRUNCH-PNK",
            "inventory_qty": 8, "units_sold_30d": 9, "units_sold_prev30d": 11,
            "daily_velocity": 0.3, "velocity_trend": "falling",
            "days_to_stockout": 26.7, "price": 22.0,
            "revenue_at_risk": 0.0, "status": "monitor",
            "abc_class": "C", "reorder_qty": 20,
        },
        {
            "product_id": "p007", "variant_id": "v007",
            "title": "Cork Yoga Block — Pair",
            "variant_title": "Pair", "handle": "cork-yoga-block",
            "image_url": None, "sku": "YOGA-CORK",
            "inventory_qty": 7, "units_sold_30d": 7, "units_sold_prev30d": 9,
            "daily_velocity": 0.23, "velocity_trend": "falling",
            "days_to_stockout": 30.4, "price": 48.0,
            "revenue_at_risk": 0.0, "status": "monitor",
            "abc_class": "C", "reorder_qty": 15,
        },
        {
            "product_id": "p008", "variant_id": "v008",
            "title": "Desk Planner 2025",
            "variant_title": None, "handle": "desk-planner-2025",
            "image_url": None, "sku": "PLAN-2025",
            "inventory_qty": 12, "units_sold_30d": 12, "units_sold_prev30d": 15,
            "daily_velocity": 0.4, "velocity_trend": "falling",
            "days_to_stockout": 30.0, "price": 19.0,
            "revenue_at_risk": 0.0, "status": "monitor",
            "abc_class": "C", "reorder_qty": 20,
        },
        {
            "product_id": "p009", "variant_id": "v009",
            "title": "Lavender Eye Pillow",
            "variant_title": None, "handle": "lavender-eye-pillow",
            "image_url": None, "sku": "EYE-LAV",
            "inventory_qty": 3, "units_sold_30d": 3, "units_sold_prev30d": 4,
            "daily_velocity": 0.1, "velocity_trend": "falling",
            "days_to_stockout": 30.0, "price": 18.0,
            "revenue_at_risk": 0.0, "status": "monitor",
            "abc_class": "C", "reorder_qty": 15,
        },
        # ── HEALTHY ─────────────────────────────────────────────────────────────
        {
            "product_id": "p010", "variant_id": "v010",
            "title": "Merino Wool Sweater — Grey / M",
            "variant_title": "Grey / M", "handle": "merino-wool-sweater",
            "image_url": None, "sku": "WOOL-GRY-M",
            "inventory_qty": 48, "units_sold_30d": 33, "units_sold_prev30d": 28,
            "daily_velocity": 1.1, "velocity_trend": "rising",
            "days_to_stockout": 43.6, "price": 95.0,
            "revenue_at_risk": 0.0, "status": "healthy",
            "abc_class": "A", "reorder_qty": 0,
        },
        {
            "product_id": "p011", "variant_id": "v011",
            "title": "Stainless Steel Mug 400ml",
            "variant_title": None, "handle": "stainless-steel-mug",
            "image_url": None, "sku": "MUG-400",
            "inventory_qty": 90, "units_sold_30d": 36, "units_sold_prev30d": 34,
            "daily_velocity": 1.2, "velocity_trend": "stable",
            "days_to_stockout": 75.0, "price": 38.0,
            "revenue_at_risk": 0.0, "status": "healthy",
            "abc_class": "A", "reorder_qty": 0,
        },
        {
            "product_id": "p012", "variant_id": "v012",
            "title": "Leather Notebook A5",
            "variant_title": None, "handle": "leather-notebook-a5",
            "image_url": None, "sku": "NOTE-A5",
            "inventory_qty": 62, "units_sold_30d": 24, "units_sold_prev30d": 22,
            "daily_velocity": 0.8, "velocity_trend": "stable",
            "days_to_stockout": 77.5, "price": 42.0,
            "revenue_at_risk": 0.0, "status": "healthy",
            "abc_class": "B", "reorder_qty": 0,
        },
        {
            "product_id": "p013", "variant_id": "v013",
            "title": "Yoga Mat — Purple",
            "variant_title": "Purple", "handle": "yoga-mat",
            "image_url": None, "sku": "MAT-PRP",
            "inventory_qty": 35, "units_sold_30d": 21, "units_sold_prev30d": 19,
            "daily_velocity": 0.7, "velocity_trend": "stable",
            "days_to_stockout": 50.0, "price": 68.0,
            "revenue_at_risk": 0.0, "status": "healthy",
            "abc_class": "B", "reorder_qty": 0,
        },
        {
            "product_id": "p014", "variant_id": "v014",
            "title": "Linen Throw Pillow — Sage",
            "variant_title": "Sage", "handle": "linen-throw-pillow",
            "image_url": None, "sku": "PILLOW-SGE",
            "inventory_qty": 28, "units_sold_30d": 15, "units_sold_prev30d": 14,
            "daily_velocity": 0.5, "velocity_trend": "stable",
            "days_to_stockout": 56.0, "price": 55.0,
            "revenue_at_risk": 0.0, "status": "healthy",
            "abc_class": "B", "reorder_qty": 0,
        },
        {
            "product_id": "p015", "variant_id": "v015",
            "title": "Natural Soy Candle Set",
            "variant_title": None, "handle": "natural-soy-candle-set",
            "image_url": None, "sku": "CANDLE-SET",
            "inventory_qty": 44, "units_sold_30d": 18, "units_sold_prev30d": 16,
            "daily_velocity": 0.6, "velocity_trend": "rising",
            "days_to_stockout": 73.3, "price": 28.0,
            "revenue_at_risk": 0.0, "status": "healthy",
            "abc_class": "C", "reorder_qty": 0,
        },
        # ── DEAD STOCK ──────────────────────────────────────────────────────────
        {
            "product_id": "p016", "variant_id": "v016",
            "title": "Oversized Blazer — Beige / XXL",
            "variant_title": "Beige / XXL", "handle": "oversized-blazer",
            "image_url": None, "sku": "BLZR-BGE-XXL",
            "inventory_qty": 22, "units_sold_30d": 1, "units_sold_prev30d": 0,
            "daily_velocity": 0.033, "velocity_trend": "stable",
            "days_to_stockout": None, "price": 145.0,
            "revenue_at_risk": 0.0, "status": "dead_stock",
            "abc_class": "C", "reorder_qty": 0,
        },
        {
            "product_id": "p017", "variant_id": "v017",
            "title": "Kids Craft Kit — Deluxe",
            "variant_title": "Deluxe", "handle": "kids-craft-kit",
            "image_url": None, "sku": "CRAFT-DLX",
            "inventory_qty": 67, "units_sold_30d": 2, "units_sold_prev30d": 3,
            "daily_velocity": 0.067, "velocity_trend": "falling",
            "days_to_stockout": None, "price": 39.0,
            "revenue_at_risk": 0.0, "status": "dead_stock",
            "abc_class": "C", "reorder_qty": 0,
        },
        {
            "product_id": "p018", "variant_id": "v018",
            "title": "Vintage Band Tee — Black / XS",
            "variant_title": "Black / XS", "handle": "vintage-band-tee",
            "image_url": None, "sku": "TEE-BLK-XS",
            "inventory_qty": 45, "units_sold_30d": 0, "units_sold_prev30d": 0,
            "daily_velocity": 0.0, "velocity_trend": "stable",
            "days_to_stockout": None, "price": 29.0,
            "revenue_at_risk": 0.0, "status": "dead_stock",
            "abc_class": "C", "reorder_qty": 0,
        },
        {
            "product_id": "p019", "variant_id": "v019",
            "title": "Metallic Pencil Case",
            "variant_title": None, "handle": "metallic-pencil-case",
            "image_url": None, "sku": "CASE-MET",
            "inventory_qty": 38, "units_sold_30d": 0, "units_sold_prev30d": 0,
            "daily_velocity": 0.0, "velocity_trend": "stable",
            "days_to_stockout": None, "price": 15.0,
            "revenue_at_risk": 0.0, "status": "dead_stock",
            "abc_class": "C", "reorder_qty": 0,
        },
        {
            "product_id": "p020", "variant_id": "v020",
            "title": "Cactus Print Tee — XL",
            "variant_title": "XL", "handle": "cactus-print-tee",
            "image_url": None, "sku": "CACTUS-XL",
            "inventory_qty": 6, "units_sold_30d": 6, "units_sold_prev30d": 9,
            "daily_velocity": 0.2, "velocity_trend": "falling",
            "days_to_stockout": 30.0, "price": 35.0,
            "revenue_at_risk": 0.0, "status": "monitor",
            "abc_class": "C", "reorder_qty": 10,
        },
    ]

    total_rar = round(sum(p["revenue_at_risk"] for p in products), 2)
    dead_value = round(sum(
        p["inventory_qty"] * p["price"]
        for p in products if p["status"] == "dead_stock"
    ), 2)
    total_inv_value = round(sum(p["inventory_qty"] * p["price"] for p in products), 2)
    capital_efficiency = round((total_inv_value - dead_value) / total_inv_value * 100, 1)
    urgent = [p for p in products if p["status"] == "urgent"]
    at_risk_days = [p["days_to_stockout"] for p in urgent if p["days_to_stockout"] is not None]
    avg_days = round(sum(at_risk_days) / len(at_risk_days), 1) if at_risk_days else 0.0

    insights = _generate_insights(products, total_rar, dead_value, capital_efficiency)

    return {
        "total_skus": len(products),
        "skus_urgent": len([p for p in products if p["status"] == "urgent"]),
        "skus_healthy": len([p for p in products if p["status"] == "healthy"]),
        "skus_monitor": len([p for p in products if p["status"] == "monitor"]),
        "skus_dead_stock": len([p for p in products if p["status"] == "dead_stock"]),
        "total_revenue_at_risk": total_rar,
        "dead_stock_value": dead_value,
        "total_inventory_value": total_inv_value,
        "capital_efficiency": capital_efficiency,
        "currency": "USD",
        "avg_days_to_stockout": avg_days,
        "products": products,
        "insights": insights,
        "orders_analyzed": 1840,
    }
