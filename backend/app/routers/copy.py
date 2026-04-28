"""
BulkCopy AI — REST Router
──────────────────────────
POST /copy/generate              — start a generation session
GET  /copy/latest                — latest session for this tenant
GET  /copy/{id}/status           — poll generation progress
GET  /copy/{id}/results          — full results when complete
PATCH /copy/{id}/product/{pid}   — save in-place edit
POST /copy/{id}/push             — push selected products to Shopify
"""
import inspect
import logging
from datetime import datetime

import httpx
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.dependencies import get_current_tenant, get_db
from app.utils.crypto import decrypt_token
from app.utils.shopify_client import SHOPIFY_API_VERSION, shopify_headers

router = APIRouter(prefix="/copy", tags=["copy"])
logger = logging.getLogger(__name__)


async def aw(result):
    if inspect.isawaitable(result):
        return await result
    return result


# ── Request models ────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    filter_mode: str = "low_score"      # 'all' | 'low_score' | 'selected'
    product_ids: list[str] | None = None
    max_products: int = 20


class PushRequest(BaseModel):
    product_ids: list[str]


class EditRequest(BaseModel):
    edited_description: str


# ── POST /copy/generate ───────────────────────────────────────────────────────

@router.post("/generate")
async def generate(body: GenerateRequest, tenant: dict = Depends(get_current_tenant)):
    db = await get_db()
    tenant_id = str(tenant["_id"])

    running = await aw(db.copy_sessions.find_one({
        "tenant_id": tenant_id,
        "status": {"$in": ["queued", "running"]},
    }))
    if running:
        return {
            "session_id": str(running["_id"]),
            "status": running["status"],
            "message": "Generation already in progress",
        }

    now = datetime.utcnow()
    doc = {
        "tenant_id": tenant_id,
        "shop_domain": tenant["shop_domain"],
        "status": "queued",
        "brand_voice": None,
        "filter_mode": body.filter_mode,
        "max_products": body.max_products,
        "products_requested": 0,
        "products_generated": 0,
        "results": [],
        "created_at": now,
        "completed_at": None,
        "error_message": None,
    }
    result = await aw(db.copy_sessions.insert_one(doc))
    session_id = str(result.inserted_id)

    from app.workers.copy_worker import run_copy_task
    run_copy_task.delay(
        session_id,
        tenant["shop_domain"],
        tenant.get("access_token", ""),
        body.product_ids,
        body.filter_mode,
        body.max_products,
    )

    logger.info(f"🚀 [BulkCopy] Session {session_id} queued for {tenant['shop_domain']}")
    return {
        "session_id": session_id,
        "status": "queued",
        "message": f"Generating copy for up to {body.max_products} products",
    }


# ── GET /copy/latest ──────────────────────────────────────────────────────────

@router.get("/latest")
async def latest(tenant: dict = Depends(get_current_tenant)):
    db = await get_db()
    session = await aw(db.copy_sessions.find_one(
        {"tenant_id": str(tenant["_id"])},
        sort=[("created_at", -1)],
    ))
    if not session:
        return None
    session["_id"] = str(session["_id"])
    return session


# ── GET /copy/{id}/status ─────────────────────────────────────────────────────

@router.get("/{session_id}/status")
async def status(session_id: str, tenant: dict = Depends(get_current_tenant)):
    db = await get_db()
    session = await aw(db.copy_sessions.find_one(
        {"_id": ObjectId(session_id), "tenant_id": str(tenant["_id"])},
        {"status": 1, "products_requested": 1, "products_generated": 1, "error_message": 1},
    ))
    if not session:
        raise HTTPException(404, "Session not found")
    return {
        "session_id": session_id,
        "status": session["status"],
        "products_requested": session.get("products_requested", 0),
        "products_generated": session.get("products_generated", 0),
        "error_message": session.get("error_message"),
    }


# ── GET /copy/{id}/results ────────────────────────────────────────────────────

@router.get("/{session_id}/results")
async def results(session_id: str, tenant: dict = Depends(get_current_tenant)):
    db = await get_db()
    session = await aw(db.copy_sessions.find_one(
        {"_id": ObjectId(session_id), "tenant_id": str(tenant["_id"])},
    ))
    if not session:
        raise HTTPException(404, "Session not found")
    session["_id"] = str(session["_id"])
    return session


# ── PATCH /copy/{id}/product/{pid} ────────────────────────────────────────────

@router.patch("/{session_id}/product/{product_id}")
async def edit_product(
    session_id: str,
    product_id: str,
    body: EditRequest,
    tenant: dict = Depends(get_current_tenant),
):
    db = await get_db()
    result = await aw(db.copy_sessions.update_one(
        {
            "_id": ObjectId(session_id),
            "tenant_id": str(tenant["_id"]),
            "results.product_id": product_id,
        },
        {"$set": {
            "results.$.edited_description": body.edited_description,
            "results.$.status": "approved",
        }},
    ))
    if result.matched_count == 0:
        raise HTTPException(404, "Session or product not found")
    return {"success": True}


# ── POST /copy/{id}/push ──────────────────────────────────────────────────────

@router.post("/{session_id}/push")
async def push_to_shopify(
    session_id: str,
    body: PushRequest,
    tenant: dict = Depends(get_current_tenant),
):
    db = await get_db()
    session = await aw(db.copy_sessions.find_one(
        {"_id": ObjectId(session_id), "tenant_id": str(tenant["_id"])},
    ))
    if not session:
        raise HTTPException(404, "Session not found")

    raw_token = tenant.get("access_token", "")
    access_token = (
        decrypt_token(raw_token)
        if raw_token not in ("mock_token_not_real", "")
        else raw_token
    )
    shop = tenant["shop_domain"]

    results_map = {r["product_id"]: r for r in session.get("results", [])}
    push_results: dict[str, dict] = {}

    async with httpx.AsyncClient(timeout=30.0) as client:
        for pid in body.product_ids:
            product_result = results_map.get(pid)
            if not product_result:
                push_results[pid] = {"success": False, "error": "Product not in session"}
                continue

            description = (
                product_result.get("edited_description")
                or product_result.get("generated_description", "")
            )

            try:
                resp = await client.put(
                    f"https://{shop}/admin/api/{SHOPIFY_API_VERSION}/products/{pid}.json",
                    json={"product": {"id": int(pid), "body_html": description}},
                    headers=shopify_headers(access_token),
                )
                if resp.status_code == 200:
                    push_results[pid] = {"success": True}
                else:
                    push_results[pid] = {
                        "success": False,
                        "error": f"Shopify {resp.status_code}: {resp.text[:200]}",
                    }
            except Exception as e:
                push_results[pid] = {"success": False, "error": str(e)}

    # Persist push status back to DB
    for pid, pr in push_results.items():
        new_status = "pushed" if pr["success"] else "failed"
        await aw(db.copy_sessions.update_one(
            {"_id": ObjectId(session_id), "results.product_id": pid},
            {"$set": {"results.$.status": new_status}},
        ))

    success_count = sum(1 for pr in push_results.values() if pr["success"])
    logger.info(
        f"{'✅' if success_count == len(body.product_ids) else '⚠️'} [BulkCopy] "
        f"Pushed {success_count}/{len(body.product_ids)} products for {shop}"
    )
    return {
        "success": True,
        "pushed": success_count,
        "total": len(body.product_ids),
        "results": push_results,
    }
