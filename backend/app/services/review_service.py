"""
ReviewReply AI — Response Generation Service
─────────────────────────────────────────────
Generates brand-consistent, sentiment-aware review responses.
Flags escalations (refund requests, safety issues, legal threats).
"""
import asyncio
import json
import logging
import time
import uuid

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)


RESPONSE_SYSTEM = (
    "You are a senior customer service manager responding to product reviews "
    "on behalf of a Shopify store. Write responses that are warm, genuine, and on-brand. "
    "Return ONLY valid JSON — no markdown fences, no text outside the JSON object."
)

RESPONSE_PROMPT = """\
Write a review response for the following customer review.

BRAND VOICE:
{brand_voice_summary}
Tone: {tone}

REVIEW:
Rating: {rating}/5 stars
Customer: {author}
Product: {product_title}
Review: "{body}"
Detected sentiment: {sentiment}

RESPONSE GUIDELINES:
- 5-star: Express genuine gratitude, reinforce their choice, warmly invite return
- 4-star: Thank them sincerely, acknowledge what could be better, show you are listening
- 3-star: Acknowledge the mixed experience, invite them to contact you directly
- 1-2 star: Apologise sincerely for the specific issue, offer a clear resolution path
- Under 80 words — concise, human, not template-sounding
- Match the brand voice exactly
- Address the specific product or issue they mentioned
- Never be defensive or dismissive

Escalation triggers (set is_escalation=true if ANY appear):
refund demand, legal threat, health/safety risk, fraud accusation, media threat

Return this exact JSON:
{{
  "response": "<the reply text>",
  "is_escalation": <true|false>
}}"""


def _detect_sentiment(rating: int, body: str) -> str:
    if rating >= 4:
        return "positive"
    if rating == 3:
        return "neutral"
    return "negative"


async def generate_review_response(
    client: genai.Client,
    review: dict,
    brand_voice: dict,
) -> dict:
    """Generate an AI response for a single review. Returns {response, is_escalation}."""
    rid = review.get("review_id", "?")
    sentiment = _detect_sentiment(review.get("rating", 3), review.get("body", ""))

    prompt = RESPONSE_PROMPT.format(
        brand_voice_summary=brand_voice.get("summary", "Clear and professional"),
        tone=brand_voice.get("tone", "professional"),
        rating=review.get("rating", 3),
        author=review.get("author", "Customer"),
        product_title=review.get("product_title") or "your purchase",
        body=review.get("body", "")[:500],
        sentiment=sentiment,
    )
    full_prompt = f"{RESPONSE_SYSTEM}\n\n{prompt}"

    t0 = time.monotonic()
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.0-flash",
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.4,
                    max_output_tokens=300,
                    response_mime_type="application/json",
                ),
            ),
            timeout=25.0,
        )
        raw = _clean_json(response.text)
        result = json.loads(raw)
        logger.info(
            f"✅ [ReviewReply] {rid} ({sentiment}, {review.get('rating')}★) "
            f"in {time.monotonic() - t0:.1f}s — escalation={result.get('is_escalation', False)}"
        )
        return {"response": result.get("response", ""), "is_escalation": result.get("is_escalation", False), "sentiment": sentiment}
    except Exception as e:
        logger.error(f"❌ [ReviewReply] Generation failed for {rid}: {e}")
        return _fallback_response(review.get("rating", 3), sentiment)


def _fallback_response(rating: int, sentiment: str) -> dict:
    if rating >= 4:
        text = "Thank you so much for your kind words! We're thrilled you had a great experience and hope to see you again soon."
    elif rating == 3:
        text = "Thank you for taking the time to leave a review. We'd love to hear more about your experience — please reach out to us directly."
    else:
        text = "We're sorry to hear your experience didn't meet expectations. Please contact us directly so we can make this right for you."
    return {"response": text, "is_escalation": False, "sentiment": sentiment}


async def generate_responses_batch(
    reviews: list[dict],
    brand_voice: dict,
    batch_size: int = 10,
) -> dict[str, dict]:
    """Generate responses for all reviews in parallel batches. Returns {review_id: result}."""
    if not settings.GEMINI_API_KEY:
        return {
            r["review_id"]: _fallback_response(r.get("rating", 3), _detect_sentiment(r.get("rating", 3), r.get("body", "")))
            for r in reviews
        }

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    results: dict[str, dict] = {}

    for i in range(0, len(reviews), batch_size):
        batch = reviews[i:i + batch_size]
        tasks = [generate_review_response(client, r, brand_voice) for r in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for review, result in zip(batch, batch_results):
            rid = review["review_id"]
            if isinstance(result, Exception):
                results[rid] = _fallback_response(review.get("rating", 3), "neutral")
            else:
                results[rid] = result

        if i + batch_size < len(reviews):
            await asyncio.sleep(0.5)

    return results


def _clean_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1].lstrip("json").strip() if len(parts) > 1 else raw
    return raw


def make_demo_reviews(products: list[dict]) -> list[dict]:
    """
    Generate realistic demo reviews. Uses real product titles if available,
    falls back to generic product names.
    """
    sample_products = [
        {"product_id": str(p.get("id", "")), "title": p.get("title", ""), "image": (p.get("images") or [{}])[0].get("src")}
        for p in products[:5]
    ] if products else []

    def _prod(i: int) -> dict:
        if i < len(sample_products):
            return sample_products[i]
        return {"product_id": None, "title": "your recent purchase", "image": None}

    return [
        {
            "review_id": str(uuid.uuid4()),
            "platform": "demo",
            "product_id": _prod(0)["product_id"],
            "product_title": _prod(0)["title"],
            "product_image": _prod(0)["image"],
            "author": "Sarah M.",
            "rating": 5,
            "title": "Absolutely love it!",
            "body": "Arrived quickly and exactly as described. The quality exceeded my expectations — I've already recommended it to three friends. Will definitely be ordering again.",
            "date": "2026-04-25",
            "status": "pending",
        },
        {
            "review_id": str(uuid.uuid4()),
            "platform": "demo",
            "product_id": _prod(1)["product_id"],
            "product_title": _prod(1)["title"],
            "product_image": _prod(1)["image"],
            "author": "James T.",
            "rating": 5,
            "title": "Third order, still impressed",
            "body": "This is my third purchase from this store. Consistent quality every time. Fast shipping, great packaging, and the product speaks for itself. Highly recommend.",
            "date": "2026-04-22",
            "status": "pending",
        },
        {
            "review_id": str(uuid.uuid4()),
            "platform": "demo",
            "product_id": _prod(2)["product_id"],
            "product_title": _prod(2)["title"],
            "product_image": _prod(2)["image"],
            "author": "Priya K.",
            "rating": 4,
            "title": "Great product, minor packaging issue",
            "body": "Really happy with the quality overall. My only gripe is the outer packaging arrived slightly dented — the item inside was fine but it gave me a scare. Would still buy again.",
            "date": "2026-04-20",
            "status": "pending",
        },
        {
            "review_id": str(uuid.uuid4()),
            "platform": "demo",
            "product_id": _prod(0)["product_id"],
            "product_title": _prod(0)["title"],
            "product_image": _prod(0)["image"],
            "author": "David L.",
            "rating": 4,
            "title": "Solid purchase",
            "body": "Does exactly what it says. Delivery was a couple of days later than estimated which was a bit frustrating, but the product itself is great. Four stars.",
            "date": "2026-04-18",
            "status": "pending",
        },
        {
            "review_id": str(uuid.uuid4()),
            "platform": "demo",
            "product_id": _prod(3)["product_id"],
            "product_title": _prod(3)["title"],
            "product_image": _prod(3)["image"],
            "author": "Emma R.",
            "rating": 3,
            "title": "Okay but not quite what I expected",
            "body": "It's decent but the product photos made it look a bit different from what I received. Not bad, just not what I pictured. Does the job though.",
            "date": "2026-04-15",
            "status": "pending",
        },
        {
            "review_id": str(uuid.uuid4()),
            "platform": "demo",
            "product_id": _prod(4)["product_id"],
            "product_title": _prod(4)["title"],
            "product_image": _prod(4)["image"],
            "author": "Marcus B.",
            "rating": 2,
            "title": "Disappointed with quality",
            "body": "For the price, I expected better quality. It feels cheap and the finish isn't as described. I've seen much better for the same price elsewhere.",
            "date": "2026-04-12",
            "status": "pending",
        },
        {
            "review_id": str(uuid.uuid4()),
            "platform": "demo",
            "product_id": _prod(1)["product_id"],
            "product_title": _prod(1)["title"],
            "product_image": _prod(1)["image"],
            "author": "Olivia W.",
            "rating": 1,
            "title": "Arrived damaged — no resolution",
            "body": "Item arrived completely damaged. I contacted support twice over two weeks and got no useful response. This is unacceptable. I want a full refund immediately. Will be disputing with my bank if not resolved.",
            "date": "2026-04-10",
            "status": "pending",
        },
        {
            "review_id": str(uuid.uuid4()),
            "platform": "demo",
            "product_id": _prod(2)["product_id"],
            "product_title": _prod(2)["title"],
            "product_image": _prod(2)["image"],
            "author": "Ryan C.",
            "rating": 2,
            "title": "Not as described",
            "body": "Returned the product — it simply didn't match the product description. The colour was wrong and it was smaller than stated. Wasted time on return postage too.",
            "date": "2026-04-08",
            "status": "pending",
        },
    ]
