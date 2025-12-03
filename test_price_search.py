import os
import sys
from pprint import pprint

# Définir les variables d'env AVANT d'importer app.config
os.environ["SECRET_KEY"] = "temp-secret-key-for-testing"
os.environ["MAGENTO_BASE_URL"] = "https://staging-site.glotelho.cm/rest/fr/V1/"
os.environ["MAGENTO_ACCESS_TOKEN"] = "n5bkuy2mfn5exq9bdyoipjuzadliatns"
os.environ["MAGENTO_TIMEOUT"] = "30"
os.environ["MAGENTO_STORE_ID"] = "1"
os.environ["MAGENTO_CURRENCY"] = "XAF"
os.environ["BACKEND_CORS_ORIGINS"] = '["http://localhost"]'

# Ajouter le répertoire courant au path
sys.path.append(os.getcwd())

from app.config import settings
from app.magento.services import MagentoService

def test_price_search():
    print(f"Test de connexion vers: {settings.MAGENTO_BASE_URL}")
    
    service = MagentoService(
        base_url=settings.MAGENTO_BASE_URL,
        token=settings.MAGENTO_ACCESS_TOKEN,
        timeout=settings.MAGENTO_TIMEOUT,
        store_id=settings.MAGENTO_STORE_ID,
        currency_code=settings.MAGENTO_CURRENCY
    )
    
    try:
        # Test 1: Recherche par plage de prix (60k - 90k)
        print("\n--- Test Plage de Prix (60,000 - 90,000) ---")
        products = service.list_products(
            page=1, 
            page_size=1, 
            min_price=60000, 
            max_price=90000
        )
        print(f"Total Trouvé: {products.total_count}")
        
        # DEBUG: Inspecter les attributs dans la charge utile brute
        params = service._build_search_params(1, 1, None, None, 60000, 90000)
        raw_payload = service._request("GET", "products-render-info", params=params)
        if raw_payload.get("items"):
            item = raw_payload["items"][0]
            print("\n--- INSPECTION DES ATTRIBUTS ---")
            print(f"Clés: {list(item.keys())}")
            print(f"Attributs d'Extension: {item.get('extension_attributes')}")
            print(f"Attributs Personnalisés: {item.get('custom_attributes')}")
        else:
            print("Aucun élément trouvé dans la charge utile brute")

        # Test 2: Prix Exact (ou plage serrée)
        # Note: La correspondance exacte de flottant est délicate, nous essayerons une petite plage ou vérifierons juste les résultats précédents
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_price_search()