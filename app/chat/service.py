import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

import httpx
from fastapi import UploadFile, HTTPException

from app.config import settings
from app.chat.image_caption import ImageCaptionService
from app.chat.mistral_client import MistralService
from app.chat.schemas import ProductRecommendation, ChatResponse

logger = logging.getLogger(__name__)


def _flatten_search_criteria(prefix: str, obj: Any, out: Dict[str, Any]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            _flatten_search_criteria(f"{prefix}[{k}]", v, out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _flatten_search_criteria(f"{prefix}[{i}]", v, out)
    else:
        out[prefix] = obj


def _extract_product_data(product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        prod_id = product.get("id")
        sku = str(product.get("sku") or "").strip()
        name = str(product.get("name") or "").strip()
        price = float(product.get("price") or 0)
    except Exception:
        return None

    if not prod_id or not sku or not name:
        return None

    return {
        "id": str(prod_id),
        "name": name,
        "sku": sku,
        "price": price,
    }


async def fetch_magento_products(
    search_criteria: Optional[Dict[str, Any]] = None,
    page_size: int = 5,
    max_pages: int = 1,
) -> List[Dict[str, Any]]:

    if not settings.MAGENTO_BASE_URL or not settings.MAGENTO_ACCESS_TOKEN:
        logger.error("Magento configuration missing")
        return []

    endpoint = settings.MAGENTO_BASE_URL.rstrip("/") + "/rest/fr/V1/products"
    headers = {
        "Authorization": f"Bearer {settings.MAGENTO_ACCESS_TOKEN}",
        "Accept": "application/json",
    }
    timeout = httpx.Timeout(connect=5.0, read=5.0, write=5.0, pool=5.0)

    items: List[Dict[str, Any]] = []
    page = 1

    async with httpx.AsyncClient(timeout=timeout, headers=headers, verify=False) as client:
        while page <= max_pages:
            params: Dict[str, Any] = {
                "searchCriteria[currentPage]": page,
                "searchCriteria[pageSize]": page_size,
            }

            if search_criteria:
                flat: Dict[str, Any] = {}
                _flatten_search_criteria("searchCriteria", search_criteria, flat)
                params.update(flat)

            logger.info("Calling Magento API (page %s)...", page)
            resp = await client.get(endpoint, params=params)

            if resp.status_code != 200:
                logger.error("Magento API error %s: %s", resp.status_code, resp.text)
                break

            data = resp.json()
            page_items = data.get("items", [])
            items.extend(page_items)

            if len(page_items) < page_size:
                break

            page += 1

    return items


class ChatService:

    @staticmethod
    async def fetch_products_by_sku(sku: str) -> List[Dict[str, Any]]:
        search_criteria = {
            "filter_groups": [
                {
                    "filters": [
                        {
                            "field": "sku",
                            "value": sku,
                            "condition_type": "eq",
                        }
                    ]
                }
            ]
        }

        try:
            return await fetch_magento_products(search_criteria)
        except Exception as e:
            logger.error("SKU fetch failed: %s", e, exc_info=True)
            return []

    @staticmethod
    async def recommend_products(message: str, user_id: int) -> ChatResponse:
        try:
            search_criteria = {
                "filter_groups": [
                    {
                        "filters": [
                            {
                                "field": "name",
                                "value": f"%{message}%",
                                "condition_type": "like",
                            }
                        ]
                    }
                ]
            }

            items = await fetch_magento_products(
                search_criteria=search_criteria,
                page_size=5,
                max_pages=1,
            )

            recommendations: List[ProductRecommendation] = []
            for product in items:
                extracted = _extract_product_data(product)
                if extracted:
                    recommendations.append(
                        ProductRecommendation(
                            **extracted,
                            relevance_score=None,
                        )
                    )

            return ChatResponse(
                message=f"Found {len(recommendations)} product(s)",
                recommendations=recommendations,
            )

        except Exception as e:
            logger.error("Text search failed: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @staticmethod
    async def recommend_products_by_image(
        image: UploadFile,
        user_id: int,
    ) -> ChatResponse:
        try:
            # Step 1: Generate image caption
            logger.info("🔹 Step 1: Starting image caption generation...")
            caption = await asyncio.wait_for(
                ImageCaptionService.generate_caption(image),
                timeout=15.0
            )
            logger.info("🔹 Step 1 complete: Image caption: %s", caption)

            # Step 2: Extract and filter keywords
            stopwords = {"the", "a", "an", "with", "and", "or", "in", "on", "for", "of"}
            words = re.findall(r'\w+', caption.lower())
            keywords = [w for w in words if w not in stopwords and len(w) > 2]

            if not keywords:
                keywords = [caption.lower()]  # fallback if all words removed

            logger.info("Filtered keywords for Magento search: %s", keywords)

            # Step 3: Build search criteria (single group)
            filters = []
            for kw in keywords:
                filters.append({"field": "name", "value": f"%{kw}%", "condition_type": "like"})
                filters.append({"field": "sku", "value": f"%{kw}%", "condition_type": "like"})

            search_criteria = {"filter_groups": [{"filters": filters}]}
            logger.info("🔹 Step 3: Search criteria: %s", search_criteria)

            # Step 4: Fetch products
            items = await asyncio.wait_for(
                fetch_magento_products(
                    search_criteria=search_criteria,
                    page_size=10,
                    max_pages=1,
                ),
                timeout=10.0
            )
            logger.info("🔹 Step 4: Fetched %d products", len(items))

            # Step 5: Extract product data
            recommendations: List[ProductRecommendation] = []
            for product in items:
                extracted = _extract_product_data(product)
                if extracted:
                    recommendations.append(ProductRecommendation(**extracted, relevance_score=None))

            logger.info("🔹 Step 5: Built %d recommendations", len(recommendations))

            # Step 6: Return response
            return ChatResponse(
                message=f"Found {len(recommendations)} product(s) using image",
                recommendations=recommendations,
            )

        except Exception as e:
            logger.error("❌ Image-based product recommendation failed: %s", e, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Image-based product recommendation failed",
            )
