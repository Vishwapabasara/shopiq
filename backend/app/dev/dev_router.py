"""
Dev-only routes — only mounted when DEV_MODE= True
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse

from app.dependencies import get_db
from app.services.audit_rules import run_rules, calculate_store_score, strip_html, word_count
from app.models.schemas import AuditStatus
from app.dev.mock_data import MOCK_PRODUCTS, MOCK_SHOP, MOCK_SHOP_DOMAIN

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dev", tags=["dev"])


def _now():
    return datetime.now(timezone.utc)


async def _db_op(coro_or_result):
    """Handle both async motor and sync mongomock results transparently."""
    import asyncio
    import inspect
    if inspect.isawaitable(coro_or_result):
        return await coro_or_result
    return coro_or_result


# ── Auto-login ────────────────────────────────────────────────────────────────

@router.get("/login")
async def dev_login(request: Request):
    """Skip OAuth — create demo tenant + session, redirect to dashboard."""
    db = await get_db()

    await _db_op(db.tenants.update_one(
        {"shop_domain": MOCK_SHOP_DOMAIN},
        {"$set": {
            "shop_domain": MOCK_SHOP_DOMAIN,
            "access_token": "mock_token_not_real",
            "scopes": "read_products,read_inventory,read_orders",
            "plan": "pro",
            "modules_enabled": ["audit", "returns", "stock", "price", "copy"],
            "shop_name": MOCK_SHOP["name"],
            "shop_email": MOCK_SHOP["email"],
            "installed_at": _now(),
            "updated_at": _now(),
        }},
        upsert=True,
    ))

    request.session["shop"] = MOCK_SHOP_DOMAIN
    logger.info("Dev auto-login: %s", MOCK_SHOP_DOMAIN)
    return {"ok": True, "shop": MOCK_SHOP_DOMAIN, "shop_name": MOCK_SHOP["name"], "plan": "pro"}


# ── Seed mock audit ───────────────────────────────────────────────────────────

@router.post("/seed-audit")
async def seed_audit(request: Request):
    """Run real rules engine on mock products, save completed audit to DB."""
    db = await get_db()

    tenant = await _db_op(db.tenants.find_one({"shop_domain": MOCK_SHOP_DOMAIN}))
    if not tenant:
        return JSONResponse({"error": "Run /dev/login first"}, status_code=400)

    # Run the real rules engine
    description_hashes: set = set()
    product_results = []

    for product in MOCK_PRODUCTS:
        issues, det_score = run_rules(product, description_hashes)
        body_text = strip_html(product.get("body_html") or "")
        seo = product.get("seo") or {}
        ai_data = _mock_ai_result(product, det_score)
        ai_score = ai_data["content_score"]
        blended = round(det_score * 0.6 + ai_score * 0.4)

        product_results.append({
            "shopify_product_id": str(product["id"]),
            "title": product.get("title", ""),
            "handle": product.get("handle", ""),
            "score": blended,
            "issues": [
                {"rule": i.rule, "category": i.category, "severity": i.severity.value,
                 "message": i.message, "fix_hint": i.fix_hint}
                for i in issues
            ],
            "image_count": len(product.get("images") or []),
            "word_count": word_count(body_text),
            "has_seo_title": bool(seo.get("title")),
            "has_meta_description": bool(seo.get("description")),
            "ai_score": ai_score,
            "ai_improvements": ai_data["improvements"],
            "ai_rewrite": ai_data["rewritten_description"],
            "ai_verdict": ai_data["one_line_verdict"],
        })

    product_results.sort(key=lambda x: x["score"])
    overall_score, category_scores = calculate_store_score(product_results)

    critical = sum(1 for p in product_results for i in p["issues"] if i["severity"] == "critical")
    warning  = sum(1 for p in product_results for i in p["issues"] if i["severity"] == "warning")
    info_c   = sum(1 for p in product_results for i in p["issues"] if i["severity"] == "info")

    audit_doc = {
        "tenant_id": str(tenant["_id"]),
        "status": AuditStatus.COMPLETE.value,
        "overall_score": overall_score,
        "category_scores": category_scores,
        "product_results": product_results,
        "products_scanned": len(MOCK_PRODUCTS),
        "critical_count": critical,
        "warning_count": warning,
        "info_count": info_c,
        "triggered_by": "manual",
        "created_at": _now(),
        "completed_at": _now(),
    }

    result = await _db_op(db.audits.insert_one(audit_doc))
    audit_id = str(result.inserted_id)

    logger.info("Dev audit seeded: %s (score %s/100)", audit_id, overall_score)

    return {
        "audit_id": audit_id,
        "overall_score": overall_score,
        "category_scores": category_scores,
        "products_scanned": len(MOCK_PRODUCTS),
        "critical_count": critical,
        "warning_count": warning,
        "info_count": info_c,
        "message": f"Seeded audit {audit_id}",
        "frontend_url": "/dashboard",
    }


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/status")
async def dev_status(request: Request):
    shop = request.session.get("shop")
    db = await get_db()
    tenant = await _db_op(db.tenants.find_one({"shop_domain": MOCK_SHOP_DOMAIN}))
    audit_count = 0
    if tenant:
        # count_documents may be sync in mongomock
        try:
            audit_count = await _db_op(db.audits.count_documents({"tenant_id": str(tenant["_id"])}))
        except Exception:
            pass
    return {
        "dev_mode": True,
        "session_shop": shop,
        "authenticated": shop == MOCK_SHOP_DOMAIN,
        "mock_products": len(MOCK_PRODUCTS),
        "audits_in_db": audit_count,
    }


# ── Reset ─────────────────────────────────────────────────────────────────────

@router.post("/reset")
async def dev_reset(request: Request):
    db = await get_db()
    tenant = await _db_op(db.tenants.find_one({"shop_domain": MOCK_SHOP_DOMAIN}))
    deleted = 0
    if tenant:
        result = await _db_op(db.audits.delete_many({"tenant_id": str(tenant["_id"])}))
        deleted = getattr(result, "deleted_count", 0)
    request.session.clear()
    return {"ok": True, "audits_deleted": deleted}


# ── Mock AI results ───────────────────────────────────────────────────────────

def _mock_ai_result(product: dict, det_score: int) -> dict:
    pid = product.get("id")
    results = {
        1001: {
            "content_score": 91,
            "improvements": [
                "Add specific care instructions — 'machine wash at 30°C, reshape while damp' converts better than just 'gentle cycle'",
                "Include a size guide with chest and length measurements — reduces returns significantly",
                "Add a sentence about delivery timeline for gift occasions — converts well during seasonal peaks",
            ],
            "rewritten_description": "<p>Experience unparalleled warmth in our <strong>100% New Zealand Merino Wool Crew Neck Sweater</strong>.</p><ul><li>Naturally odour-resistant and moisture-wicking merino wool</li><li>Ribbed cuffs and hem for a flattering, tailored silhouette</li><li>Available in 8 colours — sizes XS to 3XL</li><li>Machine washable at 30°C — reshape while damp</li><li>Ethically produced in Portugal under GOTS-certified conditions</li></ul><p>Transitions effortlessly from office to weekend. Ships in 2–3 days. Free UK delivery over £50.</p>",
            "one_line_verdict": "Near-perfect product page — add a size guide and specific care temperature to remove last friction points.",
        },
        1002: {
            "content_score": 5,
            "improvements": [
                "Replace 'New Product' with a specific, keyword-rich product name immediately",
                "Write a minimum 200-word description covering what the product is, who it's for, and key features",
                "Add at least 3 high-quality images before publishing — no images means zero conversion",
            ],
            "rewritten_description": "<p><em>This product needs a title, description, and images before it can convert.</em></p>",
            "one_line_verdict": "This product is not ready to sell — it has no title, no description, no images, and a zero price.",
        },
        1003: {
            "content_score": 38,
            "improvements": [
                "Expand the 7-word description to at least 150 words — cover leather type, dimensions, card capacity",
                "Add an SEO title and meta description — you're invisible to Google without them",
                "Add alt text to the product image — takes 5 seconds and helps both SEO and accessibility",
            ],
            "rewritten_description": "<p>Carry less, carry better. Our <strong>Leather Bifold Wallet</strong> is crafted from full-grain vegetable-tanned leather that develops a rich patina with use.</p><ul><li>Holds up to 8 cards in 4 card slots</li><li>Centre cash compartment fits notes flat</li><li>Full-grain leather — 1.2mm thickness for a slim profile</li><li>Dimensions: 11cm × 9cm × 8mm when empty</li></ul><p>Available in Black, Brown, and Tan.</p>",
            "one_line_verdict": "Seven-word description and no SEO fields — this product is invisible and unconvincing to buyers.",
        },
        1004: {
            "content_score": 74,
            "improvements": [
                "Add at least 2 more images — lifestyle shot during meal prep and one showing the juice groove in action",
                "Mention the board's weight so buyers know what to expect",
                "Add a compare-at price to show value",
            ],
            "rewritten_description": "<p>The <strong>Extra Large Bamboo Cutting Board</strong> gives serious home cooks the workspace they deserve. At 45cm × 30cm, there's room for a full chicken, a watermelon, or an entire meal prep session.</p><ul><li>45cm × 30cm × 2cm — generous workspace</li><li>100% Moso bamboo — harder than maple, renews in 3–5 years</li><li>Perimeter juice groove catches runoff</li><li>Non-slip rubber feet</li><li>Pre-oiled with food-grade mineral oil</li></ul>",
            "one_line_verdict": "Strong product with good content — one image is the single biggest conversion blocker here.",
        },
        1005: {
            "content_score": 77,
            "improvements": [
                "Fix the 2 missing alt texts — they're losing image search SEO value",
                "Add paper filter compatibility note — 'works with size 4 filters' answers buyer hesitation",
                "Include brew time and grind size recommendation",
            ],
            "rewritten_description": "<p>Your morning coffee deserves better. Our <strong>Handcrafted Ceramic Pour-Over Set</strong> is wheel-thrown by artisan potters in our Bristol studio.</p><ul><li>Wide-cone dripper for even extraction</li><li>600ml borosilicate carafe</li><li>Two 200ml cups</li><li>Compatible with size 4 paper filters</li><li>Dishwasher and microwave safe</li></ul>",
            "one_line_verdict": "Compelling product with good copy — 2 missing alt texts and filter details are the only gaps.",
        },
        1006: {
            "content_score": 82,
            "improvements": [
                "Restock before peak season — a product at zero inventory loses sales and SEO ranking",
                "Add a 'notify me when back in stock' call-to-action",
                "Include the Edison bulb wattage spec",
            ],
            "rewritten_description": "<p>The <strong>Vintage Brass Desk Lamp</strong> brings focused warmth and serious character to any desk. Inspired by 1920s industrial workshops.</p><ul><li>Solid brass — develops a natural patina over time</li><li>Adjustable arm extends up to 45cm</li><li>360° rotating head</li><li>Compatible with E27 bulbs up to 60W</li><li>4m fabric-wrapped cord with inline switch</li></ul>",
            "one_line_verdict": "Excellent product page — publishing at zero inventory means customers land on a dead end.",
        },
        1007: {
            "content_score": 68,
            "improvements": [
                "Add product tags immediately — 'water-bottle, hydration, gym, hiking, BPA-free' takes 30 seconds",
                "Set the product type to 'Drinkware' — required for automated collections",
                "Add a compare-at price to anchor value",
            ],
            "rewritten_description": "<p>The <strong>HydraFlow 750ml Insulated Water Bottle</strong> keeps cold drinks cold for 24 hours and hot drinks hot for 12.</p><ul><li>750ml — ideal all-day capacity</li><li>Double-wall vacuum insulation</li><li>18/8 food-grade stainless steel — BPA-free</li><li>Wide-mouth opening — fits ice cubes</li><li>Leak-proof lid with carry loop</li></ul>",
            "one_line_verdict": "Good product and solid description — no tags and no product type make it invisible inside your own store.",
        },
        1008: {
            "content_score": 42,
            "improvements": [
                "Write a unique description differentiating Small from Large — dimensions and use case should differ",
                "Add a compare-at price — even a small crossed-out price lifts conversion on low-price items",
                "Expand from 38 words to at least 150 — cover GSM weight, handle length, dimensions",
            ],
            "rewritten_description": "<p>The <strong>EcoCarry Small Tote</strong> is your everyday essential. Made from 280GSM organic cotton canvas.</p><ul><li>Dimensions: 38cm × 42cm × 10cm</li><li>60cm reinforced cotton handles</li><li>Carries up to 15kg without stretching</li><li>100% organic cotton — GOTS certified</li><li>Machine washable at 40°C</li></ul>",
            "one_line_verdict": "Identical description to the Large variant will hurt both products in Google — they need unique copy.",
        },
        1009: {
            "content_score": 44,
            "improvements": [
                "This description is identical to the Small variant — Google will penalise both for duplicate content",
                "Write unique copy highlighting the Large's capacity advantage",
                "Add weight capacity and exact dimensions",
            ],
            "rewritten_description": "<p>The <strong>EcoCarry Large Tote</strong> handles your biggest days — 50% more capacity than our Small.</p><ul><li>Dimensions: 45cm × 50cm × 15cm</li><li>65cm reinforced handles</li><li>Carries up to 20kg</li><li>100% organic cotton — GOTS certified</li><li>Machine washable at 40°C</li></ul>",
            "one_line_verdict": "Duplicate description shared with the Small variant is actively harming your Google rankings.",
        },
        1010: {
            "content_score": 79,
            "improvements": [
                "SEO title is 88 characters — Google truncates at ~60. Shorten to 'Hand-Poured Soy Wax Candle | EdinburghWick'",
                "Add a compare-at price — candles are a gift category where perceived value matters",
                "Include a first-use tip: 'trim wick to 5mm before each burn' reduces negative reviews",
            ],
            "rewritten_description": "<p>Our <strong>Hand-Poured Soy Wax Candles</strong> fill your space with pure essential oil fragrance — never synthetic.</p><ul><li>200g natural soy wax — vegan, cruelty-free</li><li>100% pure essential oils</li><li>Cotton wick — lead and zinc free</li><li>Burns up to 50 hours (trim wick to 5mm before each use)</li><li>Reusable glass vessel</li></ul>",
            "one_line_verdict": "Strong product with great copy — the 88-character SEO title is getting truncated in every Google result.",
        },
        1011: {
            "content_score": 72,
            "improvements": [
                "SEO title 'Denim Jacket' is only 12 characters — you're losing every long-tail search",
                "Add 6+ more tags — 'upcycled, patchwork, one-of-a-kind, handmade, Manchester, unisex'",
                "Add a compare-at price — at £185 buyers need value anchoring",
            ],
            "rewritten_description": "<p>Every <strong>Recycled Denim Patchwork Jacket</strong> is genuinely one-of-a-kind, made in our Manchester workshop from reclaimed denim offcuts.</p><ul><li>100% reclaimed denim offcuts — zero new fabric used</li><li>Fully lined with recycled polyester</li><li>Unisex relaxed fit — size down if between sizes</li><li>Each jacket photographed individually</li><li>~6 hours of handwork per jacket</li></ul>",
            "one_line_verdict": "Great product with excellent copy — a 12-character SEO title is making you invisible on Google.",
        },
        1012: {
            "content_score": 76,
            "improvements": [
                "Add a compare-at price — at £65, a crossed-out £85 RRP anchors value immediately",
                "Include the shelf weight so buyers know what they're handling",
                "Add install time estimate — 'installs in under 20 minutes' removes a key objection",
            ],
            "rewritten_description": "<p>The <strong>OakAndWood Solid Oak Floating Shelf</strong> brings warmth to any room with no visible fixings.</p><ul><li>FSC-certified solid European oak</li><li>Three lengths: 60cm, 90cm, 120cm — 20cm depth</li><li>Hidden bracket system — installs in under 20 minutes</li><li>Hard-wax oil finish — water-resistant and food-safe</li><li>Weight capacity: 15kg per shelf</li></ul>",
            "one_line_verdict": "Solid product page — no compare-at price is the single biggest missed conversion opportunity.",
        },
    }

    return results.get(pid, {
        "content_score": max(20, det_score - 10),
        "improvements": [
            "Add a detailed product description of at least 150 words",
            "Set an SEO title and meta description",
            "Add high-quality images with descriptive alt text",
        ],
        "rewritten_description": "<p>This product needs a more detailed description to convert effectively.</p>",
        "one_line_verdict": "This product page needs significant content improvement before it will convert.",
    })
