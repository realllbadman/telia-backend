"""
Module Magento pour la communication avec l'API Magento 2.4.6

Ce module fournit une interface professionnelle et structurée
pour récupérer les informations produits depuis Magento.
"""

from Services.magento.product_service import MagentoProductService
from Services.magento.schemas import (
    ProductInfo,
    ProductCharacteristic,
    ProductPrice,
    ProductImage,
    ProductListResponse,
)
from Services.magento.exceptions import (
    MagentoServiceError,
    MagentoConnectionError,
    MagentoAuthenticationError,
    MagentoProductNotFoundError,
)

__all__ = [
    "MagentoProductService",
    "ProductInfo",
    "ProductCharacteristic",
    "ProductPrice",
    "ProductImage",
    "ProductListResponse",
    "MagentoServiceError",
    "MagentoConnectionError",
    "MagentoAuthenticationError",
    "MagentoProductNotFoundError",
]
