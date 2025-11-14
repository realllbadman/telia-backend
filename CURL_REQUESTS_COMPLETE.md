# 🚀 Requêtes Curl Prêtes pour Outils en Ligne

## 📝 Collection Complète de Requêtes

### 🔐 1. Inscription Utilisateur Customer

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "customer@example.com",
    "username": "customer",
    "password": "password123",
    "role": "customer"
  }'
```

**Alternative pour ReqBin :**
- Method: POST
- URL: `http://localhost:8000/auth/register`
- Headers:
  ```
  Content-Type: application/json
  ```
- Body (JSON):
  ```json
  {
    "email": "customer@example.com",
    "username": "customer", 
    "password": "password123",
    "role": "customer"
  }
  ```

### 🔑 2. Connexion Utilisateur Customer

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "customer@example.com",
    "password": "password123"
  }'
```

**Copier le `access_token` de la réponse pour les tests suivants !**

### 👤 3. Récupération Profil Utilisateur

```bash
curl -X GET http://localhost:8000/auth/me \
  -H "Authorization: Bearer VOTRE_ACCESS_TOKEN_ICI"
```

### 🛡️ 4. Route Protégée

```bash
curl -X GET http://localhost:8000/protected \
  -H "Authorization: Bearer VOTRE_ACCESS_TOKEN_ICI"
```

### 👥 5. Zone Customer

```bash
curl -X GET http://localhost:8000/customer-area \
  -H "Authorization: Bearer VOTRE_ACCESS_TOKEN_ICI"
```

### 👑 6. Inscription Superadmin

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "superadmin@example.com",
    "username": "superadmin",
    "password": "admin123",
    "role": "superadmin"
  }'
```

### 🔑 7. Connexion Superadmin

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "superadmin@example.com",
    "password": "admin123"
  }'
```

### 🔒 8. Zone Admin (Superadmin Only)

```bash
curl -X GET http://localhost:8000/admin-only \
  -H "Authorization: Bearer VOTRE_ACCESS_TOKEN_SUPERADMIN"
```

### 📋 9. Liste des Utilisateurs (Superadmin Only)

```bash
curl -X GET http://localhost:8000/auth/users \
  -H "Authorization: Bearer VOTRE_ACCESS_TOKEN_SUPERADMIN"
```

## 🧪 Tests de Sécurité

### ❌ 10. Accès Admin Refusé (Customer)

```bash
curl -X GET http://localhost:8000/admin-only \
  -H "Authorization: Bearer VOTRE_ACCESS_TOKEN_CUSTOMER"
```

**Réponse attendue :**
```json
{
  "detail": "Access forbidden. Required roles: ['superadmin']"
}
```

### ❌ 11. Accès Sans Token

```bash
curl -X GET http://localhost:8000/protected
```

**Réponse attendue :**
```json
{
  "detail": "Not authenticated"
}
```

### ❌ 12. Test de Login avec Mauvais Mot de Passe

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "customer@example.com",
    "password": "mauvais_mot_de_passe"
  }'
```

## 🔧 Configuration ReqBin

### Variables d'Environnement ReqBin
```javascript
// Définir ces variables dans ReqBin
var customer_email = "customer@example.com";
var admin_email = "superadmin@example.com";
var customer_password = "password123";
var admin_password = "admin123";
var customer_token = ""; // À remplir après login
var admin_token = ""; // À remplir après login
```

### Collection ReqBin Prête

**1. Register Customer**
- URL: `http://localhost:8000/auth/register`
- Method: POST
- Headers: `Content-Type: application/json`
- Body: 
  ```json
  {
    "email": "{{customer_email}}",
    "username": "customer",
    "password": "{{customer_password}}",
    "role": "customer"
  }
  ```

**2. Login Customer**
- URL: `http://localhost:8000/auth/login`
- Method: POST
- Headers: `Content-Type: application/json`
- Body:
  ```json
  {
    "email": "{{customer_email}}",
    "password": "{{customer_password}}"
  }
  ```
- **Script Post-Réponse :** `customer_token = response.access_token`

**3. Get Profile**
- URL: `http://localhost:8000/auth/me`
- Method: GET
- Headers: `Authorization: Bearer {{customer_token}}`

**4. Protected Route**
- URL: `http://localhost:8000/protected`
- Method: GET
- Headers: `Authorization: Bearer {{customer_token}}`

**5. Customer Area**
- URL: `http://localhost:8000/customer-area`
- Method: GET
- Headers: `Authorization: Bearer {{customer_token}}`

**6. Register Admin**
- URL: `http://localhost:8000/auth/register`
- Method: POST
- Headers: `Content-Type: application/json`
- Body:
  ```json
  {
    "email": "{{admin_email}}",
    "username": "superadmin",
    "password": "{{admin_password}}",
    "role": "superadmin"
  }
  ```

**7. Login Admin**
- URL: `http://localhost:8000/auth/login`
- Method: POST
- Headers: `Content-Type: application/json`
- Body:
  ```json
  {
    "email": "{{admin_email}}",
    "password": "{{admin_password}}"
  }
  ```
- **Script Post-Réponse :** `admin_token = response.access_token`

**8. Admin Area**
- URL: `http://localhost:8000/admin-only`
- Method: GET
- Headers: `Authorization: Bearer {{admin_token}}`

**9. List Users**
- URL: `http://localhost:8000/auth/users`
- Method: GET
- Headers: `Authorization: Bearer {{admin_token}}`

## 📊 Scénarios de Test Automatisés

### Scénario 1 : Test Complet Utilisateur
1. Register Customer
2. Login Customer → Obtenir token
3. Get Profile avec token
4. Access Protected avec token
5. Customer Area avec token

### Scénario 2 : Test Complet Admin
1. Register Superadmin
2. Login Superadmin → Obtenir token
3. Admin Area avec token
4. List Users avec token

### Scénario 3 : Test Sécurité
1. Try Admin Area avec Customer token → Doit échouer
2. Try Protected sans token → Doit échouer
3. Try Login avec mauvais password → Doit échouer

## 🎯 Tokens de Test Valides

**Utilisateur Customer Créé :**
- Email: customer@example.com
- Password: password123
- Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9... (valide 30 min)

**Utilisateur Superadmin Créé :**
- Email: superadmin@example.com
- Password: admin123
- Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9... (valide 30 min)

## 📝 Documentation API

**Documentation Interactive :** `http://localhost:8000/docs`
**ReDoc :** `http://localhost:8000/redoc`

---

**Tous les tests sont validés et fonctionnels !** ✅