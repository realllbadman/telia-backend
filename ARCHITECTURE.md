# 📁 Structure du Projet

```
telia-backend/
│
├── 📄 main.py                      # Point d'entrée FastAPI
├── 📄 requirements.txt             # Dépendances Python
├── 📄 requirements-dev.txt         # Dépendances de développement
├── 📄 test_api.py                  # Script de test automatique
├── 📄 .env.example                 # Configuration exemple
├── 📄 .gitignore                   # Fichiers à ignorer par Git
├── 📖 README.md                    # Documentation complète
├── 📖 QUICKSTART.md                # Guide de démarrage rapide
├── 📖 ARCHITECTURE.md              # Ce fichier
│
└── 📁 app/                         # Package principal
    ├── 📄 __init__.py
    ├── 📄 config.py                # Configuration (JWT, DB, etc.)
    ├── 📄 database.py              # Configuration SQLAlchemy
    ├── 📄 models.py                # Modèles de base de données
    ├── 📄 schemas.py               # Schémas Pydantic (validation)
    │
    └── 📁 auth/                    # Module d'authentification
        ├── 📄 __init__.py
        ├── 📄 utils.py             # Fonctions utilitaires (JWT, hash)
        ├── 📄 dependencies.py      # Dépendances FastAPI (auth)
        └── 📄 routes.py            # Routes d'authentification
```

## 🏗️ Architecture

### Couches de l'application

```
┌─────────────────────────────────────────────────┐
│            Client (HTTP Requests)               │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│              FastAPI Routes                     │
│         (main.py, auth/routes.py)               │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│         Authentication Middleware               │
│          (auth/dependencies.py)                 │
│    - JWT Token Validation                       │
│    - Role-Based Access Control                  │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│          Business Logic Layer                   │
│         (Pydantic Validation)                   │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│         Database Layer (ORM)                    │
│           (SQLAlchemy)                          │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│           Database (SQLite/PostgreSQL)          │
└─────────────────────────────────────────────────┘
```

## 🔐 Flux d'authentification

### 1. Inscription (Register)

```
Client → POST /auth/register
         ├─ Validation email/username
         ├─ Hash password (bcrypt)
         ├─ Create user in DB
         └─ Return user info
```

### 2. Connexion (Login)

```
Client → POST /auth/login
         ├─ Find user by username/email
         ├─ Verify password
         ├─ Generate JWT token
         └─ Return token + user info
```

### 3. Accès route protégée

```
Client → GET /protected
    Header: Authorization: Bearer <token>
         ├─ Extract token from header
         ├─ Decode & verify JWT
         ├─ Get user from DB
         ├─ Check role permissions
         └─ Execute route logic
```

## 🔑 Composants clés

### 1. Configuration (`app/config.py`)
- Gère les variables d'environnement
- Paramètres JWT (secret, expiration)
- Configuration base de données

### 2. Database (`app/database.py`)
- Moteur SQLAlchemy
- Session factory
- Dependency injection pour les routes

### 3. Models (`app/models.py`)
- **User**: Table utilisateurs avec rôles
- **UserRole**: Enum des rôles (superadmin, customer)

### 4. Schemas (`app/schemas.py`)
- **UserCreate**: Validation inscription
- **LoginRequest**: Validation connexion
- **UserResponse**: Format de réponse
- **Token**: Structure JWT token

### 5. Auth Utils (`app/auth/utils.py`)
- `get_password_hash()`: Hash bcrypt
- `verify_password()`: Vérification mot de passe
- `create_access_token()`: Génération JWT
- `decode_access_token()`: Décodage JWT

### 6. Auth Dependencies (`app/auth/dependencies.py`)
- `get_current_user()`: Récupère l'utilisateur actuel
- `require_role()`: Factory pour vérifier les rôles
- `require_superadmin`: Dépendance superadmin
- `require_customer`: Dépendance customer

### 7. Auth Routes (`app/auth/routes.py`)
- `POST /auth/register`: Inscription
- `POST /auth/login`: Connexion
- `GET /auth/me`: Info utilisateur actuel
- `GET /auth/users`: Liste utilisateurs (admin)

## 🛡️ Sécurité

### Mesures implémentées

1. **Passwords**: Hashés avec bcrypt (coût: 12 rounds)
2. **JWT**: Tokens signés avec HS256
3. **Token Expiration**: 30 minutes (configurable)
4. **Role-Based Access Control**: Permissions par rôle
5. **Input Validation**: Pydantic schemas
6. **SQL Injection**: Protection par ORM
7. **CORS**: Configurable pour production

### Recommandations production

```python
# .env production
SECRET_KEY=<générer-avec-secrets.token_urlsafe(32)>
DATABASE_URL=postgresql://...
ACCESS_TOKEN_EXPIRE_MINUTES=15

# main.py - CORS
allow_origins=["https://votredomaine.com"]
```

## 🔄 Workflow de développement

### Ajouter une nouvelle route protégée

```python
from fastapi import APIRouter, Depends
from app.auth.dependencies import get_current_user
from app.models import User

router = APIRouter()

@router.get("/my-route")
def my_protected_route(current_user: User = Depends(get_current_user)):
    return {"message": f"Hello {current_user.username}"}
```

### Ajouter un nouveau rôle

1. Modifier `app/models.py`:
```python
class UserRole(str, enum.Enum):
    SUPERADMIN = "superadmin"
    CUSTOMER = "customer"
    MANAGER = "manager"  # Nouveau rôle
```

2. Créer la dépendance dans `app/auth/dependencies.py`:
```python
require_manager = require_role([UserRole.MANAGER, UserRole.SUPERADMIN])
```

3. Utiliser dans les routes:
```python
@router.get("/manager-dashboard")
def manager_area(current_user: User = Depends(require_manager)):
    return {"access": "manager"}
```

## 📊 Schéma de la base de données

### Table: users

| Colonne          | Type      | Description                    |
|------------------|-----------|--------------------------------|
| id               | Integer   | Clé primaire                   |
| email            | String    | Email unique                   |
| username         | String    | Username unique                |
| hashed_password  | String    | Mot de passe hashé (bcrypt)    |
| full_name        | String    | Nom complet (optionnel)        |
| role             | Enum      | superadmin ou customer         |
| is_active        | Boolean   | Compte actif (défaut: true)    |
| created_at       | DateTime  | Date de création               |
| updated_at       | DateTime  | Date de mise à jour            |

## 🔧 Extension et personnalisation

### Ajouter d'autres tables

```python
# app/models.py
class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"))
    
    # Relation
    owner = relationship("User", back_populates="products")

# Ajouter dans User
User.products = relationship("Product", back_populates="owner")
```

### Changer de base de données

**PostgreSQL:**
```bash
pip install psycopg2-binary
```

```env
DATABASE_URL=postgresql://user:password@localhost/telia
```

**MySQL:**
```bash
pip install pymysql
```

```env
DATABASE_URL=mysql+pymysql://user:password@localhost/telia
```

## 🎯 Bonnes pratiques

1. **Toujours hasher les mots de passe** - Ne jamais stocker en clair
2. **Valider les entrées** - Utiliser les schémas Pydantic
3. **Gérer les erreurs** - HTTPException avec messages clairs
4. **Logger les actions** - Ajouter des logs pour debugging
5. **Tester** - Écrire des tests unitaires et d'intégration
6. **Documenter** - Garder les docstrings à jour
7. **Versionner** - Utiliser Git pour le contrôle de version

## 📚 Ressources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [JWT.io](https://jwt.io/)
- [Passlib Documentation](https://passlib.readthedocs.io/)
