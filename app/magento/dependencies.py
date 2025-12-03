from __future__ import annotations

from functools import lru_cache

from fastapi import HTTPException, status

from app.config import settings
from app.magento.services import MagentoService


@lru_cache(maxsize=1)
def _service_factory() -> MagentoService:
    if not settings.MAGENTO_BASE_URL or not settings.MAGENTO_ACCESS_TOKEN:
        raise ValueError("Les identifiants Magento sont manquants")

    return MagentoService(
        base_url=settings.MAGENTO_BASE_URL,
        token=settings.MAGENTO_ACCESS_TOKEN,
        timeout=settings.MAGENTO_TIMEOUT,
        store_id=settings.MAGENTO_STORE_ID,
        currency_code=settings.MAGENTO_CURRENCY,
    )


def get_magento_service() -> MagentoService:
    """Dépendance FastAPI pour injecter le service Magento."""
    try:
        return _service_factory()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Les identifiants Magento ne sont pas configurés.",
        ) from exc