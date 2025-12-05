"""
Script de test pour le service Magento

Ce script permet de tester le MagentoProductService de manière
interactive et de vérifier son bon fonctionnement.

Usage:
    python -m Services.test_magento_service
    
    ou depuis le répertoire racine:
    python Services/test_magento_service.py
"""

import sys
import json
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from Services.magento import (
    MagentoProductService,
    MagentoServiceError,
    MagentoConnectionError,
)
from Services.magento.config import DEFAULT_MAGENTO_CONFIG


def print_separator(title: str = "") -> None:
    """Afficher un séparateur visuel."""
    print("\n" + "=" * 60)
    if title:
        print(f"  {title}")
        print("=" * 60)


def print_product(product, index: int = None) -> None:
    """Afficher les informations d'un produit de manière formatée."""
    prefix = f"[{index}] " if index is not None else ""
    print(f"\n{prefix}📦 {product.name}")
    print(f"   ID: {product.id}")
    print(f"   Type: {product.product_type}")
    print(f"   Prix: {product.price.formatted_price or f'{product.price.amount} {product.price.currency}'}")
    
    if product.price.has_discount:
        print(f"   🏷️  Promo: -{product.price.discount_percentage}% (était {product.price.formatted_regular_price})")
    
    if product.url:
        print(f"   🔗 URL: {product.url}")
    
    if product.images:
        print(f"   🖼️  Images: {len(product.images)} image(s)")
        for img in product.images[:3]:  # Max 3 images affichées
            print(f"      - {img.url}")
    
    if product.characteristics:
        print(f"   📋 Caractéristiques:")
        for char in product.characteristics:
            print(f"      - {char.label}: {char.value}")
    
    print(f"   Disponible: {'✅ Oui' if product.is_available else '❌ Non'}")


def test_connection(service: MagentoProductService) -> bool:
    """Tester la connexion à Magento."""
    print_separator("TEST DE CONNEXION")
    
    try:
        status = service.check_connection()
        print("✅ Connexion réussie!")
        print(f"   URL: {status['base_url']}")
        print(f"   Store ID: {status['store_id']}")
        print(f"   Devise: {status['currency']}")
        print(f"   Nombre total de produits: {status['total_products']}")
        if status.get('sample_product'):
            print(f"   Exemple de produit: {status['sample_product']}")
        return True
    except MagentoConnectionError as e:
        print(f"❌ Erreur de connexion: {e}")
        return False
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
        return False


def test_list_products(service: MagentoProductService) -> bool:
    """Tester la récupération de la liste des produits."""
    print_separator("LISTE DES PRODUITS (page 1, 5 produits)")
    
    try:
        response = service.get_products(page=1, page_size=5)
        
        print(f"📊 Total: {response.total_count} produits")
        print(f"📄 Page {response.page}/{response.total_pages}")
        print(f"⏭️  Page suivante: {'Oui' if response.has_next else 'Non'}")
        
        for i, product in enumerate(response.items, 1):
            print_product(product, i)
        
        return True
    except MagentoServiceError as e:
        print(f"❌ Erreur: {e}")
        return False


def test_search_products(service: MagentoProductService, query: str = "Samsung") -> bool:
    """Tester la recherche de produits."""
    print_separator(f"RECHERCHE: '{query}'")
    
    try:
        response = service.search_products(query=query, page=1, page_size=5)
        
        print(f"🔍 Résultats trouvés: {response.total_count}")
        
        if response.items:
            for i, product in enumerate(response.items, 1):
                print_product(product, i)
        else:
            print("   Aucun produit trouvé pour cette recherche.")
        
        return True
    except MagentoServiceError as e:
        print(f"❌ Erreur: {e}")
        return False


def test_get_product_by_id(service: MagentoProductService, product_id: int) -> bool:
    """Tester la récupération d'un produit par ID."""
    print_separator(f"PRODUIT ID: {product_id}")
    
    try:
        product = service.get_product_by_id(product_id)
        print_product(product)
        return True
    except MagentoServiceError as e:
        print(f"❌ Erreur: {e}")
        return False


def test_price_range(service: MagentoProductService, min_price: float = 10000, max_price: float = 50000) -> bool:
    """Tester le filtrage par fourchette de prix."""
    print_separator(f"PRODUITS ENTRE {min_price} ET {max_price} XAF")
    
    try:
        response = service.get_products_by_price_range(
            min_price=min_price,
            max_price=max_price,
            page=1,
            page_size=5
        )
        
        print(f"💰 Produits dans cette gamme: {response.total_count}")
        
        for i, product in enumerate(response.items, 1):
            print_product(product, i)
        
        return True
    except MagentoServiceError as e:
        print(f"❌ Erreur: {e}")
        return False


def export_to_json(service: MagentoProductService, filename: str = "products_export.json") -> bool:
    """Exporter les produits vers un fichier JSON."""
    print_separator(f"EXPORT JSON: {filename}")
    
    try:
        response = service.get_products(page=1, page_size=20)
        
        # Convertir en dictionnaire
        export_data = {
            "total_count": response.total_count,
            "exported_count": len(response.items),
            "products": [
                {
                    "id": p.id,
                    "name": p.name,
                    "price": {
                        "amount": p.price.amount,
                        "regular_amount": p.price.regular_amount,
                        "currency": p.price.currency,
                        "formatted": p.price.formatted_price,
                        "has_discount": p.price.has_discount,
                        "discount_percentage": p.price.discount_percentage,
                    },
                    "url": p.url,
                    "buy_url": p.buy_url,
                    "images": [img.url for img in p.images],
                    "characteristics": {c.code: c.value for c in p.characteristics},
                    "is_available": p.is_available,
                }
                for p in response.items
            ]
        }
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ {len(response.items)} produits exportés vers {filename}")
        return True
    except Exception as e:
        print(f"❌ Erreur d'export: {e}")
        return False


def main():
    """Exécuter tous les tests."""
    print("\n" + "🚀 " * 20)
    print("   TEST DU SERVICE MAGENTO - GLOTELHO")
    print("🚀 " * 20)
    
    print(f"\n📌 Configuration:")
    print(f"   URL: {DEFAULT_MAGENTO_CONFIG.base_url}")
    print(f"   Store ID: {DEFAULT_MAGENTO_CONFIG.store_id}")
    print(f"   Devise: {DEFAULT_MAGENTO_CONFIG.currency_code}")
    
    # Créer le service
    service = MagentoProductService()
    
    # Exécuter les tests
    results = {}
    
    # Test 1: Connexion
    results["connection"] = test_connection(service)
    
    if not results["connection"]:
        print("\n❌ La connexion a échoué. Arrêt des tests.")
        return
    
    # Test 2: Liste des produits
    results["list"] = test_list_products(service)
    
    # Test 3: Recherche
    results["search"] = test_search_products(service, "téléphone")
    
    # Test 4: Recherche alternative
    results["search2"] = test_search_products(service, "Samsung")
    
    # Test 5: Fourchette de prix
    results["price_range"] = test_price_range(service, 5000, 100000)
    
    # Test 6: Export JSON
    results["export"] = export_to_json(service, "products_export.json")
    
    # Résumé
    print_separator("RÉSUMÉ DES TESTS")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, success in results.items():
        status = "✅" if success else "❌"
        print(f"   {status} {test_name}")
    
    print(f"\n   📊 Résultat: {passed}/{total} tests passés")
    
    # Fermer le service proprement
    service.close()
    
    print("\n✨ Tests terminés!")


if __name__ == "__main__":
    main()
