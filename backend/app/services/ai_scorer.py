"""
AI Scoring Service
──────────────────
Sends product data to Gemini for qualitative scoring.
Uses Google's new genai client. Batches up to 50 products per call
using asyncio.gather to stay within rate limits.
"""
import asyncio
import json
import logging
import time
from google import genai
from google.genai import types

from app.config import settings
from app.services.audit_rules import strip_html, word_count

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert Shopify conversion rate optimisation specialist with 10 years of experience auditing e-commerce product pages.

You will receive raw product data and must return a JSON object ONLY.
No preamble, no markdown fences, no explanation outside the JSON.
Be specific and actionable — generic advice is useless.

IMPORTANT — severity when framing issues in your verdict and improvements:
- CRITICAL: Only truly show-stopping problems — no images at all, completely empty description, title missing or under 5 characters.
- WARNING: Suboptimal but not broken — missing meta description, short description, only 1–2 images, vague title.
- INFO: Nice-to-have improvements — add lifestyle images, expand keywords, add size chart, add variants.
Reserve "critical" sparingly. Missing a meta description is a WARNING, not critical."""

USER_PROMPT_TEMPLATE = """Audit this Shopify product for content quality, SEO effectiveness, and conversion potential.

Product title: {title}
Description text (HTML stripped): {description}
Word count: {word_count}
Image count: {image_count}
Has SEO title: {has_seo_title}
Has meta description: {has_meta}
Price: ${price}
Has compare-at price: {has_compare_at}
Tags: {tags}
Product type: {product_type}

Return ONLY this exact JSON structure:
{{
  "content_score": <integer 0-100>,
  "improvements": [
    "<specific actionable improvement with concrete example>",
    "<specific actionable improvement with concrete example>",
    "<specific actionable improvement with concrete example>"
  ],
  "rewritten_description": "<improved HTML description using <p> and <ul> tags, 150-200 words, includes keywords naturally>",
  "one_line_verdict": "<single sentence: the single most important problem with this product page>"
}}"""


def _build_prompt(product: dict) -> str:
    body_text = strip_html(product.get("body_html") or "")
    wc = word_count(body_text)

    variants = product.get("variants") or [{}]
    primary = variants[0]
    price = primary.get("price", "0")
    has_compare = bool(primary.get("compare_at_price"))

    seo = product.get("seo") or {}
    tags_raw = product.get("tags", "")
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

    return USER_PROMPT_TEMPLATE.format(
        title=product.get("title", ""),
        description=body_text[:1000] or "(none)",   # cap at 1000 chars to control cost
        word_count=wc,
        image_count=len(product.get("images") or []),
        has_seo_title=bool(seo.get("title")),
        has_meta=bool(seo.get("description")),
        price=price,
        has_compare_at=has_compare,
        tags=", ".join(tags[:10]) or "(none)",
        product_type=product.get("product_type") or "(none)",
    )


async def score_product_ai(
    client: genai.Client,
    product: dict,
) -> dict:
    """Score a single product with Gemini. Returns parsed result dict."""
    pid = product.get("id", "unknown")
    title = product.get("title", "untitled")[:60]
    prompt = _build_prompt(product)
    full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"

    logger.info(f"🤖 [AI] Scoring product {pid} — \"{title}\"")
    t0 = time.monotonic()

    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.models.generate_content,
                model='models/gemini-1.5-flash-latest',
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=800,
                    response_mime_type="application/json",
                )
            ),
            timeout=30.0,  # never hang indefinitely
        )

        raw = response.text

        # Clean potential markdown fences from response
        if raw.startswith("```json"):
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif raw.startswith("```"):
            raw = raw.split("```")[1].split("```")[0].strip()

        result = json.loads(raw)
        elapsed = time.monotonic() - t0
        logger.info(
            f"✅ [AI] Product {pid} scored in {elapsed:.2f}s — "
            f"content_score={result.get('content_score', '?')}"
        )
        return result

    except asyncio.TimeoutError:
        elapsed = time.monotonic() - t0
        logger.error(f"⏱️ [AI] Timeout after {elapsed:.2f}s for product {pid} — using fallback")
        return _fallback_ai_result()
    except json.JSONDecodeError as e:
        elapsed = time.monotonic() - t0
        logger.warning(f"⚠️ [AI] JSON parse error for product {pid} after {elapsed:.2f}s: {e}")
        logger.debug(f"Raw response: {raw[:200] if 'raw' in locals() else 'N/A'}")
        return _fallback_ai_result()
    except Exception as e:
        elapsed = time.monotonic() - t0
        logger.error(f"❌ [AI] Gemini call failed for product {pid} after {elapsed:.2f}s: {e}")
        return _fallback_ai_result()


def _fallback_ai_result() -> dict:
    return {
        "content_score": 50,
        "improvements": [
            "Add a more detailed product description with features and benefits",
            "Include relevant keywords naturally in the description",
            "Add customer-centric language focusing on value to the buyer",
        ],
        "rewritten_description": "",
        "one_line_verdict": "Unable to generate AI analysis (Gemini error) — deterministic score still applied",
    }


async def score_products_batch(
    products: list[dict],
    batch_size: int = 10,
) -> dict[str, dict]:
    """
    Score a list of products with Gemini.
    Processes in batches to respect rate limits.
    Returns dict keyed by shopify_product_id.
    """
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set — skipping AI scoring")
        return {}

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    results: dict[str, dict] = {}
    total = len(products)
    num_batches = (total + batch_size - 1) // batch_size
    t_start = time.monotonic()

    logger.info(f"🚀 [AI] Starting batch scoring: {total} products in {num_batches} batch(es) of {batch_size}")

    for i in range(0, total, batch_size):
        batch = products[i:i + batch_size]
        batch_num = i // batch_size + 1
        logger.info(f"📦 [AI] Batch {batch_num}/{num_batches} — scoring {len(batch)} products (done so far: {i}/{total})")
        t_batch = time.monotonic()

        tasks = [score_product_ai(client, p) for p in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        ok = 0
        for product, result in zip(batch, batch_results):
            pid = str(product.get("id", ""))
            if isinstance(result, Exception):
                logger.error(f"❌ [AI] Unhandled exception for {pid}: {result}")
                results[pid] = _fallback_ai_result()
            else:
                results[pid] = result
                ok += 1

        logger.info(
            f"✅ [AI] Batch {batch_num}/{num_batches} done in {time.monotonic() - t_batch:.2f}s "
            f"({ok}/{len(batch)} succeeded)"
        )

        # Brief pause between batches to respect rate limits
        if i + batch_size < total:
            logger.info(f"⏳ [AI] Pausing 1s before next batch...")
            await asyncio.sleep(1.0)

    logger.info(f"🏁 [AI] All scoring complete — {total} products in {time.monotonic() - t_start:.2f}s total")
    return results