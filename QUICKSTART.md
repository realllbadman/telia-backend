# 🚀 Quick Start Guide

## Installation rapide (5 minutes)

### 1. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 2. Démarrer le serveur
```bash
uvicorn main:app --reload
```

Le serveur démarre sur **http://localhost:8000**

### 3. Tester l'API

#### Option A: Interface web (Swagger UI)
Ouvrez votre navigateur: **http://localhost:8000/docs**

#### Option B: Script de test automatique
```bash
python test_api.py
```

#### Option C: Commandes cURL

**1. Créer un superadmin:**
```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@telia.com",
    "username": "admin",
    "password": "admin123456",
    "full_name": "Super Admin",
    "role": "superadmin"
  }'
```

**2. Se connecter:**
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123456"
  }'
```

Copiez le `access_token` de la réponse.

**3. Accéder à une route protégée:**
```bash
curl -X GET "http://localhost:8000/auth/me" \
  -H "Authorization: Bearer VOTRE_TOKEN_ICI"
```

## 📚 Routes disponibles

### Authentification
- `POST /auth/register` - Créer un compte
- `POST /auth/login` - Se connecter
- `GET /auth/me` - Informations utilisateur actuel
- `GET /auth/users` - Liste utilisateurs (superadmin only)

### Exemples de routes protégées
- `GET /protected` - Accessible par tous les utilisateurs authentifiés
- `GET /admin-only` - Accessible uniquement par superadmin
- `GET /customer-area` - Accessible par customer et superadmin

## 🔑 Rôles disponibles

- **customer** - Utilisateur standard
- **superadmin** - Administrateur avec tous les droits

## 💡 Conseils

1. **Documentation complète**: Voir [README.md](README.md)
2. **Swagger UI**: http://localhost:8000/docs
3. **ReDoc**: http://localhost:8000/redoc
4. **Script de test**: `python test_api.py`

## 🐛 Problèmes courants

**Erreur: Address already in use**
```bash
# Changez le port
uvicorn main:app --reload --port 8001
```

**Erreur: Module not found**
```bash
# Réinstallez les dépendances
pip install -r requirements.txt
```

**Base de données verrouillée**
```bash
# Supprimez la base de données et redémarrez
rm telia.db
python main.py
```
