import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


async def create_session(shop_domain: str, tenant_id: str, duration_days: int = 30) -> str:
    """Create a new session and store in database"""
    from app.dependencies import get_db

    db = await get_db()

    session_id = secrets.token_urlsafe(32)
    now = datetime.utcnow()

    session_doc = {
        "session_id": session_id,
        "shop_domain": shop_domain,
        "tenant_id": tenant_id,
        "created_at": now,
        "last_accessed": now,
        "expires_at": now + timedelta(days=duration_days),
        "data": {}
    }

    await db.sessions.insert_one(session_doc)
    logger.info(f"✅ Session created: {session_id} for {shop_domain}")

    return session_id


async def get_session(session_id: str) -> Optional[dict]:
    """Retrieve session from database and update last accessed time"""
    from app.dependencies import get_db

    db = await get_db()

    session = await db.sessions.find_one({
        "session_id": session_id,
        "expires_at": {"$gt": datetime.utcnow()}
    })

    if session:
        await db.sessions.update_one(
            {"session_id": session_id},
            {"$set": {"last_accessed": datetime.utcnow()}}
        )
        logger.info(f"✅ Session retrieved: {session_id}")
        return session

    logger.warning(f"⚠️ Session not found or expired: {session_id}")
    return None


async def delete_session(session_id: str):
    """Delete session from database"""
    from app.dependencies import get_db

    db = await get_db()
    await db.sessions.delete_one({"session_id": session_id})
    logger.info(f"🗑️ Session deleted: {session_id}")


async def get_session_by_shop(shop_domain: str) -> Optional[dict]:
    """Get most recent valid session for a shop"""
    from app.dependencies import get_db

    db = await get_db()

    session = await db.sessions.find_one(
        {
            "shop_domain": shop_domain,
            "expires_at": {"$gt": datetime.utcnow()}
        },
        sort=[("last_accessed", -1)]
    )

    if session:
        logger.info(f"✅ Found session for shop: {shop_domain}")
        return session

    logger.warning(f"⚠️ No valid session for shop: {shop_domain}")
    return None
