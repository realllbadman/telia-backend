# Guide de Test avec Outils d'API en Ligne

## 🎯 Objectif
Tester le système d'authentification JWT avec des outils en ligne comme **reqbin.com**, **Postman**, ou **Insomnia**.

## 📋 Prérequis
- Serveur FastAPI démarré sur `http://localhost:8000`
- Documentation API disponible sur `http://localhost:8000/docs`

## 🧪 Tests à Effectuer

### 1. Test d'Inscription (Register)
**URL :** `http://localhost:8000/auth/register`
**Méthode :** POST

**Données JSON :**
```json
{
    "email": "testuser@example.com",
    "username": "testuser",
    "password": "password123",
    "role": "customer"
}
```

**Avec reqbin.com :**
1. Aller sur https://reqbin.com
2. Sélectionner "POST" et entrer l'URL
3. Ajouter header `Content-Type: application/json`
4. Copier-coller le JSON dans le body
5. Cliquer "Send"

**Réponse attendue :**
```json
{
    "id": 1,
    "email": "testuser@example.com",
    "username": "testuser",
    "role": "customer",
    "is_active": true,
    "created_at": "2025-11-14T20:17:11"
}
```

### 2. Test de Connexion (Login)
**URL :** `http://localhost:8000/auth/login`
**Méthode :** POST

**Données JSON :**
```json
{
    "email": "testuser@example.com",
    "password": "password123"
}
```

**Réponse attendue :**
```json
{
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "token_type": "bearer"
}
```

### 3. Test d'Accès Protégé
**URL :** `http://localhost:8000/protected`
**Méthode :** GET
**Headers :** `Authorization: Bearer {VOTRE_TOKEN_JWT}`

**Avec le token reçu du login, ajouter ce header et tester.**

**Réponse attendue :**
```json
{
    "message": "Access granted! You are authenticated.",
    "user": {
        "email": "testuser@example.com",
        "username": "testuser",
        "role": "customer"
    }
}
```

### 4. Test des Profils Utilisateur
**URL :** `http://localhost:8000/auth/me`
**Méthode :** GET
**Headers :** `Authorization: Bearer {VOTRE_TOKEN_JWT}`

**Réponse attendue :**
```json
{
    "id": 1,
    "email": "testuser@example.com",
    "username": "testuser",
    "role": "customer",
    "is_active": true,
    "created_at": "2025-11-14T20:17:11"
}
```

### 5. Test des Rôles Admin (Zone Superadmin)
**URL :** `http://localhost:8000/admin-only`
**Méthode :** GET
**Headers :** `Authorization: Bearer {TOKEN_SUPERADMIN}`

### 6. Test des Rôles Client (Zone Customer)
**URL :** `http://localhost:8000/customer-area`
**Méthode :** GET
**Headers :** `Authorization: Bearer {TOKEN_CUSTOMER}`

## 🔧 Configuration ReqBin.com

### Étape 1 : Configuration de Base
1. **URL Base :** `http://localhost:8000`
2. **Headers Constants :**
   - `Content-Type: application/json`
   - `Accept: application/json`

### Étape 2 : Variables d'Environnement
Utiliser les variables de reqbin pour stocker le token :
```
{{token}} = Le token JWT reçu du login
```

### Étape 3 : Scripts de Test
Utiliser les built-in variables de reqbin :
- `{{access_token}}` pour stocker le token
- `{{user_email}}` pour l'email de test

## 📝 Cas de Test Complets

### Test Suite 1 : Cycle Complet Utilisateur
1. **Register User** → Sauvegarder l'ID utilisateur
2. **Login** → Sauvegarder le `access_token`
3. **Get Profile** → Vérifier les infos utilisateur
4. **Access Protected Route** → Vérifier l'authentification
5. **Customer Area** → Vérifier l'accès role-based

### Test Suite 2 : Cas d'Erreur
1. **Login avec mauvais password** → 401 Unauthorized
2. **Access sans token** → 401 Unauthorized
3. **Access avec token invalide** → 401 Unauthorized
4. **Customer sur route admin** → 403 Forbidden

### Test Suite 3 : Superadmin
1. **Créer superadmin** via script `create_superadmin.py`
2. **Login superadmin** → Obtenir token superadmin
3. **List all users** → Route `/auth/users` (admin only)

## 🎮 Scripts de Test Automatisés

### Utiliser Postman Collection
Importer la collection Postman (à venir) pour tester automatiquement.

### Utiliser curl
```bash
# Test register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","username":"test","password":"pass123","role":"customer"}'

# Test login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"pass123"}'

# Test protected route
curl -X GET http://localhost:8000/protected \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## ✅ Checklist de Validation

### Fonctionnalités de Base
- [ ] Inscription utilisateur fonctionne
- [ ] Login génère un JWT valide
- [ ] Routes protégées rejettent les requêtes non authentifiées
- [ ] Récupération profil utilisateur fonctionne
- [ ] Gestion des rôles (superadmin/customer)

### Sécurité
- [ ] Tokens JWT expirent (30 minutes par défaut)
- [ ] Mots de passe sont hashés (bcrypt)
- [ ] Validation email fonctionne
- [ ] Validation des données d'entrée

### Erreurs HTTP
- [ ] 200 OK - Succès
- [ ] 201 Created - Utilisateur créé
- [ ] 401 Unauthorized - Token manquant/invalide
- [ ] 403 Forbidden - Permissions insuffisantes
- [ ] 422 Unprocessable Entity - Données invalides
- [ ] 500 Internal Server Error - Erreur serveur

## 🚨 Résolution de Problèmes

### "Connection refused"
- Vérifier que le serveur fonctionne sur port 8000
- Vérifier que reqbin peut accéder à localhost (peut nécessiter un tunnel comme ngrok)

### "Token invalid"
- Vérifier que le token n'a pas expiré (30 min)
- Vérifier le format "Bearer TOKEN"

### "CORS Error"
- Le serveur supporte CORS par défaut
- Si problème, ajouter headers CORS

### "Database Error"
- Vérifier que la base SQLite est accessible
- Vérifier les permissions du fichier telia.db

## 📊 Métriques de Performance

### Temps de Réponse
- Register : < 500ms
- Login : < 300ms
- Protected routes : < 200ms

### Sécurité
- Hash password : bcrypt cost factor 12
- JWT expiration : 30 minutes
- Token algorithm : HS256

## 🎯 Prochaines Étapes

1. Créer collection Postman complète
2. Implémenter tests automatisés
3. Intégrer CI/CD pour validation continue
4. Ajouter monitoring et logs
5. Tests de charge et performance

---

**Note :** Ce guide couvre tous les aspects du système d'authentification JWT. Assurez-vous de tester chaque fonctionnalité systématiquement.