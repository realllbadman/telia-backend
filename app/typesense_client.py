"""Typesense client singleton and collection management."""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Imported lazily so the app starts even if typesense isn't installed yet
_typesense_module = None
_client = None


def _get_module():
    global _typesense_module
    if _typesense_module is None:
        try:
            import typesense as ts
            _typesense_module = ts
        except ImportError:
            logger.warning("typesense package not installed — run: pip install typesense==0.21.0")
    return _typesense_module


COLLECTION_SCHEMA: Dict[str, Any] = {
    "name": "telia_products",
    "fields": [
        {"name": "id",               "type": "string"},
        {"name": "sku",              "type": "string",  "facet": True},
        {"name": "language",         "type": "string",  "facet": True},
        {"name": "name",             "type": "string"},
        {"name": "price",            "type": "float"},
        {"name": "brand",            "type": "string",  "optional": True, "facet": True},
        {"name": "description_text", "type": "string",  "optional": True},
        {"name": "category_name",    "type": "string",  "optional": True, "facet": True},
        # raw_json is stored but NOT indexed — used to reconstruct full Magento product dict
        {"name": "raw_json",         "type": "string",  "index": False},
    ],
    "default_sorting_field": "price",
}


def get_typesense_client():
    """Return a cached Typesense client, or None if not configured/available."""
    global _client
    if _client is not None:
        return _client

    from app.config import settings
    ts = _get_module()
    if ts is None:
        return None

    if not settings.TYPESENSE_HOST or not settings.TYPESENSE_API_KEY:
        return None

    try:
        _client = ts.Client({
            "nodes": [{
                "host": settings.TYPESENSE_HOST,
                "port": str(settings.TYPESENSE_PORT),
                "protocol": settings.TYPESENSE_PROTOCOL,
            }],
            "api_key": settings.TYPESENSE_API_KEY,
            "connection_timeout_seconds": 3,
        })
        logger.info("Typesense client ready at %s:%s", settings.TYPESENSE_HOST, settings.TYPESENSE_PORT)
        return _client
    except Exception as exc:
        logger.warning("Could not create Typesense client: %s", exc)
        return None


def reset_client():
    """Force client re-creation (useful after config changes)."""
    global _client
    _client = None


def ensure_collection() -> bool:
    """Create the Typesense collection if it doesn't exist. Returns True when ready."""
    client = get_typesense_client()
    if client is None:
        return False

    from app.config import settings
    collection_name = settings.TYPESENSE_COLLECTION

    try:
        client.collections[collection_name].retrieve()
        return True
    except Exception:
        pass  # collection doesn't exist yet — create it

    schema = dict(COLLECTION_SCHEMA)
    schema["name"] = collection_name
    try:
        client.collections.create(schema)
        logger.info("Created Typesense collection: %s", collection_name)
        return True
    except Exception as exc:
        logger.error("Failed to create Typesense collection: %s", exc)
        return False


def drop_collection() -> bool:
    """Delete the Typesense collection (for full re-sync)."""
    client = get_typesense_client()
    if client is None:
        return False
    from app.config import settings
    try:
        client.collections[settings.TYPESENSE_COLLECTION].delete()
        logger.info("Deleted Typesense collection: %s", settings.TYPESENSE_COLLECTION)
        return True
    except Exception as exc:
        logger.warning("Could not delete collection: %s", exc)
        return False
