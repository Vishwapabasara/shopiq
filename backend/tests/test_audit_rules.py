"""
Tests for app/services/audit_rules.py
Run with: pytest tests/test_audit_rules.py -v
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.audit_rules import (
    run_rules,
    calculate_store_score,
    check_seo_title,
    check_meta_description,
    check_image_alt_text,
    check_description,
    check_images,
    check_pricing,
    check_tags,
    check_product_type,
    check_published_zero_inventory,
    check_duplicate_description,
    strip_html,
    word_count,
)
from app.models.schemas import IssueSeverity


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_product(**overrides) -> dict:
    """Build a perfect product dict — all overrides applied on top."""
    base = {
        "id": 123456,
        "title": "Blue Merino Wool Sweater — Premium Collection",
        "handle": "blue-merino-wool-sweater",
        "body_html": "<p>" + ("This product features premium quality materials for outstanding comfort and durability. " * 20) + "</p>",  # 220+ words
        "status": "active",
        "product_type": "Apparel",
        "vendor": "MyBrand",
        "tags": "wool, merino, winter, luxury, blue, sweater, knit",
        "seo": {
            "title": "Blue Merino Wool Sweater | MyBrand",
            "description": "Shop our premium merino wool sweater in blue. Soft, warm and sustainably sourced. Free UK delivery.",
        },
        "images": [
            {"id": 1, "alt": "Blue merino sweater front view"},
            {"id": 2, "alt": "Blue merino sweater back view"},
            {"id": 3, "alt": "Blue merino sweater detail"},
        ],
        "variants": [
            {
                "id": 1,
                "price": "89.99",
                "compare_at_price": "120.00",
                "inventory_management": "shopify",
                "inventory_quantity": 50,
            }
        ],
        "options": [{"name": "Size", "values": ["S", "M", "L", "XL"]}],
    }
    base.update(overrides)
    return base


# ── strip_html / word_count ───────────────────────────────────────────────────

class TestHtmlUtils:
    def test_strip_html_basic(self):
        assert strip_html("<p>Hello world</p>") == "Hello world"

    def test_strip_html_nested(self):
        result = strip_html("<div><h1>Title</h1><p>Body text</p></div>")
        assert "Title" in result
        assert "Body text" in result

    def test_strip_html_empty(self):
        assert strip_html("") == ""
        assert strip_html(None) == ""

    def test_word_count_basic(self):
        assert word_count("hello world foo bar") == 4

    def test_word_count_empty(self):
        assert word_count("") == 0
        assert word_count("   ") == 0


# ── SEO title checks ──────────────────────────────────────────────────────────

class TestSeoTitle:
    def test_perfect_title_no_issues(self):
        p = make_product()
        issues = check_seo_title(p)
        assert issues == []

    def test_missing_seo_field_uses_product_title(self):
        p = make_product(seo={})
        issues = check_seo_title(p)
        # Product title is long enough — no issue expected
        assert not any(i.rule == "missing_seo_title" for i in issues)

    def test_missing_seo_title_critical(self):
        p = make_product(seo={"title": "", "description": "fine"}, title="")
        issues = check_seo_title(p)
        assert any(i.rule == "missing_seo_title" for i in issues)
        assert all(i.severity == IssueSeverity.CRITICAL for i in issues)

    def test_title_too_short_warning(self):
        p = make_product(seo={"title": "Short", "description": "fine"})
        issues = check_seo_title(p)
        assert any(i.rule == "seo_title_too_short" for i in issues)
        assert issues[0].severity == IssueSeverity.WARNING

    def test_title_too_long_warning(self):
        p = make_product(seo={"title": "A" * 80, "description": "fine"})
        issues = check_seo_title(p)
        assert any(i.rule == "seo_title_too_long" for i in issues)

    def test_optimal_title_length(self):
        p = make_product(seo={"title": "A" * 55, "description": "fine"})
        assert check_seo_title(p) == []


# ── Meta description checks ───────────────────────────────────────────────────

class TestMetaDescription:
    def test_perfect_meta_no_issues(self):
        assert check_meta_description(make_product()) == []

    def test_missing_meta_critical(self):
        p = make_product(seo={"title": "Fine title", "description": ""})
        issues = check_meta_description(p)
        assert any(i.rule == "missing_meta_description" for i in issues)
        assert issues[0].severity == IssueSeverity.CRITICAL

    def test_short_meta_warning(self):
        p = make_product(seo={"title": "Fine", "description": "Too short"})
        issues = check_meta_description(p)
        assert any(i.rule == "meta_description_too_short" for i in issues)
        assert issues[0].severity == IssueSeverity.WARNING

    def test_long_meta_warning(self):
        p = make_product(seo={"title": "Fine", "description": "x" * 200})
        issues = check_meta_description(p)
        assert any(i.rule == "meta_description_too_long" for i in issues)


# ── Image alt text checks ─────────────────────────────────────────────────────

class TestImageAltText:
    def test_all_alt_text_present(self):
        assert check_image_alt_text(make_product()) == []

    def test_missing_alt_critical(self):
        p = make_product(images=[
            {"id": 1, "alt": "Good alt"},
            {"id": 2, "alt": None},
            {"id": 3, "alt": ""},
        ])
        issues = check_image_alt_text(p)
        assert len(issues) == 1
        assert issues[0].rule == "missing_alt_text"
        assert issues[0].severity == IssueSeverity.CRITICAL
        assert "2 of 3" in issues[0].message

    def test_no_images_skips_check(self):
        p = make_product(images=[])
        assert check_image_alt_text(p) == []


# ── Description checks ────────────────────────────────────────────────────────

class TestDescription:
    def test_good_description_no_issues(self):
        assert check_description(make_product()) == []

    def test_no_description_critical(self):
        p = make_product(body_html="")
        issues = check_description(p)
        assert any(i.rule == "no_description" for i in issues)
        assert issues[0].severity == IssueSeverity.CRITICAL

    def test_none_description_critical(self):
        p = make_product(body_html=None)
        issues = check_description(p)
        assert any(i.rule == "no_description" for i in issues)

    def test_thin_description_critical(self):
        p = make_product(body_html="<p>Short description here.</p>")
        issues = check_description(p)
        assert any(i.rule == "thin_description" for i in issues)
        assert issues[0].severity == IssueSeverity.CRITICAL

    def test_borderline_description_warning(self):
        # ~100 words — triggers short_description warning
        p = make_product(body_html="<p>" + ("word " * 100) + "</p>")
        issues = check_description(p)
        assert any(i.rule == "short_description" for i in issues)
        assert issues[0].severity == IssueSeverity.WARNING

    def test_duplicate_description_flagged(self):
        html = "<p>" + ("same text " * 30) + "</p>"
        p1 = make_product(body_html=html, id=1)
        p2 = make_product(body_html=html, id=2)
        hashes: set = set()
        issues1 = check_duplicate_description(p1, hashes)
        issues2 = check_duplicate_description(p2, hashes)
        assert issues1 == []   # first product — not a duplicate
        assert any(i.rule == "duplicate_description" for i in issues2)

    def test_unique_descriptions_not_flagged(self):
        hashes: set = set()
        p1 = make_product(body_html="<p>" + ("unique text A " * 20) + "</p>", id=1)
        p2 = make_product(body_html="<p>" + ("unique text B " * 20) + "</p>", id=2)
        assert check_duplicate_description(p1, hashes) == []
        assert check_duplicate_description(p2, hashes) == []


# ── Image count checks ────────────────────────────────────────────────────────

class TestImages:
    def test_three_images_no_issues(self):
        assert check_images(make_product()) == []

    def test_no_images_critical(self):
        p = make_product(images=[])
        issues = check_images(p)
        assert any(i.rule == "no_images" for i in issues)
        assert issues[0].severity == IssueSeverity.CRITICAL

    def test_single_image_critical(self):
        p = make_product(images=[{"id": 1, "alt": "alt"}])
        issues = check_images(p)
        assert any(i.rule == "single_image" for i in issues)
        assert issues[0].severity == IssueSeverity.CRITICAL

    def test_two_images_warning(self):
        p = make_product(images=[
            {"id": 1, "alt": "a"}, {"id": 2, "alt": "b"}
        ])
        issues = check_images(p)
        assert any(i.rule == "few_images" for i in issues)
        assert issues[0].severity == IssueSeverity.WARNING


# ── Pricing checks ────────────────────────────────────────────────────────────

class TestPricing:
    def test_perfect_price_no_issues(self):
        assert check_pricing(make_product()) == []

    def test_zero_price_critical(self):
        p = make_product(variants=[{
            "id": 1, "price": "0.00",
            "compare_at_price": None,
            "inventory_management": "shopify",
            "inventory_quantity": 10,
        }])
        issues = check_pricing(p)
        assert any(i.rule == "zero_price" for i in issues)
        assert issues[0].severity == IssueSeverity.CRITICAL

    def test_non_charm_price_info(self):
        # Prices ending in .50 are not charm prices — should flag info
        p = make_product(variants=[{
            "id": 1, "price": "50.50",
            "compare_at_price": "60.00",
            "inventory_management": "shopify",
            "inventory_quantity": 10,
        }])
        issues = check_pricing(p)
        assert any(i.rule == "no_charm_pricing" for i in issues)

    def test_charm_price_99_no_issue(self):
        p = make_product(variants=[{
            "id": 1, "price": "49.99",
            "compare_at_price": "60.00",
            "inventory_management": "shopify",
            "inventory_quantity": 10,
        }])
        issues = check_pricing(p)
        assert not any(i.rule == "no_charm_pricing" for i in issues)

    def test_no_compare_at_price_info(self):
        p = make_product(variants=[{
            "id": 1, "price": "49.99",
            "compare_at_price": None,
            "inventory_management": "shopify",
            "inventory_quantity": 10,
        }])
        issues = check_pricing(p)
        assert any(i.rule == "no_compare_at_price" for i in issues)
        assert issues[0].severity == IssueSeverity.INFO


# ── Catalogue checks ──────────────────────────────────────────────────────────

class TestCatalogue:
    def test_good_product_no_issues(self):
        assert check_tags(make_product()) == []
        assert check_product_type(make_product()) == []

    def test_no_tags_warning(self):
        p = make_product(tags="")
        issues = check_tags(p)
        assert any(i.rule == "no_tags" for i in issues)
        assert issues[0].severity == IssueSeverity.WARNING

    def test_few_tags_info(self):
        p = make_product(tags="wool, blue")
        issues = check_tags(p)
        assert any(i.rule == "few_tags" for i in issues)
        assert issues[0].severity == IssueSeverity.INFO

    def test_missing_product_type_warning(self):
        p = make_product(product_type="")
        issues = check_product_type(p)
        assert any(i.rule == "missing_product_type" for i in issues)

    def test_published_zero_inventory_warning(self):
        p = make_product(
            status="active",
            variants=[{
                "id": 1, "price": "49.99",
                "compare_at_price": "60.00",
                "inventory_management": "shopify",
                "inventory_quantity": 0,
            }]
        )
        issues = check_published_zero_inventory(p)
        assert any(i.rule == "published_zero_inventory" for i in issues)
        assert issues[0].severity == IssueSeverity.WARNING

    def test_draft_zero_inventory_no_issue(self):
        p = make_product(
            status="draft",
            variants=[{
                "id": 1, "price": "49.99",
                "compare_at_price": None,
                "inventory_management": "shopify",
                "inventory_quantity": 0,
            }]
        )
        assert check_published_zero_inventory(p) == []


# ── Full run_rules integration ────────────────────────────────────────────────

class TestRunRules:
    def test_perfect_product_high_score(self):
        p = make_product()
        issues, score = run_rules(p, set())
        assert score >= 85
        # No critical or warning issues on a well-configured product
        assert not any(i.severity in (IssueSeverity.CRITICAL, IssueSeverity.WARNING) for i in issues)

    def test_terrible_product_low_score(self):
        p = make_product(
            seo={},
            body_html="",
            images=[],
            tags="",
            product_type="",
            variants=[{
                "id": 1, "price": "0.00",
                "compare_at_price": None,
                "inventory_management": "shopify",
                "inventory_quantity": 0,
            }],
            status="active",
        )
        issues, score = run_rules(p, set())
        critical_issues = [i for i in issues if i.severity == IssueSeverity.CRITICAL]
        assert score <= 30
        assert len(critical_issues) >= 3

    def test_score_floors_at_zero(self):
        # Even the worst possible product doesn't go negative
        p = make_product(
            seo={"title": "", "description": ""},
            body_html="",
            images=[],
            tags="",
            product_type="",
            vendor="",
            title="",
            variants=[{
                "id": 1, "price": "0.00",
                "compare_at_price": None,
                "inventory_management": "shopify",
                "inventory_quantity": 0,
            }],
            status="active",
        )
        _, score = run_rules(p, set())
        assert score >= 0

    def test_issues_have_required_fields(self):
        p = make_product(seo={}, body_html="", images=[], tags="")
        issues, _ = run_rules(p, set())
        for issue in issues:
            assert issue.rule
            assert issue.category in ("seo", "content", "ux", "catalogue")
            assert issue.severity in (IssueSeverity.CRITICAL, IssueSeverity.WARNING, IssueSeverity.INFO)
            assert issue.message
            assert issue.fix_hint


# ── Store score aggregation ───────────────────────────────────────────────────

class TestCalculateStoreScore:
    def test_all_perfect_products(self):
        results = [
            {"score": 95, "issues": []},
            {"score": 90, "issues": []},
        ]
        overall, cats = calculate_store_score(results)
        assert overall >= 80

    def test_empty_results(self):
        overall, cats = calculate_store_score([])
        assert overall == 0
        assert cats == {"seo": 0, "content": 0, "ux": 0, "catalogue": 0}

    def test_mixed_results_weighted(self):
        # All products have content issues — content score should be low
        results = [
            {
                "score": 40,
                "issues": [
                    {"category": "content", "severity": "critical"},
                    {"category": "content", "severity": "critical"},
                ]
            },
        ]
        overall, cats = calculate_store_score(results)
        # Content is 35% weight — a poor content score should drag overall down
        assert cats["content"] < 80
