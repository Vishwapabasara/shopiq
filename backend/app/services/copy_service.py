"""
BulkCopy AI — Copy Generation Service
──────────────────────────────────────
Phase 1: Brand Voice Fingerprinting — extract brand DNA from existing products.
Phase 2: Bulk Description Generation — SEO + conversion copy per product.
"""
import asyncio
import json
import logging
import time

from google import genai
from google.genai import types

from app.config import settings
from app.services.audit_rules import strip_html

logger = logging.getLogger(__name__)


BRAND_VOICE_SYSTEM = (
    "You are a brand strategist and senior copywriter specializing in e-commerce. "
    "Analyze product descriptions and extract the brand's writing DNA. "
    "Return ONLY valid JSON — no markdown fences, no text outside the JSON object."
)

BRAND_VOICE_PROMPT = """\
Analyze these {count} product descriptions from the same Shopify store.
Extract their shared brand voice so a copywriter can replicate it exactly.

DESCRIPTIONS:
{descriptions}

Return this exact JSON structure:
{{
  "tone": "<3-5 adjectives, e.g. confident, approachable, premium>",
  "sentence_style": "<short|medium|long>",
  "vocabulary": "<casual|professional|technical>",
  "emphasis": "<features|benefits|mixed>",
  "emotional_triggers": ["<trigger 1>", "<trigger 2>", "<trigger 3>"],
  "structure": "<one sentence: how they open, develop, and close>",
  "example_phrases": ["<short phrase that sounds like this brand>", "<another>"],
  "summary": "<one-sentence copywriter brief that captures everything above>"
}}"""


COPY_GEN_SYSTEM = (
    "You are a senior e-commerce copywriter. "
    "Write Shopify product descriptions that are brand-consistent, SEO-optimized, and conversion-focused. "
    "Return ONLY valid JSON — no markdown fences, no text outside the JSON object."
)

COPY_GEN_PROMPT = """\
Write a new Shopify product description for the product below.

BRAND VOICE:
Summary: {brand_voice_summary}
Tone: {tone}
Sentence style: {sentence_style}
Vocabulary: {vocabulary}
Emphasis: {emphasis}
Emotional triggers to use: {emotional_triggers}

PRODUCT:
Title: {title}
Current description: {current_description}
Tags: {tags}
Product type: {product_type}
Price: ${price}

REQUIREMENTS:
- Match the brand voice exactly — it must sound like this brand, not generic AI
- 130-180 words
- HTML formatted with <p> and <ul> tags only
- Lead with the strongest benefit or emotional hook (not the product name)
- Weave in keywords from title and tags naturally (no keyword stuffing)
- End with a value statement (not a generic "buy now")
- SEO title: primary keyword + brand differentiator, under 70 characters
- Meta description: benefit + CTA, under 155 characters

Return this exact JSON:
{{
  "body_html": "<p>...</p>",
  "seo_title": "<70 chars max>",
  "meta_description": "<155 chars max>",
  "predicted_content_score": <integer 60-95>,
  "key_improvements": ["<what changed and why it will perform better>", "<second improvement>"]
}}"""


def _product_to_sample_text(product: dict) -> str:
    body = strip_html(product.get("body_html") or "").strip()
    title = product.get("title", "")
    return f"Title: {title}\nDescription: {body[:600] or '(no description)'}"


async def extract_brand_voice(products: list[dict]) -> dict:
    """
    Analyze top products and extract brand voice profile.
    Returns a dict with tone, style, etc. Falls back to defaults on any error.
    """
    if not settings.GEMINI_API_KEY:
        return _default_brand_voice()

    samples = [p for p in products if strip_html(p.get("body_html") or "").strip()][:8]
    if not samples:
        return _default_brand_voice()

    descriptions = "\n\n---\n\n".join(
        f"[{i + 1}] {_product_to_sample_text(p)}"
        for i, p in enumerate(samples)
    )
    prompt = BRAND_VOICE_PROMPT.format(count=len(samples), descriptions=descriptions)
    full_prompt = f"{BRAND_VOICE_SYSTEM}\n\n{prompt}"

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.0-flash",
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=600,
                    response_mime_type="application/json",
                ),
            ),
            timeout=30.0,
        )
        raw = _clean_json(response.text)
        result = json.loads(raw)
        logger.info(f"✅ [BulkCopy] Brand voice extracted: {result.get('summary', '')[:80]}")
        return result
    except Exception as e:
        logger.warning(f"⚠️ [BulkCopy] Brand voice extraction failed: {e} — using defaults")
        return _default_brand_voice()


def _default_brand_voice() -> dict:
    return {
        "tone": "clear, helpful, professional",
        "sentence_style": "medium",
        "vocabulary": "professional",
        "emphasis": "benefits",
        "emotional_triggers": ["quality", "value", "reliability"],
        "structure": "Open with a hook, detail features as benefits, close with value statement",
        "example_phrases": ["Built for", "Designed to"],
        "summary": "Clear, benefit-led copy with a professional tone and confident voice.",
    }


async def generate_copy_for_product(
    client: genai.Client,
    product: dict,
    brand_voice: dict,
) -> dict:
    """Generate SEO + conversion copy for a single product. Returns result dict."""
    pid = product.get("id", "unknown")
    title = product.get("title", "")[:60]

    body_text = strip_html(product.get("body_html") or "").strip()
    tags_raw = product.get("tags", "")
    tags = ", ".join(t.strip() for t in tags_raw.split(",") if t.strip())[:10 * 20] or "(none)"
    variants = product.get("variants") or [{}]
    price = variants[0].get("price", "0")

    prompt = COPY_GEN_PROMPT.format(
        brand_voice_summary=brand_voice.get("summary", ""),
        tone=brand_voice.get("tone", "professional"),
        sentence_style=brand_voice.get("sentence_style", "medium"),
        vocabulary=brand_voice.get("vocabulary", "professional"),
        emphasis=brand_voice.get("emphasis", "benefits"),
        emotional_triggers=", ".join(brand_voice.get("emotional_triggers", [])),
        title=title,
        current_description=body_text[:800] or "(no description)",
        tags=tags,
        product_type=product.get("product_type") or "(none)",
        price=price,
    )
    full_prompt = f"{COPY_GEN_SYSTEM}\n\n{prompt}"

    t0 = time.monotonic()
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.0-flash",
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.4,
                    max_output_tokens=800,
                    response_mime_type="application/json",
                ),
            ),
            timeout=30.0,
        )
        raw = _clean_json(response.text)
        result = json.loads(raw)
        logger.info(
            f"✅ [BulkCopy] {pid} ({title}) in {time.monotonic() - t0:.1f}s "
            f"— predicted score {result.get('predicted_content_score', '?')}"
        )
        return result
    except Exception as e:
        logger.error(f"❌ [BulkCopy] Generation failed for {pid}: {e}")
        return _fallback_copy_result(title)


def _fallback_copy_result(title: str) -> dict:
    return {
        "body_html": (
            f"<p>Discover the {title} — crafted for quality and built to last. "
            "Designed with attention to detail, it delivers real value for everyday use.</p>"
        ),
        "seo_title": title[:70],
        "meta_description": f"Shop {title}. Quality guaranteed with fast shipping.",
        "predicted_content_score": 60,
        "key_improvements": ["Customize this description to highlight your unique selling points"],
    }


def _clean_json(raw: str) -> str:
    """Strip markdown fences that some Gemini responses include."""
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1].lstrip("json").strip() if len(parts) > 1 else raw
    return raw
