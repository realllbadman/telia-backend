from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import require_superadmin
from app.models import User
from app.magento.dependencies import get_magento_service
from app.magento.schemas import (
    MagentoHealthResponse,
    MagentoProduct,
    MagentoProductsResponse,
)
from app.magento.services import MagentoAPIError, MagentoService

router = APIRouter(prefix="/magento", tags=["Magento"])


@router.get("/health", response_model=MagentoHealthResponse)
def magento_health(
    current_user: User = Depends(require_superadmin),
    service: MagentoService = Depends(get_magento_service),
) -> MagentoHealthResponse:
    """Vérifier la connectivité Magento."""
    try:
        return service.check_health()
    except MagentoAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/products", response_model=MagentoProductsResponse)
def list_magento_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    product_id: int | None = Query(None, description="Filtre exact sur l'identifiant produit"),
    search: str | None = Query(None, description="Filtre partiel sur le nom du produit"),
    min_price: float | None = Query(None, description="Prix minimum"),
    max_price: float | None = Query(None, description="Prix maximum"),
    current_user: User = Depends(require_superadmin),
    service: MagentoService = Depends(get_magento_service),
) -> MagentoProductsResponse:
    """Récupérer les produits depuis Magento."""
    try:
        return service.list_products(
            page=page,
            page_size=page_size,
            product_id=product_id,
            search=search,
            min_price=min_price,
            max_price=max_price,
        )
    except MagentoAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/products/{product_id}", response_model=MagentoProduct)
def get_magento_product(
    product_id: int,
    current_user: User = Depends(require_superadmin),
    service: MagentoService = Depends(get_magento_service),
) -> MagentoProduct:
    """Récupérer un produit Magento unique."""
    try:
        return service.get_product(product_id=product_id)
    except MagentoAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc