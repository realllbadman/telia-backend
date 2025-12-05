"""
Schémas Pydantic pour le service Magento

Ce module définit les modèles de données utilisés pour structurer
les informations produits récupérées depuis Magento 2.4.6.

Ces schémas sont indépendants de la structure interne de Magento
et fournissent une interface propre pour l'application.
"""

from __future__ import annotations

from typing import Any, List, Optional
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl, ConfigDict


class ProductType(str, Enum):
    """Types de produits Magento supportés."""
    SIMPLE = "simple"
    CONFIGURABLE = "configurable"
    BUNDLE = "bundle"
    VIRTUAL = "virtual"
    GROUPED = "grouped"
    DOWNLOADABLE = "downloadable"


class ImageType(str, Enum):
    """Types d'images de produit."""
    BASE = "image"
    SMALL = "small_image"
    THUMBNAIL = "thumbnail"
    SWATCH = "swatch_image"


class ProductCharacteristic(BaseModel):
    """
    Caractéristique d'un produit (attribut personnalisé).
    
    Représente une propriété spécifique du produit comme
    la marque, la couleur, les dimensions, etc.
    
    Attributes:
        code: Identifiant technique de la caractéristique
        label: Libellé lisible de la caractéristique
        value: Valeur de la caractéristique
        value_label: Libellé lisible de la valeur (si applicable)
    """
    code: str = Field(..., description="Code technique de l'attribut")
    label: str = Field(..., description="Libellé lisible")
    value: Any = Field(..., description="Valeur de l'attribut")
    value_label: Optional[str] = Field(None, description="Libellé de la valeur")
    
    model_config = ConfigDict(extra="ignore")


class ProductImage(BaseModel):
    """
    Image associée à un produit.
    
    Attributes:
        url: URL complète de l'image
        label: Texte alternatif de l'image
        type: Type d'image (base, thumbnail, etc.)
        position: Position d'affichage de l'image
        is_main: Indique si c'est l'image principale
        width: Largeur en pixels
        height: Hauteur en pixels
    """
    url: str = Field(..., description="URL de l'image")
    label: Optional[str] = Field(None, description="Texte alternatif")
    type: Optional[str] = Field(None, description="Type d'image")
    position: Optional[int] = Field(None, description="Position d'affichage")
    is_main: bool = Field(False, description="Image principale")
    width: Optional[int] = Field(None, description="Largeur en pixels")
    height: Optional[int] = Field(None, description="Hauteur en pixels")
    
    model_config = ConfigDict(extra="ignore")


class ProductPrice(BaseModel):
    """
    Informations de prix d'un produit.
    
    Attributes:
        amount: Montant du prix final
        regular_amount: Prix régulier (avant réduction)
        special_amount: Prix promotionnel (si applicable)
        currency: Code de devise (XAF, EUR, USD, etc.)
        formatted_price: Prix formaté pour affichage
        formatted_regular_price: Prix régulier formaté
        discount_percentage: Pourcentage de réduction
        has_discount: Indique si un prix spécial est appliqué
    """
    amount: float = Field(..., description="Prix final")
    regular_amount: Optional[float] = Field(None, description="Prix régulier")
    special_amount: Optional[float] = Field(None, description="Prix spécial")
    currency: str = Field("XAF", description="Code devise")
    formatted_price: Optional[str] = Field(None, description="Prix formaté")
    formatted_regular_price: Optional[str] = Field(None, description="Prix régulier formaté")
    discount_percentage: Optional[float] = Field(None, description="Pourcentage de réduction")
    has_discount: bool = Field(False, description="Indique si en promotion")
    
    model_config = ConfigDict(extra="ignore")
    
    @classmethod
    def calculate_discount(cls, regular: float, final: float) -> Optional[float]:
        """Calculer le pourcentage de réduction."""
        if regular and final and regular > final:
            return round(((regular - final) / regular) * 100, 2)
        return None


class ProductInfo(BaseModel):
    """
    Modèle complet d'un produit avec toutes ses informations.
    
    Ce modèle agrège toutes les informations d'un produit Magento:
    identité, prix, images, caractéristiques et liens.
    
    Attributes:
        id: Identifiant unique du produit
        sku: Code SKU du produit
        name: Nom du produit
        description: Description complète
        short_description: Description courte
        product_type: Type de produit Magento
        url: Lien vers la page produit
        buy_url: Lien d'achat direct (ajout au panier)
        is_available: Disponibilité du produit
        is_in_stock: État du stock
        price: Informations de prix
        images: Liste des images
        main_image: Image principale
        characteristics: Liste des caractéristiques
        categories: Catégories du produit
        brand: Marque du produit
        created_at: Date de création
        updated_at: Date de dernière mise à jour
    """
    id: int = Field(..., description="ID unique du produit")
    sku: Optional[str] = Field(None, description="Code SKU")
    name: str = Field(..., description="Nom du produit")
    description: Optional[str] = Field(None, description="Description complète")
    short_description: Optional[str] = Field(None, description="Description courte")
    product_type: str = Field("simple", description="Type de produit")
    
    # URLs
    url: Optional[str] = Field(None, description="URL de la page produit")
    buy_url: Optional[str] = Field(None, description="URL d'achat direct")
    
    # Disponibilité
    is_available: bool = Field(True, description="Produit disponible à la vente")
    is_in_stock: bool = Field(True, description="En stock")
    stock_quantity: Optional[int] = Field(None, description="Quantité en stock")
    
    # Prix
    price: ProductPrice = Field(..., description="Informations de prix")
    
    # Images
    images: List[ProductImage] = Field(default_factory=list, description="Liste des images")
    main_image: Optional[ProductImage] = Field(None, description="Image principale")
    
    # Caractéristiques
    characteristics: List[ProductCharacteristic] = Field(
        default_factory=list, 
        description="Caractéristiques du produit"
    )
    
    # Catégorisation
    categories: List[str] = Field(default_factory=list, description="Catégories")
    brand: Optional[str] = Field(None, description="Marque")
    
    # Métadonnées
    store_id: int = Field(1, description="ID du store")
    created_at: Optional[datetime] = Field(None, description="Date de création")
    updated_at: Optional[datetime] = Field(None, description="Date de mise à jour")
    
    model_config = ConfigDict(extra="ignore")
    
    def get_characteristics_dict(self) -> dict:
        """Retourner les caractéristiques sous forme de dictionnaire."""
        return {char.code: char.value for char in self.characteristics}
    
    def get_image_urls(self) -> List[str]:
        """Retourner la liste des URLs d'images."""
        return [img.url for img in self.images]


class ProductListResponse(BaseModel):
    """
    Réponse paginée contenant une liste de produits.
    
    Attributes:
        items: Liste des produits
        total_count: Nombre total de produits
        page: Numéro de page actuel
        page_size: Taille de la page
        has_next: Indique s'il y a une page suivante
        has_previous: Indique s'il y a une page précédente
        total_pages: Nombre total de pages
    """
    items: List[ProductInfo] = Field(default_factory=list, description="Liste des produits")
    total_count: int = Field(0, description="Nombre total de produits")
    page: int = Field(1, description="Page actuelle")
    page_size: int = Field(10, description="Taille de page")
    has_next: bool = Field(False, description="Page suivante disponible")
    has_previous: bool = Field(False, description="Page précédente disponible")
    total_pages: int = Field(1, description="Nombre total de pages")
    
    model_config = ConfigDict(extra="ignore")
    
    @classmethod
    def calculate_pagination(cls, total_count: int, page: int, page_size: int) -> dict:
        """Calculer les métadonnées de pagination."""
        total_pages = max(1, (total_count + page_size - 1) // page_size)
        return {
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1,
        }


class ProductSearchFilters(BaseModel):
    """
    Filtres de recherche pour les produits.
    
    Attributes:
        search_query: Terme de recherche textuel
        min_price: Prix minimum
        max_price: Prix maximum
        category_id: ID de catégorie
        brand: Filtre par marque
        in_stock_only: Uniquement les produits en stock
        on_sale_only: Uniquement les produits en promotion
    """
    search_query: Optional[str] = Field(None, description="Recherche textuelle")
    min_price: Optional[float] = Field(None, ge=0, description="Prix minimum")
    max_price: Optional[float] = Field(None, ge=0, description="Prix maximum")
    category_id: Optional[int] = Field(None, description="ID de catégorie")
    brand: Optional[str] = Field(None, description="Marque")
    in_stock_only: bool = Field(False, description="Uniquement en stock")
    on_sale_only: bool = Field(False, description="Uniquement en promo")
    
    model_config = ConfigDict(extra="ignore")
