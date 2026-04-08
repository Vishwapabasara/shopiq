"""
AI Scoring Service
──────────────────
Sends product data to GPT-4o for qualitative scoring.
Uses OpenAI's async client. Batches up to 50 products per call
using asyncio.gather to stay within rate limits.
"""
import asyncio
import json
import logging
import google.generativeai as genai
from app.config import settings
from app.services.audit_rules import strip_html, word_count
from app.config import settings
genai.configure(api_key=settings.GEMINI_API_KEY)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert Shopify conversion rate optimisation specialist with 10 years of experience auditing e-commerce product pages.

You will receive raw product data and must return a JSON object ONLY.
No preamble, no markdown fences, no explanation outside the JSON.
Be specific and actionable — generic advice is useless."""

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
    model: genai.GenerativeModel,
    product: dict,
) -> dict:
    """Score a single product with Gemini. Returns parsed result dict."""
    prompt = _build_prompt(product)
    
    # Combine system prompt and user prompt for Gemini
    full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"

    try:
        # Gemini API call
        response = await asyncio.to_thread(
            model.generate_content,
            full_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=800,
            )
        )

        raw = response.text
        
        # Clean potential markdown fences from response
        if raw.startswith("```json"):
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif raw.startswith("```"):
            raw = raw.split("```")[1].split("```")[0].strip()
            
        return json.loads(raw)

    except json.JSONDecodeError as e:
        logger.warning(f"Gemini JSON parse error for {product.get('id')}: {e}")
        logger.debug(f"Raw response: {raw[:200]}")
        return _fallback_ai_result()
    except Exception as e:
        logger.error(f"Gemini error for product {product.get('id')}: {e}")
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

    # Initialize Gemini model
    model = genai.GenerativeModel('gemini-1.5-flash')  # Or 'gemini-pro'
    results: dict[str, dict] = {}

    for i in range(0, len(products), batch_size):
        batch = products[i:i + batch_size]
        tasks = [score_product_ai(model, p) for p in batch]

        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for product, result in zip(batch, batch_results):
            pid = str(product.get("id", ""))
            if isinstance(result, Exception):
                logger.error(f"AI scoring failed for {pid}: {result}")
                results[pid] = _fallback_ai_result()
            else:
                results[pid] = result

        # Brief pause between batches to respect rate limits
        if i + batch_size < len(products):
            await asyncio.sleep(1.0)

    return results
