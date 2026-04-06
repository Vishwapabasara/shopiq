"""
Shopify Admin API client.
Handles pagination, rate limiting, and error normalisation.
"""
import asyncio
import httpx
from typing import AsyncGenerator

SHOPIFY_API_VERSION = "2024-01"


def shopify_headers(access_token: str) -> dict:
    return {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }


def _parse_next_url(link_header: str) -> str | None:
    """Extract the 'next' cursor URL from Shopify's Link header."""
    if not link_header or 'rel="next"' not in link_header:
        return None
    for part in link_header.split(","):
        if 'rel="next"' in part:
            return part.split(";")[0].strip().strip("<>")
    return None


async def fetch_all_products(shop: str, access_token: str) -> list[dict]:
    """
    Fetch every active product from the store.
    Follows Shopify cursor pagination automatically.
    Returns raw product dicts as returned by the REST API.
    """
    products: list[dict] = []
    url = f"https://{shop}/admin/api/{SHOPIFY_API_VERSION}/products.json"
    params = {
        "limit": 250,
        "status": "active",
        "fields": (
            "id,title,body_html,images,variants,tags,status,"
            "published_at,handle,product_type,vendor,seo"
        ),
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        while url:
            # Respect Shopify's 2 req/sec REST limit with a small delay
            await asyncio.sleep(0.5)

            response = await client.get(
                url,
                params=params,
                headers=shopify_headers(access_token),
            )

            if response.status_code == 429:
                # Rate limited — back off and retry once
                retry_after = int(response.headers.get("Retry-After", 2))
                await asyncio.sleep(retry_after)
                response = await client.get(url, params=params, headers=shopify_headers(access_token))

            response.raise_for_status()
            data = response.json()
            products.extend(data.get("products", []))

            url = _parse_next_url(response.headers.get("Link", ""))
            params = {}  # cursor URL already contains all params

    return products


async def fetch_product_collections(
    shop: str, access_token: str, product_id: int
) -> list[dict]:
    """Fetch which collections a product belongs to."""
    url = (
        f"https://{shop}/admin/api/{SHOPIFY_API_VERSION}"
        f"/products/{product_id}/collects.json"
    )
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, headers=shopify_headers(access_token))
        if response.status_code != 200:
            return []
        return response.json().get("collects", [])


async def get_shop_info(shop: str, access_token: str) -> dict:
    """Fetch basic store metadata."""
    url = f"https://{shop}/admin/api/{SHOPIFY_API_VERSION}/shop.json"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, headers=shopify_headers(access_token))
        response.raise_for_status()
        return response.json().get("shop", {})
