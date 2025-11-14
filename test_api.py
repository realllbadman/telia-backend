"""
Script de test pour l'API d'authentification Telia
Usage: python test_api.py
"""

import requests
import json
from typing import Optional

BASE_URL = "http://localhost:8000"


class TeliaAPIClient:
    """Client pour tester l'API Telia"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.token: Optional[str] = None
    
    def register(self, email: str, username: str, password: str, 
                 full_name: str = None, role: str = "customer"):
        """Inscription d'un nouvel utilisateur"""
        print(f"\n📝 Inscription de l'utilisateur: {username}")
        
        response = requests.post(
            f"{self.base_url}/auth/register",
            json={
                "email": email,
                "username": username,
                "password": password,
                "full_name": full_name,
                "role": role
            }
        )
        
        if response.status_code == 201:
            print(f"✅ Utilisateur créé avec succès!")
            print(f"   ID: {response.json()['id']}")
            print(f"   Role: {response.json()['role']}")
        else:
            print(f"❌ Erreur: {response.json()}")
        
        return response.json()
    
    def login(self, username: str, password: str):
        """Connexion d'un utilisateur"""
        print(f"\n🔐 Connexion de l'utilisateur: {username}")
        
        response = requests.post(
            f"{self.base_url}/auth/login",
            json={
                "username": username,
                "password": password
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            self.token = data["access_token"]
            print(f"✅ Connexion réussie!")
            print(f"   Token: {self.token[:50]}...")
            print(f"   User: {data['user']['username']} ({data['user']['role']})")
        else:
            print(f"❌ Erreur: {response.json()}")
        
        return response.json()
    
    def get_current_user(self):
        """Récupérer les informations de l'utilisateur actuel"""
        print(f"\n👤 Récupération des informations utilisateur")
        
        if not self.token:
            print("❌ Erreur: Aucun token disponible. Connectez-vous d'abord.")
            return None
        
        response = requests.get(
            f"{self.base_url}/auth/me",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        if response.status_code == 200:
            user = response.json()
            print(f"✅ Informations récupérées:")
            print(f"   Username: {user['username']}")
            print(f"   Email: {user['email']}")
            print(f"   Role: {user['role']}")
            print(f"   Active: {user['is_active']}")
        else:
            print(f"❌ Erreur: {response.json()}")
        
        return response.json() if response.status_code == 200 else None
    
    def access_protected_route(self):
        """Tester l'accès à une route protégée"""
        print(f"\n🔒 Accès à une route protégée")
        
        if not self.token:
            print("❌ Erreur: Aucun token disponible. Connectez-vous d'abord.")
            return None
        
        response = requests.get(
            f"{self.base_url}/protected",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Accès autorisé!")
            print(f"   Message: {data['message']}")
        else:
            print(f"❌ Erreur: {response.json()}")
        
        return response.json() if response.status_code == 200 else None
    
    def access_admin_route(self):
        """Tester l'accès à une route admin"""
        print(f"\n👑 Accès à une route admin")
        
        if not self.token:
            print("❌ Erreur: Aucun token disponible. Connectez-vous d'abord.")
            return None
        
        response = requests.get(
            f"{self.base_url}/admin-only",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Accès autorisé (superadmin)!")
            print(f"   Message: {data['message']}")
        elif response.status_code == 403:
            print(f"🚫 Accès refusé: {response.json()['detail']}")
        else:
            print(f"❌ Erreur: {response.json()}")
        
        return response.json() if response.status_code == 200 else None
    
    def list_users(self):
        """Lister tous les utilisateurs (superadmin seulement)"""
        print(f"\n📋 Liste de tous les utilisateurs")
        
        if not self.token:
            print("❌ Erreur: Aucun token disponible. Connectez-vous d'abord.")
            return None
        
        response = requests.get(
            f"{self.base_url}/auth/users",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        if response.status_code == 200:
            users = response.json()
            print(f"✅ {len(users)} utilisateur(s) trouvé(s):")
            for user in users:
                print(f"   - {user['username']} ({user['email']}) - Role: {user['role']}")
        elif response.status_code == 403:
            print(f"🚫 Accès refusé: {response.json()['detail']}")
        else:
            print(f"❌ Erreur: {response.json()}")
        
        return response.json() if response.status_code == 200 else None


def main():
    """Script principal de test"""
    print("=" * 60)
    print("🚀 Test de l'API d'authentification Telia")
    print("=" * 60)
    
    client = TeliaAPIClient()
    
    # Test 1: Inscription d'un client
    print("\n" + "=" * 60)
    print("TEST 1: Inscription d'un utilisateur customer")
    print("=" * 60)
    
    client.register(
        email="customer@telia.com",
        username="customer1",
        password="customer123",
        full_name="Customer Test",
        role="customer"
    )
    
    # Test 2: Connexion du client
    print("\n" + "=" * 60)
    print("TEST 2: Connexion du customer")
    print("=" * 60)
    
    client.login("customer1", "customer123")
    
    # Test 3: Récupérer les infos utilisateur
    print("\n" + "=" * 60)
    print("TEST 3: Récupération des informations utilisateur")
    print("=" * 60)
    
    client.get_current_user()
    
    # Test 4: Accès à une route protégée
    print("\n" + "=" * 60)
    print("TEST 4: Accès à une route protégée")
    print("=" * 60)
    
    client.access_protected_route()
    
    # Test 5: Tentative d'accès admin (devrait échouer)
    print("\n" + "=" * 60)
    print("TEST 5: Tentative d'accès admin (customer)")
    print("=" * 60)
    
    client.access_admin_route()
    
    # Test 6: Inscription d'un superadmin
    print("\n" + "=" * 60)
    print("TEST 6: Inscription d'un superadmin")
    print("=" * 60)
    
    admin_client = TeliaAPIClient()
    admin_client.register(
        email="admin@telia.com",
        username="superadmin",
        password="admin123456",
        full_name="Super Admin",
        role="superadmin"
    )
    
    # Test 7: Connexion du superadmin
    print("\n" + "=" * 60)
    print("TEST 7: Connexion du superadmin")
    print("=" * 60)
    
    admin_client.login("superadmin", "admin123456")
    
    # Test 8: Accès admin avec superadmin
    print("\n" + "=" * 60)
    print("TEST 8: Accès à la route admin (superadmin)")
    print("=" * 60)
    
    admin_client.access_admin_route()
    
    # Test 9: Liste des utilisateurs
    print("\n" + "=" * 60)
    print("TEST 9: Liste de tous les utilisateurs (superadmin)")
    print("=" * 60)
    
    admin_client.list_users()
    
    print("\n" + "=" * 60)
    print("✅ Tous les tests terminés!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("\n❌ Erreur: Impossible de se connecter à l'API.")
        print("   Assurez-vous que le serveur est démarré:")
        print("   uvicorn main:app --reload")
    except Exception as e:
        print(f"\n❌ Erreur inattendue: {e}")
