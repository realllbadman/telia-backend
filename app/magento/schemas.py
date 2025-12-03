"""
Schémas Pydantic pour l'intégration Magento 2

Ce module définit les modèles de données pour la communication avec l'API Magento.
Les schémas utilisent Pydantic pour la validation automatique des données et
la désérialisation des réponses JSON de Magento.
"""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict


class MagentoImage(BaseModel):
    """
    Représente une image de produit Magento.
    
    Attributs:
        url: URL complète de l'image sur le serveur Magento
        label: Texte alternatif ou description de l'image (optionnel)
        code: Code de type d'image (ex: 'image', 'small_image', 'thumbnail')
        width: Largeur de l'image en pixels (optionnel)
        height: Hauteur de l'image en pixels (optionnel)
    """
    url: str
    label: Optional[str] = None
    code: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None

    # Ignore les champs supplémentaires non définis dans le schéma
    model_config = ConfigDict(extra="ignore")


class MagentoPriceInfo(BaseModel):
    """
    Contient les informations de prix d'un produit Magento.
    
    Attributs:
        final_price: Prix final après application de toutes les réductions
        regular_price: Prix régulier du produit (prix de base)
        minimal_price: Prix minimal du produit (pour les produits configurables)
        special_price: Prix spécial promotionnel si applicable
        currency_code: Code de devise ISO 4217 (ex: 'XAF', 'EUR', 'USD')
        formatted_final_price: Prix final formaté avec symbole de devise
        formatted_regular_price: Prix régulier formaté avec symbole de devise
    """
    final_price: Optional[float] = None
    regular_price: Optional[float] = None
    minimal_price: Optional[float] = None
    special_price: Optional[float] = None
    currency_code: Optional[str] = None
    formatted_final_price: Optional[str] = None
    formatted_regular_price: Optional[str] = None

    # Ignore les champs supplémentaires non définis dans le schéma
    model_config = ConfigDict(extra="ignore")


class MagentoAttribute(BaseModel):
    """
    Attribut personnalisé d'un produit Magento.
    
    Permet de stocker des caractéristiques produit supplémentaires
    comme la couleur, la taille, la marque, etc.
    
    Attributs:
        code: Identifiant unique de l'attribut (ex: 'color', 'size', 'brand')
        value: Valeur de l'attribut (peut être de tout type: str, int, list, etc.)
    """
    code: str
    value: Any


class MagentoProduct(BaseModel):
    """
    Modèle complet d'un produit Magento.
    
    Représente toutes les informations essentielles d'un produit
    récupéré depuis l'API products-render-info de Magento.
    
    Attributs:
        id: Identifiant unique du produit dans Magento (entity_id)
        name: Nom commercial du produit
        type: Type de produit ('simple', 'configurable', 'bundle', 'virtual', etc.)
        url: URL complète de la page produit sur le storefront (optionnel)
        store_id: Identifiant du store/vue Magento
        currency_code: Code de devise pour ce produit
        is_salable: Indique si le produit est actuellement vendable (en stock)
        price_info: Informations détaillées sur les prix du produit
        images: Liste des images associées au produit
        attributes: Liste des attributs personnalisés du produit
    """
    id: int
    name: str
    type: str
    url: Optional[str] = None
    store_id: int
    currency_code: str
    is_salable: bool
    price_info: MagentoPriceInfo
    images: List[MagentoImage]
    attributes: List[MagentoAttribute] = []


class MagentoProductsResponse(BaseModel):
    """
    Réponse paginée contenant une liste de produits Magento.
    
    Utilisé pour retourner les résultats de recherche de produits
    avec les métadonnées de pagination.
    
    Attributs:
        items: Liste des produits récupérés
        total_count: Nombre total de produits correspondant aux critères (tous pages confondues)
        page: Numéro de la page actuelle (commence à 1)
        page_size: Nombre de produits par page
    """
    items: list[MagentoProduct]
    total_count: int
    page: int
    page_size: int


class MagentoHealthResponse(BaseModel):
    """
    Réponse du contrôle de santé de la connexion Magento.
    
    Utilisé pour vérifier que l'API Magento est accessible et
    fonctionnelle, avec des informations de diagnostic.
    
    Attributs:
        ok: True si la connexion à Magento est fonctionnelle
        store_id: ID du store Magento configuré
        currency_code: Code de devise configuré
        total_products_detected: Nombre total de produits détectés dans le catalogue
        sample_product_id: ID d'un produit exemple utilisé pour le test (optionnel)
    """
    ok: bool
    store_id: int
    currency_code: str
    total_products_detected: int
    sample_product_id: Optional[int] = None
