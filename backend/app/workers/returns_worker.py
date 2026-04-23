import logging
import asyncio
from datetime import datetime
from collections import defaultdict
from bson import ObjectId
from celery import Task

from app.workers.celery_app import celery_app
from app.config import settings
from app.utils.crypto import decrypt_token
from app.utils.shopify_client import fetch_orders_with_refunds

logger = logging.getLogger(__name__)

NOTE_KEYWORDS = {
    "size_fit":   ["size", "fit", "small", "large", "tight", "loose", "short", "long"],
    "wrong_item": ["wrong", "mistake", "not what", "different", "incorrect", "not ordered"],
    "damaged":    ["broken", "damage", "defect", "not work", "cracked", "faulty", "scratched"],
    "quality":    ["quality", "cheap", "poor", "material", "bad"],
    "not_needed": ["changed mind", "no longer", "don't need", "dont need", "not needed"],
}

SHOPIFY_REASON_MAP = {
    "customer":  "not_needed",
    "inventory": "wrong_item",
    "fraud":     "fraud",
    "exchange":  "exchange",
    "other":     "other",
}


def _categorize_reason(shopify_reason: str, note: str) -> str:
    mapped = SHOPIFY_REASON_MAP.get(shopify_reason or "", "other")
    if mapped not in ("other", ""):
        return mapped
    note_lower = (note or "").lower()
    for reason, keywords in NOTE_KEYWORDS.items():
        if any(kw in note_lower for kw in keywords):
            return reason
    return "other"


def _generate_insights(return_rate, reason_counts, top_products, flagged_customers):
    insights = []
    total_reasons = sum(reason_counts.values()) or 1

    if return_rate < 5:
        insights.append(f"Excellent return rate of {return_rate}% — well below the e-commerce average of 15–20%.")
    elif return_rate < 15:
        insights.append(f"Return rate of {return_rate}% is within the normal range for e-commerce.")
    else:
        insights.append(f"Return rate of {return_rate}% is above the e-commerce average — prioritise the top reasons below.")

    if reason_counts:
        top_reason, top_count = max(reason_counts.items(), key=lambda x: x[1])
        pct = round(top_count / total_reasons * 100)
        labels = {
            "size_fit": "size/fit issues", "wrong_item": "wrong item shipped",
            "damaged": "damaged or defective items", "quality": "quality concerns",
            "not_needed": "customer changed mind", "fraud": "suspected fraud",
            "exchange": "exchange requests", "other": "unspecified reasons",
        }
        insights.append(f"{pct}% of returns cite {labels.get(top_reason, top_reason)} — consider addressing this in your product listings or fulfilment process.")

    if top_products:
        p = top_products[0]
        insights.append(
            f'"{p["title"]}" has the highest return rate at {p["return_rate"]}% '
            f'({p["total_returns"]} of {p["total_orders"]} orders).'
        )

    if flagged_customers:
        insights.append(
            f"{len(flagged_customers)} customer(s) flagged with a return rate above 30% — review their order history for potential abuse."
        )

    return insights


def get_sync_db():
    from pymongo import MongoClient
    client = MongoClient(settings.MONGO_URI)
    return client.get_default_database()


@celery_app.task(bind=True, name='app.workers.returns_worker.analyze_returns_task')
def analyze_returns_task(self: Task, analysis_id: str, shop_domain: str, encrypted_token: str):
    logger.info(f"🔄 Return analysis task started: {analysis_id}")
    try:
        db = get_sync_db()
        db.return_analyses.update_one(
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
            logger.info(f"✅ Return analysis {analysis_id} complete")
            return result
        finally:
            loop.close()

    except Exception as exc:
        logger.exception(f"❌ Return analysis {analysis_id} failed: {exc}")
        try:
            db.return_analyses.update_one(
                {"_id": ObjectId(analysis_id)},
                {"$set": {"status": "failed", "error_message": str(exc)}}
            )
        except Exception:
            pass
        raise


async def _analyze_async(analysis_id: str, shop_domain: str, access_token: str, db):
    if settings.DEV_MODE:
        from app.dev.mock_data import MOCK_ORDERS
        orders = MOCK_ORDERS
        logger.info(f"🧪 DEV MODE: using {len(orders)} mock orders")
    else:
        logger.info(f"📦 Fetching orders for {shop_domain} (last 90 days)…")
        orders = await fetch_orders_with_refunds(shop_domain, access_token, days_back=90)
        logger.info(f"✅ Fetched {len(orders)} orders")

    total_orders = len(orders)
    refunded_orders = [o for o in orders if o.get("refunds")]
    total_refunded = len(refunded_orders)
    return_rate = round(total_refunded / total_orders * 100, 1) if total_orders else 0.0

    reason_counts: dict[str, int] = defaultdict(int)
    total_refund_value = 0.0
    currency = "USD"

    # product_id → stats
    product_stats: dict[str, dict] = defaultdict(lambda: {
        "total": 0, "refunded": 0, "refund_value": 0.0,
        "reasons": defaultdict(int), "title": "", "handle": "", "image_url": None,
    })

    # customer_id → stats
    customer_stats: dict[str, dict] = defaultdict(lambda: {
        "total": 0, "refunded": 0, "name": "", "email": ""
    })

    # month "YYYY-MM" → stats
    month_stats: dict[str, dict] = defaultdict(lambda: {
        "orders": 0, "returns": 0, "refund_value": 0.0
    })

    for order in orders:
        month_key = (order.get("created_at") or "")[:7]
        if month_key:
            month_stats[month_key]["orders"] += 1

        currency = order.get("currency", "USD")
        cust = order.get("customer") or {}
        cust_id = str(cust.get("id", "")) if cust else ""
        if cust_id:
            customer_stats[cust_id]["total"] += 1
            customer_stats[cust_id]["name"] = (
                f"{cust.get('first_name', '')} {cust.get('last_name', '')}".strip()
            )
            customer_stats[cust_id]["email"] = cust.get("email", "")

        # line_item_id → product_id mapping
        li_to_pid: dict[str, str] = {}
        for li in order.get("line_items", []):
            pid = str(li.get("product_id") or "")
            if not pid:
                continue
            li_to_pid[str(li.get("id", ""))] = pid
            product_stats[pid]["title"] = li.get("title", "")
            product_stats[pid]["handle"] = li.get("handle", "")
            product_stats[pid]["total"] += 1
            if not product_stats[pid]["image_url"]:
                img = li.get("image") or {}
                product_stats[pid]["image_url"] = img.get("src")

        if not order.get("refunds"):
            continue

        if month_key:
            month_stats[month_key]["returns"] += 1
        if cust_id:
            customer_stats[cust_id]["refunded"] += 1

        for refund in order["refunds"]:
            reason = _categorize_reason(
                refund.get("reason", ""),
                refund.get("note", ""),
            )
            reason_counts[reason] += 1

            for rli in refund.get("refund_line_items", []):
                subtotal = float(rli.get("subtotal") or 0)
                total_refund_value += subtotal
                if month_key:
                    month_stats[month_key]["refund_value"] += subtotal
                pid = li_to_pid.get(str(rli.get("line_item_id", "")))
                if pid:
                    product_stats[pid]["refunded"] += 1
                    product_stats[pid]["refund_value"] += subtotal
                    product_stats[pid]["reasons"][reason] += 1

    # Top returned products (min 2 orders, sorted by return rate)
    top_products = []
    for pid, s in product_stats.items():
        if s["total"] < 2:
            continue
        rate = round(s["refunded"] / s["total"] * 100, 1) if s["total"] else 0.0
        top_reason = max(s["reasons"], key=s["reasons"].get) if s["reasons"] else "other"
        top_products.append({
            "product_id": pid,
            "title": s["title"],
            "handle": s["handle"],
            "image_url": s["image_url"],
            "total_orders": s["total"],
            "total_returns": s["refunded"],
            "return_rate": rate,
            "refund_value": round(s["refund_value"], 2),
            "top_reason": top_reason,
        })
    top_products.sort(key=lambda x: x["return_rate"], reverse=True)

    # Flagged customers (≥2 orders, ≥30% return rate)
    flagged = []
    for cid, s in customer_stats.items():
        if s["total"] < 2:
            continue
        rate = round(s["refunded"] / s["total"] * 100, 1)
        if rate >= 30:
            flagged.append({
                "customer_id": cid,
                "name": s["name"],
                "email": s["email"],
                "total_orders": s["total"],
                "total_returns": s["refunded"],
                "return_rate": rate,
                "risk_level": "high" if rate >= 60 else "medium",
            })
    flagged.sort(key=lambda x: x["return_rate"], reverse=True)

    # Monthly trend (sorted chronologically)
    trend = []
    for month, s in sorted(month_stats.items()):
        rate = round(s["returns"] / s["orders"] * 100, 1) if s["orders"] else 0.0
        trend.append({
            "month": month,
            "orders": s["orders"],
            "returns": s["returns"],
            "return_rate": rate,
            "refund_value": round(s["refund_value"], 2),
        })

    insights = _generate_insights(return_rate, dict(reason_counts), top_products, flagged)

    db.return_analyses.update_one(
        {"_id": ObjectId(analysis_id)},
        {"$set": {
            "status": "complete",
            "orders_analyzed": total_orders,
            "total_refunded": total_refunded,
            "return_rate": return_rate,
            "total_refund_value": round(total_refund_value, 2),
            "currency": currency,
            "reason_breakdown": dict(reason_counts),
            "top_returned_products": top_products[:20],
            "flagged_customers": flagged[:20],
            "monthly_trend": trend,
            "insights": insights,
            "completed_at": datetime.utcnow(),
        }}
    )

    return {"analysis_id": analysis_id, "return_rate": return_rate, "orders": total_orders}
