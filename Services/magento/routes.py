"""
Routes FastAPI pour le service Magento

Ce module expose les endpoints REST pour accéder aux produits Magento
via le MagentoProductService.

Endpoints disponibles:
- GET /api/v1/products - Liste des produits avec pagination et filtres
- GET /api/v1/products/{id} - Détails d'un produit
- GET /api/v1/products/search - Recherche de produits
- GET /api/v1/products/health - Vérification de la connexion
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from functools import lru_cache

from Services.magento.product_service import MagentoProductService
from Services.magento.schemas import (
    ProductInfo,
    ProductListResponse,
    ProductSearchFilters,
)
from Services.magento.exceptions import (
    MagentoServiceError,
    MagentoConnectionError,
    MagentoAuthenticationError,
    MagentoProductNotFoundError,
)
from Services.magento.config import DEFAULT_MAGENTO_CONFIG, MagentoConfig


# Router FastAPI
router = APIRouter(
    prefix="/api/v1/products",
    tags=["Products - Magento"],
    responses={
        401: {"description": "Non autorisé - Token invalide"},
        502: {"description": "Erreur de connexion Magento"},
        503: {"description": "Service Magento indisponible"},
    }
)


@lru_cache(maxsize=1)
def get_product_service() -> MagentoProductService:
    """
    Dépendance FastAPI pour obtenir une instance singleton du service Magento.
    
    Utilise le caching pour éviter de recréer le service à chaque requête.
    """
    return MagentoProductService(config=DEFAULT_MAGENTO_CONFIG)


def handle_magento_error(exc: Exception) -> HTTPException:
    """
    Convertir une exception Magento en HTTPException.
    
    Args:
        exc: Exception Magento
    
    Returns:
        HTTPException appropriée
    """
    if isinstance(exc, MagentoAuthenticationError):
        return HTTPException(
            status_code=401,
            detail={
                "error": "authentication_failed",
                "message": str(exc),
            }
        )
    elif isinstance(exc, MagentoProductNotFoundError):
        return HTTPException(
            status_code=404,
            detail={
                "error": "product_not_found",
                "message": str(exc),
                "details": exc.details,
            }
        )
    elif isinstance(exc, MagentoConnectionError):
        return HTTPException(
            status_code=503,
            detail={
                "error": "connection_failed",
                "message": str(exc),
            }
        )
    elif isinstance(exc, MagentoServiceError):
        return HTTPException(
            status_code=exc.status_code or 502,
            detail={
                "error": "magento_error",
                "message": str(exc),
                "details": exc.details,
            }
        )
    else:
        return HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Erreur inattendue: {exc}",
            }
        )


@router.get("/", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1, description="Numéro de page"),
    page_size: int = Query(10, ge=1, le=100, description="Produits par page"),
    search: Optional[str] = Query(None, description="Recherche par nom"),
    min_price: Optional[float] = Query(None, ge=0, description="Prix minimum"),
    max_price: Optional[float] = Query(None, ge=0, description="Prix maximum"),
    category_id: Optional[int] = Query(None, description="ID de catégorie"),
    service: MagentoProductService = Depends(get_product_service),
) -> ProductListResponse:
    """
    Récupérer la liste des produits depuis Magento.
    
    Retourne une liste paginée de produits avec leurs informations complètes:
    - Nom et description
    - Prix (régulier, promotionnel, formaté)
    - Images (URL, dimensions)
    - Caractéristiques du produit
    - Lien d'achat
    
    **Paramètres de filtrage:**
    - `search`: Recherche textuelle dans le nom du produit
    - `min_price` / `max_price`: Fourchette de prix
    - `category_id`: Filtrer par catégorie
    
    **Pagination:**
    - `page`: Numéro de page (commence à 1)
    - `page_size`: Nombre de produits par page (max 100)
    """
    try:
        return service.get_products(
            page=page,
            page_size=page_size,
            search=search,
            min_price=min_price,
            max_price=max_price,
            category_id=category_id,
        )
    except MagentoServiceError as exc:
        raise handle_magento_error(exc)


@router.get("/search", response_model=ProductListResponse)
async def search_products(
    q: str = Query(..., min_length=2, description="Terme de recherche"),
    page: int = Query(1, ge=1, description="Numéro de page"),
    page_size: int = Query(10, ge=1, le=100, description="Résultats par page"),
    service: MagentoProductService = Depends(get_product_service),
) -> ProductListResponse:
    """
    Rechercher des produits par nom.
    
    Effectue une recherche textuelle dans les noms de produits.
    La recherche est insensible à la casse et supporte les correspondances partielles.
    
    **Paramètres:**
    - `q`: Terme de recherche (minimum 2 caractères)
    """
    try:
        return service.search_products(
            query=q,
            page=page,
            page_size=page_size,
        )
    except MagentoServiceError as exc:
        raise handle_magento_error(exc)


@router.get("/health")
async def check_health(
    service: MagentoProductService = Depends(get_product_service),
) -> dict:
    """
    Vérifier l'état de la connexion avec Magento.
    
    Retourne les informations de connexion et le nombre total de produits.
    Utile pour le monitoring et les health checks.
    """
    try:
        return service.check_connection()
    except MagentoServiceError as exc:
        raise handle_magento_error(exc)


@router.get("/{product_id}", response_model=ProductInfo)
async def get_product(
    product_id: int,
    service: MagentoProductService = Depends(get_product_service),
) -> ProductInfo:
    """
    Récupérer les détails d'un produit spécifique.
    
    Retourne toutes les informations du produit:
    - Nom, description, SKU
    - Informations de prix complètes
    - Toutes les images du produit
    - Caractéristiques et attributs
    - URL de la page produit et lien d'achat
    
    **Paramètres:**
    - `product_id`: ID unique du produit dans Magento
    """
    try:
        return service.get_product_by_id(product_id)
    except MagentoServiceError as exc:
        raise handle_magento_error(exc)


@router.get("/price-range/")
async def get_by_price_range(
    min_price: float = Query(..., ge=0, description="Prix minimum"),
    max_price: float = Query(..., ge=0, description="Prix maximum"),
    page: int = Query(1, ge=1, description="Numéro de page"),
    page_size: int = Query(10, ge=1, le=100, description="Produits par page"),
    service: MagentoProductService = Depends(get_product_service),
) -> ProductListResponse:
    """
    Récupérer les produits dans une fourchette de prix.
    
    Filtre les produits dont le prix final est compris entre
    `min_price` et `max_price` (inclus).
    """
    try:
        return service.get_products_by_price_range(
            min_price=min_price,
            max_price=max_price,
            page=page,
            page_size=page_size,
        )
    except MagentoServiceError as exc:
        raise handle_magento_error(exc)
