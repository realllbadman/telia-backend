import os
import sys
import requests
from pprint import pprint

# Configuration des variables d'environnement
os.environ["MAGENTO_BASE_URL"] = "https://staging-site.glotelho.cm/rest/fr/V1/"
os.environ["MAGENTO_ACCESS_TOKEN"] = "n5bkuy2mfn5exq9bdyoipjuzadliatns"

BASE_URL = os.environ["MAGENTO_BASE_URL"]
TOKEN = os.environ["MAGENTO_ACCESS_TOKEN"]

def get_sample_sku():
    """Récupérer un SKU depuis products-render-info à utiliser pour les tests"""
    url = f"{BASE_URL}products-render-info"
    params = {
        "searchCriteria[pageSize]": 1,
        "searchCriteria[currentPage]": 1,
        "storeId": 1,
        "currencyCode": "XAF"
    }
    headers = {"Authorization": f"Bearer {TOKEN}"}
    try:
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code == 200 and resp.json().get('items'):
            item = resp.json()['items'][0]
            # products-render-info peut ne pas avoir 'sku', vérifions 'url' ou 'id'
            # En fait, le render-info standard N'A PAS de SKU au niveau supérieur,
            # mais vérifions à nouveau la réponse brute ou essayons de deviner/trouver.
            # Attendez, si nous ne pouvons pas obtenir de SKU, nous ne pouvons pas tester /products/:sku.
            # Vérifions si 'sku' est dans les clés de l'élément.
            return item.get('sku')
    except:
        pass
    return None

def test_request(name, url, headers=None):
    print(f"\n--- Test de {name} ---")
    print(f"URL: {url}")
    try:
        response = requests.get(url, headers=headers)
        print(f"Statut: {response.status_code}")
        if response.status_code == 200:
            print("✅ Succès!")
            data = response.json()
            if isinstance(data, dict):
                print(f"Clés: {list(data.keys())}")
                if 'custom_attributes' in data:
                    print(f"Attributs personnalisés trouvés: {len(data['custom_attributes'])}")
                    pprint(data['custom_attributes'])
                if 'extension_attributes' in data:
                    print(f"Attributs d'extension trouvés: {len(data['extension_attributes'])}")
        else:
            print(f"❌ Échec: {response.text[:100]}")
    except Exception as e:
        print(f"Erreur: {e}")

def main():
    # 1. Essayer de trouver un SKU
    print("Récupération d'un produit exemple pour obtenir un SKU...")
    # Nous avons besoin d'un SKU. Si products-render-info ne le donne pas, nous pourrions être bloqués.
    # Essayons de voir si nous pouvons en trouver un.
    # D'après la sortie précédente, nous avons vu 'id', 'name', 'price_info', etc.
    # Nous n'avons pas vu explicitement 'sku'.
    # Essayons de récupérer render-info et d'afficher les clés pour être sûrs.
    
    headers_auth = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }
    
    # Test 1: products-render-info anonyme
    test_request("Anonymous products-render-info", 
                 f"{BASE_URL}products-render-info?searchCriteria[pageSize]=1&storeId=1&currencyCode=XAF")

    # Obtenir un SKU si possible
    sku = None
    try:
        resp = requests.get(f"{BASE_URL}products-render-info?searchCriteria[pageSize]=1&storeId=1&currencyCode=XAF", headers=headers_auth)
        if resp.status_code == 200:
            items = resp.json().get('items', [])
            if items:
                print(f"Clés de l'élément exemple: {list(items[0].keys())}")
                sku = items[0].get('sku')
                if not sku:
                    print("⚠️ Aucun SKU trouvé dans l'élément products-render-info.")
    except:
        pass

    if sku:
        print(f"SKU trouvé: {sku}")
        # Test 2: GET /products/:sku avec Token
        test_request(f"GET /products/{sku} (Auth)", f"{BASE_URL}products/{sku}", headers=headers_auth)
        
        # Test 3: GET /products/:sku Anonyme
        test_request(f"GET /products/{sku} (Anon)", f"{BASE_URL}products/{sku}")
    else:
        print("Tests SKU ignorés (aucun SKU trouvé).")

if __name__ == "__main__":
    main()