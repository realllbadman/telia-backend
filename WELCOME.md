# 🎉 Bienvenue dans Telia Backend

## ✅ Votre API d'authentification JWT est prête !

Ce projet implémente un système complet d'authentification avec gestion des rôles (superadmin, customer).

---

## 🚀 Démarrage en 3 étapes

### 1. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 2. Lancer le serveur
```bash
uvicorn main:app --reload
```

### 3. Accéder à la documentation
Ouvrez votre navigateur: **http://localhost:8000/docs**

---

## 📚 Documentation disponible

| Fichier | Description |
|---------|-------------|
| **README.md** | Documentation complète et détaillée |
| **QUICKSTART.md** | Guide de démarrage rapide (5 min) |
| **ARCHITECTURE.md** | Architecture et design patterns |
| **COMMANDS.md** | Toutes les commandes utiles |
| **PROJECT_SUMMARY.md** | Résumé du projet |
| **PROJECT_STRUCTURE.md** | Structure des fichiers |

---

## 🎯 Premiers pas recommandés

### Option A: Script automatique (le plus simple)
```bash
chmod +x start.sh
./start.sh
```

### Option B: Manuel étape par étape
```bash
# 1. Installer
pip install -r requirements.txt

# 2. Créer un superadmin
python create_superadmin.py

# 3. Démarrer
uvicorn main:app --reload

# 4. Tester
python test_api.py
```

---

## 🔐 Fonctionnalités principales

### ✅ Authentification
- **Inscription** - Créer un compte utilisateur
- **Connexion** - Obtenir un JWT token
- **Protection** - Sécuriser vos routes

### ✅ Gestion des rôles
- **Superadmin** - Accès complet
- **Customer** - Utilisateur standard
- **Extensible** - Ajouter facilement de nouveaux rôles

### ✅ Sécurité
- **Mots de passe** - Hashés avec bcrypt
- **JWT tokens** - Signés et avec expiration
- **Validation** - Données validées avec Pydantic

---

## 🌐 Endpoints disponibles

### Authentification
- `POST /auth/register` - Créer un compte
- `POST /auth/login` - Se connecter
- `GET /auth/me` - Info utilisateur actuel
- `GET /auth/users` - Liste utilisateurs (admin only)

### Exemples
- `GET /protected` - Route authentifiée
- `GET /admin-only` - Route superadmin
- `GET /customer-area` - Route customer/admin

---

## 📖 Exemples d'utilisation

### Python
```python
import requests

# Inscription
response = requests.post("http://localhost:8000/auth/register", json={
    "email": "user@example.com",
    "username": "user123",
    "password": "password123",
    "role": "customer"
})

# Connexion
response = requests.post("http://localhost:8000/auth/login", json={
    "username": "user123",
    "password": "password123"
})
token = response.json()["access_token"]

# Route protégée
response = requests.get("http://localhost:8000/auth/me",
    headers={"Authorization": f"Bearer {token}"})
```

### cURL
```bash
# Inscription
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "username": "user123", 
       "password": "password123", "role": "customer"}'

# Connexion
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "user123", "password": "password123"}'
```

---

## 🛠️ Structure du projet

```
telia-backend/
├── main.py                     # App FastAPI
├── app/
│   ├── config.py               # Configuration
│   ├── database.py             # SQLAlchemy
│   ├── models.py               # Models (User, UserRole)
│   ├── schemas.py              # Pydantic schemas
│   └── auth/
│       ├── utils.py            # JWT, hashage
│       ├── dependencies.py     # Auth dependencies
│       └── routes.py           # Routes auth
├── test_api.py                 # Tests automatiques
├── create_superadmin.py        # Utilitaire admin
└── start.sh                    # Script démarrage
```

---

## 🔧 Configuration

### Variables d'environnement (.env)
```bash
# Copier le fichier exemple
cp .env.example .env

# Générer une clé secrète
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Modifier .env avec votre clé
SECRET_KEY=votre_cle_secrete_ici
```

---

## 🧪 Tests

### Script de test automatique
```bash
python test_api.py
```

### Test manuel (Swagger UI)
1. Aller sur http://localhost:8000/docs
2. Cliquer sur "Try it out"
3. Tester les endpoints

---

## 📊 Technologies

- **FastAPI** - Framework web moderne
- **SQLAlchemy** - ORM base de données
- **Pydantic** - Validation données
- **JWT** - Authentification par tokens
- **Bcrypt** - Hashage mots de passe

---

## 💡 Astuces

### Créer votre premier superadmin
```bash
python create_superadmin.py
```

### Accéder à la documentation interactive
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Changer le port
```bash
uvicorn main:app --reload --port 8001
```

### Réinitialiser la base de données
```bash
rm telia.db
python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine)"
```

---

## 🚀 Production

### PostgreSQL
```bash
# Installer le driver
pip install psycopg2-binary

# Modifier .env
DATABASE_URL=postgresql://user:password@localhost/telia

# Lancer
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Docker
```bash
docker build -t telia-backend .
docker run -p 8000:8000 telia-backend
```

---

## 🆘 Aide

### Problèmes courants

**Port déjà utilisé**
```bash
uvicorn main:app --reload --port 8001
```

**Module non trouvé**
```bash
pip install -r requirements.txt
```

**Base de données verrouillée**
```bash
rm telia.db
```

### Documentation

Pour plus d'informations, consultez:
- **README.md** - Documentation complète
- **ARCHITECTURE.md** - Architecture détaillée
- **COMMANDS.md** - Toutes les commandes

---

## ✨ Prochaines étapes

1. **Tester l'API** avec `python test_api.py`
2. **Créer un superadmin** avec `python create_superadmin.py`
3. **Explorer la doc** sur http://localhost:8000/docs
4. **Ajouter vos routes** dans `main.py`
5. **Déployer en production** avec PostgreSQL

---

## 🎉 Félicitations !

Votre API d'authentification JWT est prête à l'emploi !

**Bon développement ! 🚀**
