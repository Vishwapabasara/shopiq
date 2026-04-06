# ShopIQ — Shopify Intelligence Platform

> Module 1: ShopAudit AI — Store Health Analyser

A production-ready SaaS platform that audits every product in a Shopify store across 18 SEO, content, UX, and catalogue rules, then uses GPT-4o to score descriptions and generate rewrites. Built as the first module of a 10-module Shopify intelligence platform.

---

## Architecture

```
shopiq/
├── backend/                  # FastAPI + Celery
│   ├── app/
│   │   ├── main.py           # FastAPI app entry point
│   │   ├── config.py         # Pydantic settings (env vars)
│   │   ├── dependencies.py   # MongoDB client + auth guard
│   │   ├── models/
│   │   │   └── schemas.py    # All Pydantic models
│   │   ├── routers/
│   │   │   ├── auth.py       # Shopify OAuth install + callback
│   │   │   └── audit.py      # Audit trigger, status, results
│   │   ├── services/
│   │   │   ├── audit_rules.py  # 18 deterministic rules engine
│   │   │   └── ai_scorer.py    # GPT-4o batch scoring
│   │   ├── utils/
│   │   │   ├── crypto.py       # AES-256 token encryption
│   │   │   └── shopify_client.py  # Paginated Shopify API client
│   │   └── workers/
│   │       ├── celery_app.py   # Celery + Redis config
│   │       └── audit_worker.py # Main pipeline Celery task
│   ├── tests/
│   │   └── test_audit_rules.py  # 47 unit tests (all passing)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                 # React + Vite + Tailwind
│   ├── src/
│   │   ├── App.tsx           # Router + auth guard
│   │   ├── lib/
│   │   │   ├── api.ts        # Typed Axios client
│   │   │   └── utils.ts      # Score colours, formatting
│   │   ├── hooks/
│   │   │   └── useAudit.ts   # React Query hooks + 2s polling
│   │   ├── components/
│   │   │   ├── ui/           # ScoreRing, StatCard, Badges, Spinner
│   │   │   ├── layout/       # Sidebar nav
│   │   │   └── audit/        # AuditProgress, ScoreOverview,
│   │   │                     # ProductTable, ProductDrawer, ScoreHistory
│   │   └── pages/
│   │       ├── AuditPage.tsx
│   │       ├── LoginPage.tsx
│   │       └── ComingSoonPage.tsx
│   └── Dockerfile
└── docker-compose.yml
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI 0.111, Python 3.12 |
| Database | MongoDB Atlas (Motor async driver) |
| Queue | Celery 5.4 + Redis 7 |
| AI | OpenAI GPT-4o (structured JSON output) |
| Frontend | React 18, Vite, Tailwind CSS, React Query |
| Charts | Recharts |
| Email | SendGrid |
| PDF | WeasyPrint + AWS S3 |
| Auth | Shopify OAuth 2.0, AES-256 token encryption |
| Billing | Stripe (subscriptions + webhooks) |

---

## Quickstart

### 1. Clone and configure

```bash
git clone <your-repo> shopiq
cd shopiq
cp backend/.env.example backend/.env
# Edit backend/.env with your credentials (see Environment Variables below)
```

### 2. Run with Docker Compose

```bash
docker-compose up --build
```

This starts:
- **API** on `http://localhost:8000`
- **Frontend** on `http://localhost:5173`
- **MongoDB** on `localhost:27017`
- **Redis** on `localhost:6379`
- **Celery worker** (background jobs)
- **Celery Beat** (monthly scheduled audits)

### 3. Local development (without Docker)

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install beautifulsoup4 lxml

# Start API
uvicorn app.main:app --reload --port 8000

# Start Celery worker (separate terminal)
celery -A app.workers.celery_app worker --loglevel=info

# Start Celery Beat scheduler (separate terminal)
celery -A app.workers.celery_app beat --loglevel=info
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### 4. Run tests

```bash
cd backend
python -m pytest tests/ -v
# 47 tests, all passing
```

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in:

### Required

| Variable | Description |
|---|---|
| `SHOPIFY_API_KEY` | From your Shopify Partner Dashboard app |
| `SHOPIFY_API_SECRET` | From your Shopify Partner Dashboard app |
| `APP_URL` | Your app's public URL (e.g. `https://shopiq.yourdomain.com`) |
| `MONGO_URI` | MongoDB connection string |
| `REDIS_URL` | Redis connection string |
| `OPENAI_API_KEY` | OpenAI API key for GPT-4o |
| `TOKEN_ENCRYPTION_KEY` | Fernet key — generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `SESSION_SECRET` | Random 32+ char string for session signing |

### Optional (for full features)

| Variable | Description |
|---|---|
| `SENDGRID_API_KEY` | For completion notification emails |
| `FROM_EMAIL` | Sender address for emails |
| `AWS_ACCESS_KEY_ID` | For PDF report storage |
| `AWS_SECRET_ACCESS_KEY` | For PDF report storage |
| `S3_BUCKET` | S3 bucket name for PDFs |
| `STRIPE_SECRET_KEY` | For billing |
| `STRIPE_WEBHOOK_SECRET` | For Stripe webhook verification |

---

## Shopify App Setup

1. Go to [partners.shopify.com](https://partners.shopify.com) → Apps → Create app
2. Set **App URL** to `https://yourdomain.com/auth/shopify/install`
3. Set **Allowed redirection URL** to `https://yourdomain.com/auth/shopify/callback`
4. Copy **API key** and **API secret** to your `.env`
5. Required scopes: `read_products, read_inventory, read_orders, read_collections`

---

## API Endpoints

### Auth
| Method | Route | Description |
|---|---|---|
| `GET` | `/auth/shopify/install?shop=...` | Initiates OAuth flow |
| `GET` | `/auth/shopify/callback` | Handles OAuth callback, stores token |
| `GET` | `/auth/me` | Returns current session info |
| `POST` | `/auth/logout` | Clears session |

### Audit
| Method | Route | Description |
|---|---|---|
| `POST` | `/audit/run` | Trigger new audit, returns `audit_id` |
| `GET` | `/audit/{id}/status` | Poll status (queued/running/complete/failed) |
| `GET` | `/audit/{id}/results` | Full results with filtering + pagination |
| `GET` | `/audit/{id}/product/{product_id}` | Single product detail + AI rewrite |
| `GET` | `/audit/history` | Past audits for score trend chart |

### Query params for `/audit/{id}/results`
- `severity=critical|warning|info` — filter by severity
- `sort=score_asc|score_desc|alpha` — sort order
- `limit=25` — page size
- `offset=0` — pagination offset

---

## Audit Pipeline

```
Merchant installs app
        ↓
Shopify OAuth (3-step HMAC-verified flow)
        ↓
POST /audit/run → creates audit doc → dispatches Celery task
        ↓
Celery worker:
  1. Fetch all products via Shopify Admin API (paginated, rate-limited)
  2. Run 18 deterministic rules per product (pure functions, no I/O)
  3. Batch GPT-4o scoring (10 products/batch, async)
  4. Blend scores (60% rules + 40% AI)
  5. Aggregate store-level category scores
  6. Save to MongoDB
  7. Send completion email via SendGrid
        ↓
Frontend polls /audit/{id}/status every 2s
        ↓
On complete: renders ScoreOverview + ProductTable + ScoreHistory
```

---

## Audit Rules (18 deterministic + 3 AI)

### SEO (25% weight)
- Missing SEO title → **Critical**
- SEO title too short (<30 chars) → Warning
- SEO title too long (>70 chars) → Warning
- Missing meta description → **Critical**
- Meta description too short (<80 chars) → Warning
- Meta description too long (>160 chars) → Warning
- Image alt text missing → **Critical**
- Bad URL handle (invalid characters) → Warning

### Content (35% weight)
- No description → **Critical**
- Thin description (<80 words) → **Critical**
- Short description (<150 words) → Warning
- Duplicate description across products → Warning
- Generic/placeholder title → **Critical**
- **AI: GPT-4o content quality score** (0–100)
- **AI: GPT-4o rewrite suggestion**

### UX (25% weight)
- No images → **Critical**
- Single image only → **Critical**
- Fewer than 3 images → Warning
- No charm pricing (.99/.95/.97) → Info
- No compare-at price → Info
- No real variants configured → Info
- **AI: GPT-4o overall page health verdict**

### Catalogue (15% weight)
- No product tags → Warning
- Fewer than 3 tags → Info
- Missing product type → Warning
- Missing vendor → Info
- Published with zero inventory → Warning

---

## Scoring Formula

```python
# Per-product deterministic score
score = 100
for issue in issues:
    score -= {CRITICAL: 15, WARNING: 8, INFO: 3}[issue.severity]
score = max(0, score)

# Blend with AI score
final_score = round(score * 0.6 + ai_score * 0.4)

# Store-level category score (average across all products)
category_scores = {category: avg(product_scores_for_category)}

# Overall store score (weighted average)
overall = (seo * 0.25) + (content * 0.35) + (ux * 0.25) + (catalogue * 0.15)
```

---

## MongoDB Collections

### `tenants`
One document per installed Shopify store. Stores encrypted access token, plan, and feature flags.

### `audits`
One document per audit run. Contains the full `product_results` array embedded (avoids N+1 queries on the results page). Indexed on `(tenant_id, created_at)`.

---

## Planned Modules (M2–M10)

| Module | Status |
|---|---|
| M1 ShopAudit AI | ✅ Complete |
| M2 ReturnRadar | 🔜 Next |
| M3 StockSense | 🔜 Planned |
| M4 PricePulse | 🔜 Planned |
| M5 BulkCopy AI | 🔜 Planned |
| M6 ReviewReply Pro | 🔜 Planned |
| M7 LeadForge | 🔜 Planned |
| M8 InvoiceFlow | 🔜 Planned |
| M9 ContractPilot | 🔜 Planned |
| M10 OnboardKit | 🔜 Planned |

---

## Pricing

| Plan | Price | Modules | Stores |
|---|---|---|---|
| Starter | $29/mo | ShopAudit only | 1 |
| Growth | $79/mo | Any 3 modules | 1 |
| Pro | $149/mo | All modules | 1 |
| Agency | $299/mo | All modules | 10 |

---

## Deployment (Production)

```bash
# 1. Provision: EC2 t3.small (or Railway / Render)
# 2. MongoDB Atlas M0 free tier to start
# 3. Redis via Upstash (free tier) or ElastiCache

# 4. Build and push images
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

# 5. Set Nginx reverse proxy
#    /          → frontend:5173
#    /auth/*    → api:8000
#    /audit/*   → api:8000
#    /health    → api:8000
```

---

## License

MIT
