#!/usr/bin/env python3
"""
ShopIQ Dev Server
─────────────────
Single-command dev server with:
  - In-memory MongoDB (mongomock) — no MongoDB install needed
  - Auto-seeded mock data (12 realistic Shopify products)
  - Auto-login endpoint (no Shopify credentials needed)
  - Full audit pipeline using real rules engine + pre-written AI results

Usage:
    pip install fastapi uvicorn motor mongomock pydantic-settings \
                beautifulsoup4 lxml starlette itsdangerous httpx
    python dev_server.py

Then open:
    http://localhost:8000/dev/login   → auto-login + redirect to frontend
    http://localhost:8000/dev/seed-audit  → seed mock audit data
    http://localhost:8000/docs        → interactive API docs

Frontend (in a separate terminal):
    cd frontend && npm install && npm run dev
    Open http://localhost:5173
"""

import sys
import os

# ── Patch motor to use mongomock BEFORE any app imports ──────────────────────
try:
    import mongomock
    import motor.motor_asyncio
    motor.motor_asyncio.AsyncIOMotorClient = mongomock.MongoClient
    print("✅ Using in-memory MongoDB (mongomock)")
except ImportError:
    print("❌ mongomock not installed. Run: pip install mongomock")
    sys.exit(1)

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

# ── Start the app ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    print("\n" + "="*60)
    print("  ShopIQ Dev Server")
    print("="*60)
    print("  API:       http://localhost:8000")
    print("  API docs:  http://localhost:8000/docs")
    print()
    print("  Quick start:")
    print("  1. Open http://localhost:8000/dev/login")
    print("     → Auto-creates demo store session")
    print("  2. POST http://localhost:8000/dev/seed-audit")
    print("     → Runs audit on 12 mock products, saves to DB")
    print("     → Or use the button in the frontend")
    print()
    print("  Frontend:  cd frontend && npm run dev")
    print("             Then open http://localhost:5173")
    print("="*60 + "\n")

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        app_dir="backend",
        log_level="info",
    )
