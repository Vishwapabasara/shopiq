"""
Audit Rules Engine
──────────────────
18 deterministic checks across 4 categories.
Each rule inspects a raw Shopify product dict and returns zero or more AuditIssue objects.
All rules are pure functions — no I/O, no side effects.
"""
import re
import hashlib
from bs4 import BeautifulSoup
from app.models.schemas import AuditIssue, IssueSeverity


# ── HTML utilities ────────────────────────────────────────────────────────────

def strip_html(html: str) -> str:
    if not html:
        return ""
    return BeautifulSoup(html, "html.parser").get_text(separator=" ").strip()


def word_count(text: str) -> int:
    return len(text.split()) if text.strip() else 0


def hash_text(text: str) -> str:
    return hashlib.md5(text.strip().lower().encode()).hexdigest()


# ── Category: SEO (weight 25%) ────────────────────────────────────────────────

def check_seo_title(product: dict) -> list[AuditIssue]:
    seo = product.get("seo") or {}
    title = seo.get("title") or product.get("title", "")
    issues = []

    if not title:
        issues.append(AuditIssue(
            rule="missing_seo_title",
            category="seo",
            severity=IssueSeverity.CRITICAL,
            message="Product has no SEO title tag",
            fix_hint="Add a unique SEO title (50–70 chars) in the product's search engine listing preview",
        ))
    elif len(title) < 30:
        issues.append(AuditIssue(
            rule="seo_title_too_short",
            category="seo",
            severity=IssueSeverity.WARNING,
            message=f"SEO title is only {len(title)} characters — too short to rank well",
            fix_hint="Expand SEO title to 50–70 characters including your primary keyword",
        ))
    elif len(title) > 70:
        issues.append(AuditIssue(
            rule="seo_title_too_long",
            category="seo",
            severity=IssueSeverity.WARNING,
            message=f"SEO title is {len(title)} characters — Google truncates at ~70",
            fix_hint="Shorten SEO title to under 70 characters to avoid truncation in search results",
        ))
    return issues


def check_meta_description(product: dict) -> list[AuditIssue]:
    seo = product.get("seo") or {}
    desc = seo.get("description") or ""
    issues = []

    if not desc:
        issues.append(AuditIssue(
            rule="missing_meta_description",
            category="seo",
            severity=IssueSeverity.CRITICAL,
            message="No meta description set for this product",
            fix_hint="Add a meta description (120–160 chars) summarising the product with keywords",
        ))
    elif len(desc) < 80:
        issues.append(AuditIssue(
            rule="meta_description_too_short",
            category="seo",
            severity=IssueSeverity.WARNING,
            message=f"Meta description is only {len(desc)} characters",
            fix_hint="Expand meta description to 120–160 characters for best click-through rate",
        ))
    elif len(desc) > 160:
        issues.append(AuditIssue(
            rule="meta_description_too_long",
            category="seo",
            severity=IssueSeverity.WARNING,
            message=f"Meta description is {len(desc)} characters — Google truncates at ~160",
            fix_hint="Shorten meta description to under 160 characters",
        ))
    return issues


def check_image_alt_text(product: dict) -> list[AuditIssue]:
    images = product.get("images") or []
    if not images:
        return []

    missing = [img for img in images if not img.get("alt")]
    if missing:
        count = len(missing)
        return [AuditIssue(
            rule="missing_alt_text",
            category="seo",
            severity=IssueSeverity.CRITICAL,
            message=f"{count} of {len(images)} images are missing alt text",
            fix_hint="Add descriptive alt text to every image — include product name and key feature",
        )]
    return []


def check_url_handle(product: dict) -> list[AuditIssue]:
    handle = product.get("handle", "")
    # A bad handle contains uppercase, spaces, or special chars
    if re.search(r'[A-Z\s!@#$%^&*()+=\[\]{};\':",.<>?]', handle):
        return [AuditIssue(
            rule="bad_url_handle",
            category="seo",
            severity=IssueSeverity.WARNING,
            message=f"URL handle '{handle}' contains invalid characters",
            fix_hint="Use only lowercase letters, numbers, and hyphens in URL handles",
        )]
    return []


# ── Category: Content (weight 35%) ───────────────────────────────────────────

def check_description(product: dict) -> list[AuditIssue]:
    html = product.get("body_html") or ""
    text = strip_html(html)
    wc = word_count(text)
    issues = []

    if wc == 0:
        issues.append(AuditIssue(
            rule="no_description",
            category="content",
            severity=IssueSeverity.CRITICAL,
            message="Product has no description at all",
            fix_hint="Write a product description of at least 150 words covering features, benefits, and use cases",
        ))
    elif wc < 80:
        issues.append(AuditIssue(
            rule="thin_description",
            category="content",
            severity=IssueSeverity.CRITICAL,
            message=f"Description is only {wc} words — too thin for SEO and conversion",
            fix_hint="Expand description to at least 150 words; add features, benefits, sizing, and care instructions",
        ))
    elif wc < 150:
        issues.append(AuditIssue(
            rule="short_description",
            category="content",
            severity=IssueSeverity.WARNING,
            message=f"Description is {wc} words — borderline for SEO",
            fix_hint="Consider expanding to 150+ words with more product details",
        ))
    return issues


def check_duplicate_description(product: dict, all_hashes: set) -> list[AuditIssue]:
    html = product.get("body_html") or ""
    if not html.strip():
        return []

    h = hash_text(strip_html(html))
    if h in all_hashes:
        return [AuditIssue(
            rule="duplicate_description",
            category="content",
            severity=IssueSeverity.WARNING,
            message="This product has the same description as another product",
            fix_hint="Write a unique description — duplicate content hurts both products in Google rankings",
        )]
    all_hashes.add(h)
    return []


def check_title_quality(product: dict) -> list[AuditIssue]:
    title = product.get("title", "")
    issues = []

    if len(title) < 10:
        issues.append(AuditIssue(
            rule="title_too_short",
            category="content",
            severity=IssueSeverity.WARNING,
            message=f"Product title '{title}' is very short ({len(title)} chars)",
            fix_hint="Use a descriptive title: Brand + Product Name + Key Feature (e.g. 'Acme Merino Wool Beanie — Navy')",
        ))

    # Detect generic placeholder titles
    generic = ["untitled", "new product", "draft", "test", "product 1", "copy of"]
    if any(g in title.lower() for g in generic):
        issues.append(AuditIssue(
            rule="generic_title",
            category="content",
            severity=IssueSeverity.CRITICAL,
            message=f"Title '{title}' appears to be a placeholder",
            fix_hint="Replace with a descriptive, keyword-rich product title",
        ))
    return issues


# ── Category: UX (weight 25%) ─────────────────────────────────────────────────

def check_images(product: dict) -> list[AuditIssue]:
    images = product.get("images") or []
    issues = []

    if len(images) == 0:
        issues.append(AuditIssue(
            rule="no_images",
            category="ux",
            severity=IssueSeverity.CRITICAL,
            message="Product has no images",
            fix_hint="Add at least 3–5 high-quality images: main shot, lifestyle, detail, and size reference",
        ))
    elif len(images) == 1:
        issues.append(AuditIssue(
            rule="single_image",
            category="ux",
            severity=IssueSeverity.CRITICAL,
            message="Product only has one image",
            fix_hint="Add 3–5 images showing different angles, in-use context, and detail shots",
        ))
    elif len(images) < 3:
        issues.append(AuditIssue(
            rule="few_images",
            category="ux",
            severity=IssueSeverity.WARNING,
            message=f"Only {len(images)} images — shoppers expect at least 3–5",
            fix_hint="Add more product images to increase buyer confidence and reduce returns",
        ))
    return issues


def check_pricing(product: dict) -> list[AuditIssue]:
    variants = product.get("variants") or []
    issues = []

    if not variants:
        return issues

    for variant in variants[:1]:  # Check primary variant
        price_str = variant.get("price", "0")
        try:
            price = float(price_str)
        except (ValueError, TypeError):
            continue

        if price == 0:
            issues.append(AuditIssue(
                rule="zero_price",
                category="ux",
                severity=IssueSeverity.CRITICAL,
                message="Product is priced at $0.00",
                fix_hint="Set a price or mark as free intentionally — a zero price can undermine perceived value",
            ))
            continue

        # Check charm pricing (.99 / .95 / .97)
        cents = round((price % 1) * 100)
        if cents not in (99, 95, 97, 0):
            issues.append(AuditIssue(
                rule="no_charm_pricing",
                category="ux",
                severity=IssueSeverity.INFO,
                message=f"Price ${price:.2f} doesn't use charm pricing",
                fix_hint="Consider ending price in .99 or .95 — psychological pricing typically lifts conversion 2–5%",
            ))

        # Check compare-at price (strike-through)
        compare_at = variant.get("compare_at_price")
        if not compare_at:
            issues.append(AuditIssue(
                rule="no_compare_at_price",
                category="ux",
                severity=IssueSeverity.INFO,
                message="No compare-at (strike-through) price set",
                fix_hint="Add a compare-at price to show a discount — this creates urgency and perceived value",
            ))

    return issues


def check_variants(product: dict) -> list[AuditIssue]:
    variants = product.get("variants") or []
    options = product.get("options") or []

    # If there's only one option and it's "Title" (Shopify default), no real variants
    has_real_variants = not (
        len(options) == 1 and
        options[0].get("name", "").lower() == "title"
    )

    if not has_real_variants and len(variants) == 1:
        return [AuditIssue(
            rule="no_variants",
            category="ux",
            severity=IssueSeverity.INFO,
            message="No product variants configured",
            fix_hint="If this product comes in sizes, colours, or materials, add variants to reduce purchase friction",
        )]
    return []


# ── Category: Catalogue (weight 15%) ──────────────────────────────────────────

def check_tags(product: dict) -> list[AuditIssue]:
    tags_raw = product.get("tags", "")
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

    if not tags:
        return [AuditIssue(
            rule="no_tags",
            category="catalogue",
            severity=IssueSeverity.WARNING,
            message="Product has no tags",
            fix_hint="Add 5–10 relevant tags: material, use case, occasion, season — they power automated collections and filtering",
        )]
    elif len(tags) < 3:
        return [AuditIssue(
            rule="few_tags",
            category="catalogue",
            severity=IssueSeverity.INFO,
            message=f"Only {len(tags)} tag(s) — more tags improve collection assignment",
            fix_hint="Add at least 5 tags covering material, style, occasion, and audience",
        )]
    return []


def check_product_type(product: dict) -> list[AuditIssue]:
    if not product.get("product_type", "").strip():
        return [AuditIssue(
            rule="missing_product_type",
            category="catalogue",
            severity=IssueSeverity.WARNING,
            message="Product type is not set",
            fix_hint="Set a product type (e.g. 'Apparel', 'Accessories') — used for automated collections and analytics",
        )]
    return []


def check_vendor(product: dict) -> list[AuditIssue]:
    if not product.get("vendor", "").strip():
        return [AuditIssue(
            rule="missing_vendor",
            category="catalogue",
            severity=IssueSeverity.INFO,
            message="Vendor/brand is not set",
            fix_hint="Set the vendor field to your brand name — shown on product pages and used for filtering",
        )]
    return []


def check_published_zero_inventory(product: dict) -> list[AuditIssue]:
    """Flag active products with zero inventory across all variants."""
    if product.get("status") != "active":
        return []

    variants = product.get("variants") or []
    total_inventory = sum(
        int(v.get("inventory_quantity") or 0)
        for v in variants
        if v.get("inventory_management") == "shopify"
    )

    managed = any(v.get("inventory_management") == "shopify" for v in variants)
    if managed and total_inventory == 0:
        return [AuditIssue(
            rule="published_zero_inventory",
            category="catalogue",
            severity=IssueSeverity.WARNING,
            message="Product is published but has zero inventory",
            fix_hint="Either restock, hide the product, or enable 'Continue selling when out of stock' to avoid dead product pages",
        )]
    return []


# ── Master runner ─────────────────────────────────────────────────────────────

CATEGORY_WEIGHTS = {
    "seo": 0.25,
    "content": 0.35,
    "ux": 0.25,
    "catalogue": 0.15,
}

SEVERITY_PENALTY = {
    IssueSeverity.CRITICAL: 15,
    IssueSeverity.WARNING: 8,
    IssueSeverity.INFO: 3,
}


def run_rules(product: dict, description_hashes: set) -> tuple[list[AuditIssue], int]:
    """
    Run all 18 deterministic rules against a single product.
    Returns (issues, deterministic_score).
    description_hashes is mutated in place for duplicate detection across the batch.
    """
    checks = [
        check_seo_title(product),
        check_meta_description(product),
        check_image_alt_text(product),
        check_url_handle(product),
        check_description(product),
        check_duplicate_description(product, description_hashes),
        check_title_quality(product),
        check_images(product),
        check_pricing(product),
        check_variants(product),
        check_tags(product),
        check_product_type(product),
        check_vendor(product),
        check_published_zero_inventory(product),
    ]

    issues: list[AuditIssue] = []
    for result in checks:
        issues.extend(result)

    score = 100
    for issue in issues:
        score -= SEVERITY_PENALTY[issue.severity]
    score = max(0, score)

    return issues, score


def calculate_store_score(product_results: list) -> tuple[int, dict]:
    """
    Aggregate all product scores into category scores and an overall store score.
    Returns (overall_score, category_scores_dict).
    """
    if not product_results:
        return 0, {"seo": 0, "content": 0, "ux": 0, "catalogue": 0}

    category_issue_totals: dict[str, list[int]] = {
        "seo": [], "content": [], "ux": [], "catalogue": []
    }

    for pr in product_results:
        per_category: dict[str, int] = {k: 100 for k in CATEGORY_WEIGHTS}
        for issue in pr.get("issues", []):
            cat = issue.get("category", "seo")
            if cat in per_category:
                per_category[cat] -= SEVERITY_PENALTY.get(issue.get("severity", "info"), 3)

        for cat in per_category:
            per_category[cat] = max(0, per_category[cat])
            category_issue_totals[cat].append(per_category[cat])

    category_scores = {
        cat: round(sum(scores) / len(scores)) if scores else 0
        for cat, scores in category_issue_totals.items()
    }

    overall = round(sum(
        category_scores[cat] * weight
        for cat, weight in CATEGORY_WEIGHTS.items()
    ))

    return overall, category_scores
