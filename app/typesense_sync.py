"""
Syncs the full Magento product catalog into Typesense.

Usage (run from telia-backend/):
    python -m app.typesense_sync              # incremental upsert
    python -m app.typesense_sync --recreate   # drop + recreate collection first
"""
import asyncio
import json
import logging
import re
import sys
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SYNC_PAGE_SIZE = 100   # products per Magento page
SYNC_MAX_PAGES = 50    # up to 5 000 products per language store
BATCH_SIZE = 100       # documents per Typesense import batch


def _build_typesense_doc(
    product: Dict[str, Any],
    language: str,
) -> Optional[Dict[str, Any]]:
    """Convert a raw Magento product dict to a Typesense document."""
    sku = str(product.get("sku") or "").strip()
    name = str(product.get("name") or "").strip()
    prod_id = product.get("id")
    if not sku or not name or prod_id is None:
        return None

    try:
        price = float(product.get("price") or 0)
    except Exception:
        price = 0.0

    # Import helpers from service without triggering the full module at top-level
    from app.chat.service import (
        _iter_custom_attribute_pairs,
        PRODUCT_SEARCH_ATTRIBUTE_CODES,
    )

    brand = ""
    category_name = ""
    text_parts: List[str] = [name]

    for code, value in _iter_custom_attribute_pairs(product):
        if code not in PRODUCT_SEARCH_ATTRIBUTE_CODES:
            continue
        v = re.sub(r"\s+", " ", str(value or "").strip())
        if not v:
            continue
        text_parts.append(v)
        if code in {"brand", "manufacturer"} and not brand:
            brand = v
        if code in {"category_name", "category_ids"} and not category_name:
            category_name = v

    description_text = " ".join(text_parts)[:4000]

    return {
        "id": f"{sku}_{language}",
        "sku": sku,
        "language": language,
        "name": name,
        "price": price,
        "brand": brand,
        "description_text": description_text,
        "category_name": category_name,
        "raw_json": json.dumps(product, ensure_ascii=False),
    }


async def sync_all(force_recreate: bool = False) -> Dict[str, int]:
    """
    Fetch all products from Magento (EN + FR) and index them in Typesense.
    Returns {"indexed": N, "errors": M}.
    """
    from app.typesense_client import (
        drop_collection,
        ensure_collection,
        get_typesense_client,
    )
    from app.config import settings
    from app.chat.service import fetch_magento_products

    client = get_typesense_client()
    if client is None:
        logger.warning("Typesense not configured — set TYPESENSE_HOST and TYPESENSE_API_KEY in .env")
        return {"indexed": 0, "errors": 0, "skipped": True}

    if force_recreate:
        drop_collection()

    if not ensure_collection():
        return {"indexed": 0, "errors": 1}

    collection_name = settings.TYPESENSE_COLLECTION
    total_indexed = 0
    total_errors = 0

    for language in ("en", "fr"):
        logger.info("Fetching %s products from Magento...", language.upper())
        products = await fetch_magento_products(
            search_criteria=None,
            page_size=SYNC_PAGE_SIZE,
            max_pages=SYNC_MAX_PAGES,
            language=language,
        )
        logger.info("  Retrieved %d products from %s store", len(products), language.upper())

        # Build Typesense docs
        docs: List[Dict[str, Any]] = []
        for p in products:
            doc = _build_typesense_doc(p, language)
            if doc:
                docs.append(doc)

        if not docs:
            logger.warning("  No valid documents for %s — skipping", language)
            continue

        # Batch import
        for i in range(0, len(docs), BATCH_SIZE):
            batch = docs[i: i + BATCH_SIZE]
            try:
                results = client.collections[collection_name].documents.import_(
                    batch, {"action": "upsert"}
                )
                for r in results:
                    if isinstance(r, dict):
                        if r.get("success"):
                            total_indexed += 1
                        else:
                            total_errors += 1
                            logger.debug("Index error: %s", r)
                    else:
                        total_indexed += 1
            except Exception as exc:
                logger.error("Typesense batch import error: %s", exc)
                total_errors += len(batch)

        logger.info("  Indexed %d %s products so far", total_indexed, language.upper())

    logger.info("Sync complete — indexed: %d, errors: %d", total_indexed, total_errors)
    return {"indexed": total_indexed, "errors": total_errors}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    recreate = "--recreate" in sys.argv
    result = asyncio.run(sync_all(force_recreate=recreate))
    print(result)
