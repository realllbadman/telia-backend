import os
import sys
import requests
from pprint import pprint

# Configuration des variables d'environnement
os.environ["MAGENTO_BASE_URL"] = "https://staging-site.glotelho.cm/rest/fr/V1/"
os.environ["MAGENTO_ACCESS_TOKEN"] = "n5bkuy2mfn5exq9bdyoipjuzadliatns"

BASE_URL = os.environ["MAGENTO_BASE_URL"]
TOKEN = os.environ["MAGENTO_ACCESS_TOKEN"]

def test_v1_products():
    print(f"Test d'accès V1/products...")
    
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }
    
    # Essayer de récupérer 1 produit
    url = f"{BASE_URL}products"
    params = {
        "searchCriteria[pageSize]": 1,
        "searchCriteria[currentPage]": 1
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        print(f"Code Statut: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("✅ Succès! V1/products est accessible.")
            if data.get('items'):
                item = data['items'][0]
                print("Clés de l'élément exemple:", list(item.keys()))
                print("Attributs Personnalisés:", item.get('custom_attributes'))
        else:
            print(f"❌ Échec: {response.text}")
            
    except Exception as e:
        print(f"Erreur: {e}")

if __name__ == "__main__":
    test_v1_products()