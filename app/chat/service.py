import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

import httpx
from fastapi import UploadFile, HTTPException

from app.config import settings
from app.chat.image_caption import ImageCaptionService
from app.chat.schemas import ProductRecommendation, ChatResponse

logger = logging.getLogger(__name__)

# ------------------------
# Helpers
# ------------------------

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


def _is_image_quality_poor(image: UploadFile, image_bytes: bytes) -> Optional[str]:
    if not image_bytes or len(image_bytes) < 3_000:
        return "The image is too small or blurry. Please upload a clearer photo."

    if not image.content_type or not image.content_type.startswith("image/"):
        return "The uploaded file is not a valid image."

    return None


def _extract_keywords(text: str, language: str) -> List[str]:
    stopwords_en = {
        "the", "a", "an", "with", "and", "or", "in", "on",
        "for", "of", "this", "that", "is", "are",
        "person", "wearing", "background", "photo", "image",
    }

    stopwords_fr = {
        "le", "la", "les", "un", "une", "des", "de", "du",
        "que", "qui", "avec", "pour", "sur", "et",
        "personne", "image", "photo", "arriere",
    }

    stopwords = stopwords_fr if language == "fr" else stopwords_en

    words = re.findall(r"[^\W\d_]+", text.lower(), flags=re.UNICODE)
    keywords = [w for w in words if w not in stopwords and len(w) > 2]

    seen = set()
    result = []
    for w in keywords:
        if w not in seen:
            seen.add(w)
            result.append(w)

    return result[:6]


# ------------------------
# Magento Fetch (language-aware)
# ------------------------

async def fetch_magento_products(
    search_criteria: Optional[Dict[str, Any]] = None,
    page_size: int = 20,
    max_pages: int = 2,
    language: str = "en",
) -> List[Dict[str, Any]]:

    if not settings.MAGENTO_BASE_URL or not settings.MAGENTO_ACCESS_TOKEN:
        return []

    language = language.strip().lower()
    store_view = (
        settings.MAGENTO_STORE_VIEW_FR
        if language == "fr"
        else settings.MAGENTO_STORE_VIEW_EN
    )

    endpoint = (
        settings.MAGENTO_BASE_URL.rstrip("/")
        + f"/rest/{store_view}/V1/products"
    )

    headers = {
        "Authorization": f"Bearer {settings.MAGENTO_ACCESS_TOKEN}",
        "Accept": "application/json",
    }

    items: List[Dict[str, Any]] = []

    timeout = httpx.Timeout(
        connect=settings.MAGENTO_TIMEOUT,
        read=settings.MAGENTO_TIMEOUT,
        write=settings.MAGENTO_TIMEOUT,
        pool=settings.MAGENTO_TIMEOUT,
    )

    async with httpx.AsyncClient(
        headers=headers,
        verify=False,
        timeout=timeout,
    ) as client:
        for page in range(1, max_pages + 1):
            params = {
                "searchCriteria[currentPage]": page,
                "searchCriteria[pageSize]": page_size,
            }

            if search_criteria:
                flat = {}
                _flatten_search_criteria("searchCriteria", search_criteria, flat)
                params.update(flat)

            resp = await _get_with_retry(
                client=client,
                endpoint=endpoint,
                params=params,
                retries=settings.MAGENTO_RETRIES,
            )
            resp.raise_for_status()
            data = resp.json()
            page_items = data.get("items", [])
            items.extend(page_items)

            if len(page_items) < page_size:
                break

    return items


async def _get_with_retry(
    client: httpx.AsyncClient,
    endpoint: str,
    params: Dict[str, Any],
    retries: int,
) -> httpx.Response:
    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            return await client.get(endpoint, params=params)
        except (
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.ReadError,
            httpx.RemoteProtocolError,
        ) as exc:
            last_exc = exc
            if attempt >= retries:
                break
            backoff = 0.5 * (2 ** attempt)
            await asyncio.sleep(backoff)
    assert last_exc is not None
    raise last_exc


# ------------------------
# Chat Service
# ------------------------

class ChatService:

    @staticmethod
    async def fetch_products_by_sku(sku: str, language: str = "en") -> List[Dict[str, Any]]:
        search_criteria = {
            "filter_groups": [
                {
                    "filters": [
                        {"field": "sku", "value": sku, "condition_type": "eq"}
                    ]
                }
            ]
        }

        try:
            return await fetch_magento_products(
                search_criteria=search_criteria,
                language=language,
            )
        except Exception as e:
            logger.error("SKU fetch failed: %s", e, exc_info=True)
            return []


    @staticmethod
    async def recommend_products(
        message: str,
        user_id: int,
        language: str = "en",
    ) -> ChatResponse:

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
            page_size=10,
            max_pages=1,
            language=language,
        )

        recommendations: List[ProductRecommendation] = []
        for product in items:
            extracted = _extract_product_data(product)
            if extracted:
                recommendations.append(
                    ProductRecommendation(**extracted, relevance_score=None)
                )

        return ChatResponse(
            message=f"Found {len(recommendations)} product(s)",
            recommendations=recommendations,
        )


    @staticmethod
    async def recommend_products_by_image(
        image: UploadFile,
        user_id: int,
        language: str = "en",
    ) -> ChatResponse:

        try:
            image_bytes = await image.read()
            language = language.strip().lower()

            quality_error = _is_image_quality_poor(image, image_bytes)
            if quality_error:
                return ChatResponse(message=quality_error, recommendations=[])

            # Caption matches catalog language
            if language == "fr":
                caption_data = await ImageCaptionService.generate_caption_fr_from_bytes(
                    image_bytes=image_bytes,
                    content_type=image.content_type,
                )
            else:
                caption_data = await ImageCaptionService.generate_caption_en_from_bytes(
                    image_bytes=image_bytes,
                    content_type=image.content_type,
                )

            if not caption_data["ok"]:
                return ChatResponse(
                    message=caption_data["reason"] or "Image could not be processed",
                    recommendations=[],
                )

            keywords = _extract_keywords(caption_data["caption"], language)

            filters = [
                {"field": "name", "value": f"%{kw}%", "condition_type": "like"}
                for kw in keywords
            ]

            items = await fetch_magento_products(
                search_criteria={"filter_groups": [{"filters": filters}]},
                page_size=40,
                max_pages=2,
                language=language,
            )

            recommendations: List[ProductRecommendation] = []

            for product in items:
                extracted = _extract_product_data(product)
                if not extracted:
                    continue

                haystack = (
                    extracted["name"].lower()
                    + " "
                    + str(product.get("description", "")).lower()
                )

                relevance = sum(1 for kw in keywords if kw in haystack)

                if relevance > 0:
                    recommendations.append(
                        ProductRecommendation(**extracted, relevance_score=relevance)
                    )

            recommendations.sort(
                key=lambda x: x.relevance_score or 0,
                reverse=True,
            )

            return ChatResponse(
                message=f"Found {len(recommendations)} product(s) using image",
                recommendations=recommendations,
            )

        except Exception as e:
            logger.error("Image-based recommendation failed: %s", e, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Image-based product recommendation failed",
            )
