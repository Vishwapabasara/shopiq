from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


# ── Enums ─────────────────────────────────────────────────────────────────────

class AuditStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class IssueSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class TriggerSource(str, Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    WEBHOOK = "webhook"


class Plan(str, Enum):
    STARTER = "starter"
    GROWTH = "growth"
    PRO = "pro"
    AGENCY = "agency"


# ── Issue model ───────────────────────────────────────────────────────────────

class AuditIssue(BaseModel):
    rule: str                        # e.g. "missing_alt_text"
    category: str                    # seo | content | ux | catalogue
    severity: IssueSeverity
    message: str                     # human-readable description
    fix_hint: str                    # one-line actionable fix


# ── Per-product result ────────────────────────────────────────────────────────

class ProductAuditResult(BaseModel):
    shopify_product_id: str
    title: str
    handle: str
    score: int = Field(ge=0, le=100)
    issues: list[AuditIssue] = []

    # AI layer results (populated after GPT-4o batch)
    ai_score: Optional[int] = None
    ai_improvements: list[str] = []
    ai_rewrite: Optional[str] = None
    ai_verdict: Optional[str] = None

    # Snapshot metadata
    image_count: int = 0
    word_count: int = 0
    has_seo_title: bool = False
    has_meta_description: bool = False


# ── Audit document ────────────────────────────────────────────────────────────

class CategoryScores(BaseModel):
    seo: int = 0
    content: int = 0
    ux: int = 0
    catalogue: int = 0


class AuditDocument(BaseModel):
    tenant_id: str
    status: AuditStatus = AuditStatus.QUEUED
    overall_score: Optional[int] = None
    category_scores: Optional[CategoryScores] = None
    product_results: list[ProductAuditResult] = []
    products_scanned: int = 0
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    pdf_url: Optional[str] = None
    triggered_by: TriggerSource = TriggerSource.MANUAL
    celery_task_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


# ── Tenant document ───────────────────────────────────────────────────────────

class TenantDocument(BaseModel):
    shop_domain: str
    access_token: str                # encrypted
    scopes: str = ""
    plan: Plan = Plan.STARTER
    modules_enabled: list[str] = ["audit"]
    shop_name: Optional[str] = None
    shop_email: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    installed_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── API response schemas ──────────────────────────────────────────────────────

class AuditRunResponse(BaseModel):
    audit_id: str
    status: AuditStatus
    message: str


class AuditStatusResponse(BaseModel):
    audit_id: str
    status: AuditStatus
    products_scanned: int
    overall_score: Optional[int] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
