import os
import sys
import requests
from pprint import pprint

# Configuration des variables d'environnement
os.environ["MAGENTO_BASE_URL"] = "https://staging-site.glotelho.cm/rest/fr/V1/"
os.environ["MAGENTO_ACCESS_TOKEN"] = "n5bkuy2mfn5exq9bdyoipjuzadliatns"

BASE_URL = os.environ["MAGENTO_BASE_URL"]
TOKEN = os.environ["MAGENTO_ACCESS_TOKEN"]

def test_endpoint(name, endpoint):
    print(f"\n--- Test de {name} ({endpoint}) ---")
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }
    url = f"{BASE_URL}{endpoint}"
    try:
        response = requests.get(url, headers=headers)
        print(f"Statut: {response.status_code}")
        if response.status_code == 200:
            print("✅ Accessible")
            # Afficher un extrait pour voir ce que nous obtenons
            try:
                data = response.json()
                if isinstance(data, list):
                    print(f"Données (Liste): {len(data)} éléments")
                    if data: pprint(data[0])
                elif isinstance(data, dict):
                    print("Données (Dictionnaire):")
                    pprint(list(data.keys()))
            except:
                print("Impossible d'analyser le JSON")
        else:
            print(f"❌ Interdit/Erreur: {response.text[:100]}")
    except Exception as e:
        print(f"Erreur: {e}")

if __name__ == "__main__":
    test_endpoint("Catégories", "categories")
    test_endpoint("Config Boutiques", "store/storeConfigs")
    test_endpoint("Recherche", "search?searchCriteria[pageSize]=1")
    test_endpoint("Attributs (Couleur)", "products/attributes/color")
    test_endpoint("Jeux d'attributs", "products/attribute-sets/sets/list?searchCriteria[pageSize]=1")