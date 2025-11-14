# Telia Backend - JWT Authentication API

API Backend avec authentification JWT et gestion des rôles (superadmin, customer).

## 🚀 Installation

### 1. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 2. Configuration

Créer un fichier `.env` à partir de `.env.example`:

```bash
cp .env.example .env
```

**Important**: Changez le `SECRET_KEY` en production avec une clé sécurisée!

```bash
# Générer une clé sécurisée (Python)
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Lancer l'application

```bash
# Mode développement avec auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Ou directement avec Python
python main.py
```

L'API sera accessible sur: `http://localhost:8000`

Documentation interactive: `http://localhost:8000/docs`

## 📋 Architecture

```
telia-backend/
├── main.py                 # Point d'entrée de l'application
├── requirements.txt        # Dépendances Python
├── .env.example           # Configuration exemple
├── app/
│   ├── config.py          # Configuration de l'application
│   ├── database.py        # Configuration base de données
│   ├── models.py          # Modèles SQLAlchemy
│   ├── schemas.py         # Schémas Pydantic
│   └── auth/
│       ├── utils.py       # Fonctions JWT et hashage
│       ├── dependencies.py # Dépendances FastAPI
│       └── routes.py      # Routes d'authentification
```

## 🔐 API Endpoints

### Authentication

#### 1. Register (Inscription)

```http
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "username": "johndoe",
  "password": "securepassword123",
  "full_name": "John Doe",
  "role": "customer"  // "customer" ou "superadmin"
}
```

**Response:**
```json
{
  "id": 1,
  "email": "user@example.com",
  "username": "johndoe",
  "full_name": "John Doe",
  "role": "customer",
  "is_active": true,
  "created_at": "2025-11-13T22:52:31.000Z"
}
```

#### 2. Login (Connexion)

```http
POST /auth/login
Content-Type: application/json

{
  "username": "johndoe",  // ou email
  "password": "securepassword123"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "username": "johndoe",
    "full_name": "John Doe",
    "role": "customer",
    "is_active": true,
    "created_at": "2025-11-13T22:52:31.000Z"
  }
}
```

#### 3. Get Current User

```http
GET /auth/me
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response:**
```json
{
  "id": 1,
  "email": "user@example.com",
  "username": "johndoe",
  "full_name": "John Doe",
  "role": "customer",
  "is_active": true,
  "created_at": "2025-11-13T22:52:31.000Z"
}
```

#### 4. List All Users (Superadmin only)

```http
GET /auth/users?skip=0&limit=100
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Protected Routes (Examples)

#### 5. Protected Route (Authentification requise)

```http
GET /protected
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### 6. Admin Only (Superadmin uniquement)

```http
GET /admin-only
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### 7. Customer Area (Customer ou Superadmin)

```http
GET /customer-area
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## 👥 Gestion des Rôles

### Rôles disponibles:

- **customer**: Utilisateur standard
- **superadmin**: Administrateur avec tous les privilèges

### Comment utiliser les rôles dans vos routes:

```python
from fastapi import APIRouter, Depends
from app.auth.dependencies import (
    get_current_user,      # N'importe quel utilisateur authentifié
    require_superadmin,    # Uniquement superadmin
    require_customer       # Customer ou superadmin
)
from app.models import User

router = APIRouter()

# Route accessible par tous les utilisateurs authentifiés
@router.get("/profile")
def get_profile(current_user: User = Depends(get_current_user)):
    return {"user": current_user.username}

# Route uniquement pour superadmin
@router.delete("/users/{user_id}")
def delete_user(user_id: int, current_user: User = Depends(require_superadmin)):
    # Seuls les superadmins peuvent supprimer
    pass

# Route pour customers et superadmins
@router.get("/products")
def list_products(current_user: User = Depends(require_customer)):
    # Accessible par customers et superadmins
    pass

# Rôle personnalisé
from app.auth.dependencies import require_role
from app.models import UserRole

require_custom = require_role([UserRole.CUSTOMER, UserRole.SUPERADMIN])

@router.get("/custom")
def custom_route(current_user: User = Depends(require_custom)):
    pass
```

## 🔒 Sécurité

### Bonnes pratiques implémentées:

1. **Hashage des mots de passe**: Utilisation de bcrypt
2. **JWT tokens**: Tokens signés avec secret key
3. **Token expiration**: Tokens expirent après 30 minutes (configurable)
4. **Protection CORS**: Configurable pour la production
5. **Validation des données**: Pydantic schemas
6. **Rôles et permissions**: Système de contrôle d'accès basé sur les rôles

### Pour la production:

1. Changez `SECRET_KEY` dans `.env`
2. Configurez `DATABASE_URL` pour PostgreSQL/MySQL
3. Limitez `allow_origins` dans le middleware CORS
4. Activez HTTPS
5. Ajoutez rate limiting
6. Configurez les logs

## 📝 Exemples d'utilisation

### Python (requests)

```python
import requests

BASE_URL = "http://localhost:8000"

# 1. Register
response = requests.post(f"{BASE_URL}/auth/register", json={
    "email": "admin@example.com",
    "username": "admin",
    "password": "admin123456",
    "full_name": "Administrator",
    "role": "superadmin"
})
print(response.json())

# 2. Login
response = requests.post(f"{BASE_URL}/auth/login", json={
    "username": "admin",
    "password": "admin123456"
})
token_data = response.json()
access_token = token_data["access_token"]

# 3. Access protected route
headers = {"Authorization": f"Bearer {access_token}"}
response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
print(response.json())
```

### JavaScript (fetch)

```javascript
const BASE_URL = "http://localhost:8000";

// 1. Register
const registerResponse = await fetch(`${BASE_URL}/auth/register`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    email: "user@example.com",
    username: "user123",
    password: "password123",
    full_name: "User Name",
    role: "customer"
  })
});
const userData = await registerResponse.json();

// 2. Login
const loginResponse = await fetch(`${BASE_URL}/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    username: "user123",
    password: "password123"
  })
});
const { access_token } = await loginResponse.json();

// 3. Access protected route
const protectedResponse = await fetch(`${BASE_URL}/protected`, {
  headers: { "Authorization": `Bearer ${access_token}` }
});
const data = await protectedResponse.json();
```

### cURL

```bash
# 1. Register
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "username": "testuser",
    "password": "testpass123",
    "role": "customer"
  }'

# 2. Login
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "testpass123"
  }'

# 3. Access protected route (remplacez YOUR_TOKEN)
curl -X GET "http://localhost:8000/auth/me" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 🗄️ Base de données

Par défaut, SQLite est utilisé pour le développement. Le fichier `telia.db` sera créé automatiquement.

### Migration vers PostgreSQL/MySQL:

1. Installez le driver approprié:
   ```bash
   # PostgreSQL
   pip install psycopg2-binary
   
   # MySQL
   pip install pymysql
   ```

2. Modifiez `DATABASE_URL` dans `.env`:
   ```bash
   # PostgreSQL
   DATABASE_URL=postgresql://user:password@localhost/telia
   
   # MySQL
   DATABASE_URL=mysql+pymysql://user:password@localhost/telia
   ```

## 📚 Technologies

- **FastAPI**: Framework web moderne et rapide
- **SQLAlchemy**: ORM pour la base de données
- **Pydantic**: Validation des données
- **python-jose**: Gestion des JWT tokens
- **passlib**: Hashage des mots de passe (bcrypt)
- **python-multipart**: Support formulaires multipart

## 🐛 Troubleshooting

### Erreur: "Could not validate credentials"
- Vérifiez que le token est valide et non expiré
- Vérifiez le format: `Authorization: Bearer YOUR_TOKEN`

### Erreur: "Access forbidden"
- Vérifiez que votre utilisateur a le bon rôle
- Vérifiez que votre compte est actif (`is_active: true`)

### Erreur: "Email already registered"
- L'email est déjà utilisé par un autre compte
- Utilisez un email différent ou connectez-vous

## 📄 License

MIT License
