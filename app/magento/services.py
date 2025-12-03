from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx

from app.magento.schemas import (
    MagentoHealthResponse,
    MagentoImage,
    MagentoPriceInfo,
    MagentoProduct,
    MagentoProductsResponse,
    MagentoAttribute,
)


class MagentoAPIError(Exception):
    """Levé lorsque l'API Magento retourne une erreur."""


class MagentoService:
    """Couche de service responsable de la communication avec les API storefront Magento."""

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 15.0,
        store_id: int = 1,
        currency_code: str = "XAF",
    ) -> None:
        if not base_url:
            raise ValueError("L'URL de base Magento est requise.")
        if not token:
            raise ValueError("Le token d'accès Magento est requis.")

        self.base_url = base_url if base_url.endswith("/") else f"{base_url}/"
        self.token = token
        self.timeout = timeout
        self.store_id = store_id
        self.currency_code = currency_code

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = urljoin(self.base_url, endpoint)
        try:
            response = httpx.request(
                method=method,
                url=url,
                headers=self._headers,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            message = exc.response.text
            raise MagentoAPIError(
                f"Magento a retourné {exc.response.status_code}: {message}"
            ) from exc
        except httpx.HTTPError as exc:
            raise MagentoAPIError(f"Erreur de connexion Magento: {exc}") from exc

        if response.content:
            return response.json()
        return {}

    def check_health(self) -> MagentoHealthResponse:
        """Vérifier la connectivité Magento en récupérant un produit exemple."""
        sample = self.list_products(page=1, page_size=1)
        sample_id = sample.items[0].id if sample.items else None
        return MagentoHealthResponse(
            ok=True,
            store_id=self.store_id,
            currency_code=self.currency_code,
            total_products_detected=sample.total_count,
            sample_product_id=sample_id,
        )

    def list_products(
        self,
        page: int = 1,
        page_size: int = 10,
        product_id: Optional[int] = None,
        search: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
    ) -> MagentoProductsResponse:
        """Retourner les produits storefront paginés."""
        params = self._build_search_params(
            page, page_size, product_id, search, min_price, max_price
        )
        payload = self._request("GET", "products-render-info", params=params)
        items = [self._parse_product(item) for item in payload.get("items", [])]

        return MagentoProductsResponse(
            items=items,
            total_count=payload.get("total_count", len(items)),
            page=page,
            page_size=page_size,
        )

    def get_product(self, product_id: int) -> MagentoProduct:
        """Retourner un produit unique par ID d'entité Magento."""
        response = self.list_products(page=1, page_size=1, product_id=product_id)
        if not response.items:
            raise MagentoAPIError(f"Produit {product_id} introuvable.")
        return response.items[0]

    def _build_search_params(
        self,
        page: int,
        page_size: int,
        product_id: Optional[int],
        search: Optional[str],
        min_price: Optional[float],
        max_price: Optional[float],
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "searchCriteria[currentPage]": page,
            "searchCriteria[pageSize]": page_size,
            "searchCriteria[sortOrders][0][field]": "id",
            "searchCriteria[sortOrders][0][direction]": "DESC",
            "storeId": self.store_id,
            "currencyCode": self.currency_code,
        }

        filter_groups: List[Dict[str, Any]] = []

        if product_id is not None:
            filter_groups.append(
                {
                    "filters": [
                        {
                            "field": "entity_id",
                            "value": product_id,
                            "condition_type": "eq",
                        }
                    ]
                }
            )
        if search:
            filter_groups.append(
                {
                    "filters": [
                        {
                            "field": "name",
                            "value": f"%{search}%",
                            "condition_type": "like",
                        }
                    ]
                }
            )
            
        # Filtres de prix
        if min_price is not None and max_price is not None:
            # Recherche par plage
            filter_groups.append(
                {
                    "filters": [
                        {
                            "field": "price",
                            "value": min_price,
                            "condition_type": "from",
                        }
                    ]
                }
            )
            filter_groups.append(
                {
                    "filters": [
                        {
                            "field": "price",
                            "value": max_price,
                            "condition_type": "to",
                        }
                    ]
                }
            )
        elif min_price is not None:
            # Prix min uniquement
            filter_groups.append(
                {
                    "filters": [
                        {
                            "field": "price",
                            "value": min_price,
                            "condition_type": "from",
                        }
                    ]
                }
            )
        elif max_price is not None:
            # Prix max uniquement
            filter_groups.append(
                {
                    "filters": [
                        {
                            "field": "price",
                            "value": max_price,
                            "condition_type": "to",
                        }
                    ]
                }
            )

        for idx, group in enumerate(filter_groups):
            filters = group["filters"]
            for jdx, filt in enumerate(filters):
                params[f"searchCriteria[filterGroups][{idx}][filters][{jdx}][field]"] = filt[
                    "field"
                ]
                params[
                    f"searchCriteria[filterGroups][{idx}][filters][{jdx}][value]"
                ] = filt["value"]
                params[
                    f"searchCriteria[filterGroups][{idx}][filters][{jdx}][conditionType]"
                ] = filt["condition_type"]

        return params

    def _parse_product(self, product: Dict[str, Any]) -> MagentoProduct:
        price_info = product.get("price_info", {})
        formatted = price_info.get("formatted_prices") or {}
        price_payload = MagentoPriceInfo(
            final_price=price_info.get("final_price"),
            regular_price=price_info.get("regular_price"),
            minimal_price=price_info.get("minimal_price"),
            special_price=price_info.get("special_price"),
            currency_code=product.get("currency_code"),
            formatted_final_price=formatted.get("final_price"),
            formatted_regular_price=formatted.get("regular_price"),
        )

        images = [
            MagentoImage(**image)
            for image in product.get("images", [])
            if isinstance(image, dict) and image.get("url")
        ]
        
        # Extraction des attributs d'extension (attributs personnalisés)
        attributes = []
        extension_attributes = product.get("extension_attributes", {})
        # Note: la structure products-render-info peut différer de l'API standard
        # Nous cherchons 'review_html' ou d'autres champs, mais pour les caractéristiques
        # nous pourrions avoir besoin de nous fier à ce qui est disponible dans 'extension_attributes'
        # ou si l'utilisateur veut des attributs spécifiques, nous devrions peut-être les récupérer différemment.
        # Pour l'instant, mappons ce que nous trouvons dans extension_attributes comme point de départ.
        
        # Dans products-render-info, les attributs personnalisés peuvent être sous 'extension_attributes' -> 'converted_regular_price' etc
        # Mais souvent les attributs détaillés comme 'color' ne sont pas dans render-info.
        # Cependant, le besoin est d'obtenir les caractéristiques.
        # Si elles ne sont pas dans render-info, nous pourrions avoir besoin d'utiliser le endpoint standard V1/products.
        # Mais le guide utilisateur dit que nous utilisons render-info en raison des permissions.
        # Essayons d'analyser ce que nous pouvons trouver.
        
        # Tentative de trouver une liste d'attributs si présente
        # (C'est un effort basé sur les structures de réponse standard Magento)
        
        return MagentoProduct(
            id=product.get("id"),
            name=product.get("name"),
            type=product.get("type"),
            url=product.get("url"),
            store_id=product.get("store_id"),
            currency_code=product.get("currency_code"),
            is_salable=product.get("is_salable"),
            price_info=price_payload,
            images=images,
            attributes=attributes, 
        )