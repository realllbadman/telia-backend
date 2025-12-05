"""
Configuration pour le service Magento

Ce module contient les configurations spécifiques au service Magento,
incluant les paramètres de connexion, les timeouts et les options de cache.
"""

from typing import Optional
from pydantic import BaseModel, Field


class MagentoConfig(BaseModel):
    """
    Configuration du service Magento.
    
    Cette classe contient tous les paramètres nécessaires
    pour établir une connexion avec l'API Magento.
    
    Attributes:
        base_url: URL de base de l'API Magento REST
        access_token: Token d'authentification Bearer
        timeout: Timeout des requêtes en secondes
        store_id: ID du store Magento
        currency_code: Code de devise par défaut
        max_retries: Nombre maximum de tentatives
        retry_delay: Délai entre les tentatives en secondes
        verify_ssl: Vérification du certificat SSL
    """
    base_url: str = Field(..., description="URL de base de l'API Magento")
    access_token: str = Field(..., description="Token d'authentification")
    timeout: float = Field(15.0, ge=1.0, le=120.0, description="Timeout en secondes")
    store_id: int = Field(1, ge=1, description="ID du store Magento")
    currency_code: str = Field("XAF", description="Code devise ISO 4217")
    max_retries: int = Field(3, ge=0, le=10, description="Tentatives max")
    retry_delay: float = Field(1.0, ge=0.1, le=10.0, description="Délai entre tentatives")
    verify_ssl: bool = Field(True, description="Vérifier le certificat SSL")
    
    class Config:
        extra = "ignore"


# Configuration par défaut pour Glotelho
DEFAULT_MAGENTO_CONFIG = MagentoConfig(
    base_url="https://staging-site.glotelho.cm/rest/fr/V1/",
    access_token="e9sjymma6rjvvn1fov5sl4ftdhl804iz",
    timeout=15.0,
    store_id=1,
    currency_code="XAF",
    max_retries=3,
    retry_delay=1.0,
    verify_ssl=True
)
