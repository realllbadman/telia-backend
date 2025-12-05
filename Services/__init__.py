"""
Module Services de Telia Backend

Ce module contient les services métier pour l'intégration avec
des systèmes externes comme Magento 2.4.6.

Services disponibles:
- MagentoProductService: Récupération des produits depuis Magento
"""

from Services.magento.product_service import MagentoProductService
from Services.magento.schemas import (
    ProductInfo,
    ProductCharacteristic,
    ProductPrice,
    ProductImage,
    ProductListResponse,
)

__all__ = [
    "MagentoProductService",
    "ProductInfo",
    "ProductCharacteristic", 
    "ProductPrice",
    "ProductImage",
    "ProductListResponse",
]
