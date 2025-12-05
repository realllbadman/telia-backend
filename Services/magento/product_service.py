"""
Service principal pour la communication avec Magento

Ce module implémente le service de récupération des produits depuis Magento.
Il gère la connexion, l'authentification, le parsing des données et 
la gestion des erreurs de manière professionnelle.

"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin, quote

import httpx

from Services.magento.config import MagentoConfig, DEFAULT_MAGENTO_CONFIG
from Services.magento.exceptions import (
    MagentoServiceError,
    MagentoConnectionError,
    MagentoAuthenticationError,
    MagentoProductNotFoundError,
    MagentoRateLimitError,
    MagentoDataParsingError,
)
from Services.magento.schemas import (
    ProductInfo,
    ProductCharacteristic,
    ProductPrice,
    ProductImage,
    ProductListResponse,
    ProductSearchFilters,
)


# Configuration du logging
logger = logging.getLogger(__name__)


class MagentoProductService:
    """
    Service pour récupérer les informations produits depuis Magento
    
    Ce service fournit une interface propre et professionnelle pour:
    - Lister les produits avec pagination et filtres
    - Récupérer un produit par son ID
    - Rechercher des produits par nom ou caractéristiques
    - Récupérer les images, prix et caractéristiques
    
    Example:
        >>> config = MagentoConfig(
        ...     base_url="https://staging-site.glotelho.cm/rest/fr/V1/",
        ...     access_token="votre_token"
        ... )
        >>> service = MagentoProductService(config)
        >>> products = service.get_products(page=1, page_size=10)
        >>> print(products.total_count)
    
    Attributes:
        config: Configuration du service Magento
        _client: Client HTTP pour les requêtes
    """
    
    def __init__(self, config: Optional[MagentoConfig] = None) -> None:
        """
        Initialiser le service Magento.
        
        Args:
            config: Configuration du service. Utilise la config par défaut si non fourni.
        
        Raises:
            ValueError: Si la configuration est invalide
        """
        self.config = config or DEFAULT_MAGENTO_CONFIG
        
        # Validation de la configuration
        if not self.config.base_url:
            raise ValueError("L'URL de base Magento est requise")
        if not self.config.access_token:
            raise ValueError("Le token d'accès Magento est requis")
        
        # Normaliser l'URL de base
        self._base_url = (
            self.config.base_url 
            if self.config.base_url.endswith("/") 
            else f"{self.config.base_url}/"
        )
        
        # Client HTTP (lazy loading)
        self._client: Optional[httpx.Client] = None
        
        logger.info(f"Service Magento initialisé pour {self._base_url}")
    
    @property
    def _headers(self) -> Dict[str, str]:
        """Headers HTTP pour les requêtes Magento."""
        return {
            "Authorization": f"Bearer {self.config.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    
    def _get_client(self) -> httpx.Client:
        """Obtenir ou créer le client HTTP."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
            )
        return self._client
    
    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Effectuer une requête HTTP vers l'API Magento avec gestion des erreurs.
        
        Args:
            method: Méthode HTTP (GET, POST, etc.)
            endpoint: Endpoint relatif de l'API
            params: Paramètres de requête
            data: Données JSON pour le corps de la requête
        
        Returns:
            Réponse JSON parsée
        
        Raises:
            MagentoConnectionError: Erreur de connexion
            MagentoAuthenticationError: Erreur d'authentification
            MagentoRateLimitError: Limite de requêtes dépassée
            MagentoServiceError: Autres erreurs
        """
        url = urljoin(self._base_url, endpoint)
        client = self._get_client()
        
        last_error: Optional[Exception] = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                logger.debug(f"Requête {method} {url} (tentative {attempt + 1})")
                
                response = client.request(
                    method=method,
                    url=url,
                    headers=self._headers,
                    params=params,
                    json=data,
                )
                
                # Gestion des codes d'erreur HTTP
                if response.status_code == 401:
                    raise MagentoAuthenticationError()
                elif response.status_code == 404:
                    raise MagentoServiceError(
                        f"Ressource non trouvée: {endpoint}",
                        status_code=404
                    )
                elif response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    raise MagentoRateLimitError(
                        retry_after=int(retry_after) if retry_after else None
                    )
                elif response.status_code >= 500:
                    # Erreur serveur - on réessaie
                    if attempt < self.config.max_retries:
                        logger.warning(f"Erreur serveur {response.status_code}, nouvelle tentative...")
                        time.sleep(self.config.retry_delay)
                        continue
                
                response.raise_for_status()
                
                if response.content:
                    return response.json()
                return {}
                
            except httpx.ConnectError as exc:
                last_error = exc
                logger.error(f"Erreur de connexion: {exc}")
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_delay)
                    continue
                raise MagentoConnectionError(
                    f"Impossible de se connecter à {url}: {exc}"
                ) from exc
                
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.error(f"Timeout: {exc}")
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_delay)
                    continue
                raise MagentoConnectionError(
                    f"Timeout lors de la connexion à {url}"
                ) from exc
                
            except (MagentoAuthenticationError, MagentoRateLimitError):
                raise
                
            except httpx.HTTPStatusError as exc:
                error_message = exc.response.text
                logger.error(f"Erreur HTTP {exc.response.status_code}: {error_message}")
                raise MagentoServiceError(
                    f"Erreur Magento: {error_message}",
                    status_code=exc.response.status_code
                ) from exc
                
            except Exception as exc:
                last_error = exc
                logger.error(f"Erreur inattendue: {exc}")
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_delay)
                    continue
                raise MagentoServiceError(f"Erreur inattendue: {exc}") from exc
        
        # Si on arrive ici, toutes les tentatives ont échoué
        raise MagentoConnectionError(
            f"Échec après {self.config.max_retries + 1} tentatives: {last_error}"
        )
    
    def _build_search_params(
        self,
        page: int = 1,
        page_size: int = 10,
        product_id: Optional[int] = None,
        search: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        category_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Construire les paramètres de recherche pour l'API Magento.
        
        Args:
            page: Numéro de page
            page_size: Nombre de produits par page
            product_id: ID de produit spécifique
            search: Terme de recherche
            min_price: Prix minimum
            max_price: Prix maximum
            category_id: ID de catégorie
        
        Returns:
            Dictionnaire de paramètres pour la requête
        """
        params: Dict[str, Any] = {
            "searchCriteria[currentPage]": page,
            "searchCriteria[pageSize]": page_size,
            "searchCriteria[sortOrders][0][field]": "entity_id",
            "searchCriteria[sortOrders][0][direction]": "DESC",
            "storeId": self.config.store_id,
            "currencyCode": self.config.currency_code,
        }
        
        filter_groups: List[Dict[str, Any]] = []
        
        # Filtre par ID produit
        if product_id is not None:
            filter_groups.append({
                "filters": [{
                    "field": "entity_id",
                    "value": product_id,
                    "condition_type": "eq",
                }]
            })
        
        # Filtre par recherche textuelle
        if search:
            filter_groups.append({
                "filters": [{
                    "field": "name",
                    "value": f"%{search}%",
                    "condition_type": "like",
                }]
            })
        
        # Filtres de prix
        if min_price is not None:
            filter_groups.append({
                "filters": [{
                    "field": "price",
                    "value": min_price,
                    "condition_type": "from",
                }]
            })
        
        if max_price is not None:
            filter_groups.append({
                "filters": [{
                    "field": "price",
                    "value": max_price,
                    "condition_type": "to",
                }]
            })
        
        # Filtre par catégorie
        if category_id is not None:
            filter_groups.append({
                "filters": [{
                    "field": "category_id",
                    "value": category_id,
                    "condition_type": "eq",
                }]
            })
        
        # Ajouter les groupes de filtres aux paramètres
        for idx, group in enumerate(filter_groups):
            for jdx, filt in enumerate(group["filters"]):
                prefix = f"searchCriteria[filterGroups][{idx}][filters][{jdx}]"
                params[f"{prefix}[field]"] = filt["field"]
                params[f"{prefix}[value]"] = filt["value"]
                params[f"{prefix}[conditionType]"] = filt["condition_type"]
        
        return params
    
    def _parse_product(self, raw_product: Dict[str, Any]) -> ProductInfo:
        """
        Parser les données brutes d'un produit Magento.
        
        Args:
            raw_product: Données JSON du produit depuis Magento
        
        Returns:
            ProductInfo structuré et validé
        
        Raises:
            MagentoDataParsingError: Si les données sont invalides
        """
        try:
            # Extraction des informations de prix
            price_info = raw_product.get("price_info", {})
            formatted_prices = price_info.get("formatted_prices", {})
            
            final_price = price_info.get("final_price", 0)
            regular_price = price_info.get("regular_price", final_price)
            special_price = price_info.get("special_price")
            
            # Calcul du pourcentage de réduction
            discount_percentage = None
            has_discount = False
            if regular_price and final_price and regular_price > final_price:
                discount_percentage = round(((regular_price - final_price) / regular_price) * 100, 2)
                has_discount = True
            
            price = ProductPrice(
                amount=final_price,
                regular_amount=regular_price,
                special_amount=special_price,
                currency=raw_product.get("currency_code", self.config.currency_code),
                formatted_price=formatted_prices.get("final_price"),
                formatted_regular_price=formatted_prices.get("regular_price"),
                discount_percentage=discount_percentage,
                has_discount=has_discount,
            )
            
            # Extraction des images
            images: List[ProductImage] = []
            for idx, img_data in enumerate(raw_product.get("images", [])):
                if isinstance(img_data, dict) and img_data.get("url"):
                    images.append(ProductImage(
                        url=img_data["url"],
                        label=img_data.get("label"),
                        type=img_data.get("code"),
                        position=idx,
                        is_main=(idx == 0),
                        width=img_data.get("width"),
                        height=img_data.get("height"),
                    ))
            
            # Image principale
            main_image = images[0] if images else None
            
            # Extraction des caractéristiques depuis extension_attributes
            characteristics: List[ProductCharacteristic] = []
            extension_attrs = raw_product.get("extension_attributes", {})
            
            # Parser les attributs courants si disponibles
            common_attrs = ["brand", "color", "size", "material", "weight", "manufacturer"]
            for attr_code in common_attrs:
                if attr_code in extension_attrs:
                    characteristics.append(ProductCharacteristic(
                        code=attr_code,
                        label=attr_code.capitalize(),
                        value=extension_attrs[attr_code],
                    ))
            
            # Construction de l'URL d'achat
            product_url = raw_product.get("url", "")
            # L'URL d'ajout au panier suit généralement ce pattern dans Magento
            buy_url = None
            if product_url:
                # Pattern standard Magento pour ajouter au panier
                buy_url = f"{product_url}?add_to_cart={raw_product.get('id')}"
            
            # Créer l'objet ProductInfo
            return ProductInfo(
                id=raw_product.get("id", 0),
                sku=raw_product.get("sku"),
                name=raw_product.get("name", "Produit sans nom"),
                description=raw_product.get("description"),
                short_description=raw_product.get("short_description"),
                product_type=raw_product.get("type", "simple"),
                url=product_url,
                buy_url=buy_url,
                is_available=raw_product.get("is_salable", True),
                is_in_stock=raw_product.get("is_salable", True),
                price=price,
                images=images,
                main_image=main_image,
                characteristics=characteristics,
                store_id=raw_product.get("store_id", self.config.store_id),
            )
            
        except Exception as exc:
            logger.error(f"Erreur de parsing produit: {exc}")
            raise MagentoDataParsingError(
                f"Impossible de parser les données du produit: {exc}"
            ) from exc
    
    def get_products(
        self,
        page: int = 1,
        page_size: int = 10,
        search: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        category_id: Optional[int] = None,
        filters: Optional[ProductSearchFilters] = None,
    ) -> ProductListResponse:
        """
        Récupérer une liste de produits depuis Magento.
        
        Args:
            page: Numéro de page (commence à 1)
            page_size: Nombre de produits par page (max 100)
            search: Terme de recherche
            min_price: Prix minimum
            max_price: Prix maximum
            category_id: ID de catégorie
            filters: Objet de filtres avancés
        
        Returns:
            ProductListResponse avec les produits et la pagination
        
        Raises:
            MagentoServiceError: En cas d'erreur API
        """
        # Appliquer les filtres si fournis
        if filters:
            search = filters.search_query or search
            min_price = filters.min_price or min_price
            max_price = filters.max_price or max_price
            category_id = filters.category_id or category_id
        
        # Valider les paramètres
        page = max(1, page)
        page_size = min(max(1, page_size), 100)
        
        logger.info(
            f"Récupération des produits - page={page}, size={page_size}, "
            f"search={search}, price=[{min_price}, {max_price}]"
        )
        
        # Construire et exécuter la requête
        params = self._build_search_params(
            page=page,
            page_size=page_size,
            search=search,
            min_price=min_price,
            max_price=max_price,
            category_id=category_id,
        )
        
        response = self._request("GET", "products-render-info", params=params)
        
        # Parser les produits
        items: List[ProductInfo] = []
        for raw_product in response.get("items", []):
            try:
                product = self._parse_product(raw_product)
                items.append(product)
            except MagentoDataParsingError as exc:
                logger.warning(f"Produit ignoré - erreur de parsing: {exc}")
                continue
        
        total_count = response.get("total_count", len(items))
        
        # Calculer la pagination
        pagination = ProductListResponse.calculate_pagination(total_count, page, page_size)
        
        return ProductListResponse(
            items=items,
            total_count=total_count,
            page=page,
            page_size=page_size,
            **pagination,
        )
    
    def get_product_by_id(self, product_id: int) -> ProductInfo:
        """
        Récupérer un produit spécifique par son ID.
        
        Args:
            product_id: ID du produit Magento
        
        Returns:
            ProductInfo du produit demandé
        
        Raises:
            MagentoProductNotFoundError: Si le produit n'existe pas
            MagentoServiceError: En cas d'erreur API
        """
        logger.info(f"Récupération du produit ID={product_id}")
        
        params = self._build_search_params(
            page=1,
            page_size=1,
            product_id=product_id,
        )
        
        response = self._request("GET", "products-render-info", params=params)
        
        items = response.get("items", [])
        if not items:
            raise MagentoProductNotFoundError(product_id)
        
        return self._parse_product(items[0])
    
    def search_products(
        self,
        query: str,
        page: int = 1,
        page_size: int = 10,
    ) -> ProductListResponse:
        """
        Rechercher des produits par terme de recherche.
        
        Args:
            query: Terme de recherche
            page: Numéro de page
            page_size: Nombre de résultats par page
        
        Returns:
            ProductListResponse avec les résultats de recherche
        """
        return self.get_products(
            page=page,
            page_size=page_size,
            search=query,
        )
    
    def get_products_by_price_range(
        self,
        min_price: float,
        max_price: float,
        page: int = 1,
        page_size: int = 10,
    ) -> ProductListResponse:
        """
        Récupérer les produits dans une fourchette de prix.
        
        Args:
            min_price: Prix minimum
            max_price: Prix maximum
            page: Numéro de page
            page_size: Nombre de produits par page
        
        Returns:
            ProductListResponse avec les produits filtrés
        """
        return self.get_products(
            page=page,
            page_size=page_size,
            min_price=min_price,
            max_price=max_price,
        )
    
    def check_connection(self) -> Dict[str, Any]:
        """
        Vérifier la connexion au serveur Magento.
        
        Returns:
            Dictionnaire avec les informations de connexion
        
        Raises:
            MagentoConnectionError: Si la connexion échoue
        """
        try:
            result = self.get_products(page=1, page_size=1)
            return {
                "status": "connected",
                "base_url": self._base_url,
                "store_id": self.config.store_id,
                "currency": self.config.currency_code,
                "total_products": result.total_count,
                "sample_product": result.items[0].name if result.items else None,
            }
        except Exception as exc:
            raise MagentoConnectionError(
                f"Impossible de vérifier la connexion: {exc}"
            ) from exc
    
    def close(self) -> None:
        """Fermer le client HTTP."""
        if self._client and not self._client.is_closed:
            self._client.close()
            logger.info("Client HTTP fermé")
    
    def __enter__(self) -> "MagentoProductService":
        """Support du context manager."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Fermer le client à la sortie du context."""
        self.close()
