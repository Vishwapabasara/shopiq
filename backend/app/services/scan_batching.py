import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def get_product_batch(
    all_products: list,
    scan_state: dict,
    batch_size: int,
) -> tuple[list, dict]:
    """
    Return (batch, new_scan_state) for a free-tier rotating audit.

    Priority:
      1. Products not yet seen (never audited)
      2. Products updated since last scan (Shopify updated_at)
      3. Cursor-ordered rotation so every product is eventually covered
    """
    if batch_size <= 0 or not all_products:
        return all_products, scan_state

    all_known_ids: set = set(scan_state.get("all_known_product_ids", []))
    cursor: int = scan_state.get("cursor", 0)
    last_scan_at: Optional[datetime] = scan_state.get("last_scan_at")

    # Stable sort by product id string so cursor is deterministic across calls
    sorted_products = sorted(all_products, key=lambda p: str(p.get("id", "")))
    all_ids = [str(p.get("id", "")) for p in sorted_products]
    n = len(sorted_products)

    cursor = cursor % n  # guard against store shrinking

    # ── Priority 1: products never seen ─────────────────────────────────────────
    new_products = [p for p in sorted_products if str(p.get("id", "")) not in all_known_ids]

    # ── Priority 2: products updated since last scan ─────────────────────────────
    updated_products: list = []
    if last_scan_at:
        for p in sorted_products:
            pid = str(p.get("id", ""))
            if pid not in all_known_ids:
                continue
            updated_at_str = p.get("updated_at")
            if not updated_at_str:
                continue
            try:
                updated_at = datetime.fromisoformat(
                    updated_at_str.replace("Z", "+00:00")
                ).replace(tzinfo=None)
                if updated_at > last_scan_at:
                    updated_products.append(p)
            except Exception:
                pass

    # ── Priority 3: cursor-ordered rotation ──────────────────────────────────────
    rotation = [sorted_products[(cursor + i) % n] for i in range(n)]

    # Merge with deduplication, maintaining priority order
    seen: set = set()
    prioritized: list = []
    for p in new_products + updated_products + rotation:
        pid = str(p.get("id", ""))
        if pid not in seen:
            seen.add(pid)
            prioritized.append(p)

    batch = prioritized[:batch_size]

    # ── Advance cursor ────────────────────────────────────────────────────────────
    new_cursor = cursor
    if batch:
        last_id = str(batch[-1].get("id", ""))
        if last_id in all_ids:
            new_cursor = (all_ids.index(last_id) + 1) % n
        else:
            new_cursor = (cursor + batch_size) % n

    new_state = {
        "cursor": new_cursor,
        "scanned_product_ids": [str(p.get("id", "")) for p in batch],
        "all_known_product_ids": list(set(all_known_ids) | set(all_ids)),
        "last_scan_at": datetime.utcnow(),
        "total_products": n,
    }

    logger.info(
        f"🔄 Batch scan: {len(batch)}/{n} products | cursor {cursor}→{new_cursor}"
    )
    return batch, new_state
