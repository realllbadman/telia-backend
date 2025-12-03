# 🤖 Telia Assistant - Chatbot Intelligent Glotelho

<p align="center">
  <img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ccircle cx='50' cy='50' r='45' fill='%23FF6600'/%3E%3Crect x='25' y='35' width='50' height='35' rx='5' fill='white'/%3E%3Ccircle cx='38' cy='50' r='6' fill='%23FF6600'/%3E%3Ccircle cx='62' cy='50' r='6' fill='%23FF6600'/%3E%3C/svg%3E" width="120" alt="Telia Logo"/>
</p>

<p align="center">
  <strong>Assistant shopping intelligent propulsé par l'IA Gemini</strong><br>
  Conçu pour la plateforme e-commerce <a href="https://glotelho.cm">Glotelho.cm</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Nuxt.js-3.x-00DC82?style=flat-square&logo=nuxt.js" alt="Nuxt.js"/>
  <img src="https://img.shields.io/badge/Vue.js-3.x-4FC08D?style=flat-square&logo=vue.js" alt="Vue.js"/>
  <img src="https://img.shields.io/badge/Gemini-AI-4285F4?style=flat-square&logo=google" alt="Gemini AI"/>
  <img src="https://img.shields.io/badge/TypeScript-5.x-3178C6?style=flat-square&logo=typescript" alt="TypeScript"/>
</p>

---

## 📋 Table des Matières

- [🎯 Présentation](#-présentation)
- [✨ Fonctionnalités](#-fonctionnalités)
- [🏗️ Architecture](#️-architecture)
- [⚙️ Installation](#️-installation)
- [🚀 Démarrage](#-démarrage)
- [🔧 Configuration](#-configuration)
- [📁 Structure du Projet](#-structure-du-projet)
- [🎨 Thème & Design](#-thème--design)
- [💬 Utilisation du Chatbot](#-utilisation-du-chatbot)
- [🔌 API & Intégrations](#-api--intégrations)
- [📱 Modes d'Affichage](#-modes-daffichage)
- [🛠️ Développement](#️-développement)
- [❓ FAQ](#-faq)

---

## 🎯 Présentation

**Telia Assistant** est un chatbot intelligent conçu pour être intégré sur la plateforme e-commerce [Glotelho.cm](https://glotelho.cm). Il utilise l'intelligence artificielle **Google Gemini** pour comprendre les besoins des clients et les aider dans leur parcours d'achat.

### Objectifs principaux :
- 🛒 **Aide à l'achat** : Guider les clients vers les produits adaptés à leurs besoins
- 🔍 **Recherche intelligente** : Comprendre les requêtes en langage naturel
- 📸 **Analyse d'images** : Identifier des produits à partir de photos
- 💰 **Gestion du budget** : Proposer des produits dans la fourchette de prix du client
- 📦 **Suivi de commandes** : Informer sur l'état des commandes

---

## ✨ Fonctionnalités

### 🔐 Authentification
| Fonctionnalité | Description |
|----------------|-------------|
| Connexion | Email ou nom d'utilisateur + mot de passe |
| Inscription | Création de compte avec validation |
| Session persistante | Token JWT stocké localement |
| Déconnexion | Suppression sécurisée de la session |

### 💬 Conversation Intelligente
| Fonctionnalité | Description |
|----------------|-------------|
| Chat en temps réel | Réponses instantanées de l'IA |
| Historique | Conservation des messages de la session |
| Markdown | Support du formatage (gras, italique, listes) |
| Emojis | Réponses engageantes et conviviales |

### 📸 Gestion des Images
| Fonctionnalité | Description |
|----------------|-------------|
| Upload multiple | Envoyer plusieurs images à la fois |
| Prévisualisation | Aperçu avant envoi |
| Analyse IA | Gemini analyse le contenu des images |
| Suggestions | Produits similaires proposés |

### 🛍️ Recommandations Produits
| Fonctionnalité | Description |
|----------------|-------------|
| Recherche contextuelle | Basée sur la conversation |
| Filtrage par budget | Extraction automatique du prix max |
| Affichage produits | Cartes avec image, nom, prix |
| Liens directs | Redirection vers Glotelho.cm |

### 🖥️ Interface Widget
| Fonctionnalité | Description |
|----------------|-------------|
| Mode compact | Widget flottant 380×520px |
| Mode plein écran | Occupe tout l'écran |
| Mode minimisé | Barre d'en-tête uniquement |
| Badge notifications | Compteur de messages non lus |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND (Nuxt.js)                      │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Pages     │  │  Composants │  │      Stores         │  │
│  │  - Login    │  │  - Widget   │  │  - Auth (Pinia)     │  │
│  │  - Chat     │  │  - Messages │  │  - Chat (Pinia)     │  │
│  │  - Index    │  │  - Input    │  │                     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                    SERVER (Nitro)                           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  /api/chat.post.ts → Gemini AI Integration          │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   SERVICES EXTERNES                         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐         ┌─────────────────────────┐    │
│  │  Google Gemini  │         │   Backend FastAPI       │    │
│  │  (IA Générative)│         │   - Auth JWT            │    │
│  │  gemini-2.5     │         │   - API Magento         │    │
│  └─────────────────┘         │   - Base de données     │    │
│                              └─────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## ⚙️ Installation

### Prérequis

- **Node.js** 18.x ou supérieur
- **npm** 9.x ou supérieur
- **Python** 3.10+ (pour le backend)
- **Git** (optionnel)

### Étapes d'installation

```bash
# 1. Cloner ou accéder au projet
cd telia-chatbot

# 2. Installer les dépendances
npm install

# 3. Préparer Nuxt
npm run postinstall
```

---

## 🚀 Démarrage

### Mode Développement

```bash
# Terminal 1 : Démarrer le backend (depuis telia-backend/)
cd ../telia-backend
python main.py

# Terminal 2 : Démarrer le frontend (depuis telia-chatbot/)
npm run dev
```

### Accès à l'application

| Service | URL |
|---------|-----|
| **Frontend** | http://localhost:3000 |
| **Backend API** | http://localhost:8000 |
| **API Docs** | http://localhost:8000/docs |

### Mode Production

```bash
# Build de production
npm run build

# Prévisualisation
npm run preview
```

---

## 🔧 Configuration

### Variables d'Environnement

Créer un fichier `.env` à la racine :

```env
# Clé API Google Gemini (obligatoire)
GEMINI_API_KEY=votre_clé_api_gemini

# URL du backend FastAPI
API_BASE_URL=http://localhost:8000
```

### Configuration Nuxt (`nuxt.config.ts`)

```typescript
export default defineNuxtConfig({
  runtimeConfig: {
    // Clé Gemini (côté serveur uniquement)
    geminiApiKey: process.env.GEMINI_API_KEY,
    
    public: {
      // URL du backend
      apiBaseUrl: process.env.API_BASE_URL || 'http://localhost:8000',
      appName: 'Telia Assistant',
    }
  }
})
```

### Obtenir une Clé API Gemini

1. Accéder à [Google AI Studio](https://aistudio.google.com/)
2. Créer un projet ou en sélectionner un
3. Générer une clé API
4. Copier la clé dans votre fichier `.env`

---

## 📁 Structure du Projet

```
telia-chatbot/
│
├── 📁 assets/
│   └── 📁 css/
│       └── main.css              # Styles globaux (thème Glotelho)
│
├── 📁 layouts/
│   └── default.vue               # Layout principal
│
├── 📁 middleware/
│   └── auth.ts                   # Protection des routes authentifiées
│
├── 📁 pages/
│   ├── index.vue                 # Page d'accueil (redirection)
│   ├── login.vue                 # Page de connexion/inscription
│   └── chat.vue                  # Interface du chatbot (widget)
│
├── 📁 server/
│   └── 📁 api/
│       └── chat.post.ts          # Endpoint API pour Gemini
│
├── 📁 stores/
│   ├── auth.ts                   # Store Pinia - Authentification
│   └── chat.ts                   # Store Pinia - Conversation
│
├── app.vue                       # Composant racine
├── nuxt.config.ts                # Configuration Nuxt
├── package.json                  # Dépendances npm
├── tsconfig.json                 # Configuration TypeScript
└── README.md                     # Ce fichier
```

### Description des Fichiers Clés

| Fichier | Rôle |
|---------|------|
| `pages/chat.vue` | Interface principale du widget chatbot |
| `server/api/chat.post.ts` | Intégration avec l'API Gemini |
| `stores/auth.ts` | Gestion de l'authentification JWT |
| `stores/chat.ts` | Gestion des messages et de la conversation |
| `middleware/auth.ts` | Protection des routes privées |
| `assets/css/main.css` | Variables CSS et styles Glotelho |

---

## 🎨 Thème & Design

### Palette de Couleurs Glotelho

| Élément | Couleur | Code Hex |
|---------|---------|----------|
| **Orange Principal** | ![#FF6600](https://via.placeholder.com/15/FF6600/000000?text=+) | `#FF6600` |
| **Orange Foncé** | ![#E55C00](https://via.placeholder.com/15/E55C00/000000?text=+) | `#E55C00` |
| **Noir Profond** | ![#0F1419](https://via.placeholder.com/15/0F1419/000000?text=+) | `#0F1419` |
| **Rouge Urgence** | ![#E63946](https://via.placeholder.com/15/E63946/000000?text=+) | `#E63946` |
| **Rose Secondaire** | ![#FF4757](https://via.placeholder.com/15/FF4757/000000?text=+) | `#FF4757` |
| **Texte Principal** | ![#333333](https://via.placeholder.com/15/333333/000000?text=+) | `#333333` |
| **Texte Secondaire** | ![#666666](https://via.placeholder.com/15/666666/000000?text=+) | `#666666` |

### Typographie

| Usage | Police | Poids |
|-------|--------|-------|
| Titres, Logo, Prix | **Poppins** | Bold (700) |
| Boutons CTA | **Poppins** | Semi-Bold (600) |
| Corps de texte | **Open Sans** | Regular (400) |
| Descriptions | **Open Sans** | Semi-Bold (600) |

### Principes de Design

- ✅ **Flat Design** - Pas d'ombres 3D ni de dégradés complexes
- ✅ **Contraste élevé** - Lisibilité maximale
- ✅ **Orange dominant** - Couleur d'action et de conversion
- ✅ **Responsive** - Adapté mobile et desktop

---

## 💬 Utilisation du Chatbot

### Exemples de Requêtes

```
👤 "Je cherche un téléphone à 90.000 FCFA"
🤖 Telia analyse le budget et propose des smartphones dans cette gamme

👤 "Je suis photographe, je veux un bon appareil"
🤖 Telia comprend le profil et suggère des appareils adaptés

👤 "Montrez-moi les promotions du moment"
🤖 Telia liste les offres en cours sur Glotelho

👤 [Envoie une image d'un produit]
🤖 Telia identifie le produit et propose des alternatives similaires

👤 "Je voudrais suivre ma commande #12345"
🤖 Telia fournit les informations de suivi
```

### Fonctionnalités de l'Interface

| Action | Comment faire |
|--------|---------------|
| **Ouvrir le chat** | Cliquer sur le bouton orange flottant |
| **Envoyer un message** | Taper + Entrée ou bouton envoi |
| **Ajouter une image** | Cliquer sur l'icône image 📷 |
| **Plein écran** | Cliquer sur l'icône ⛶ |
| **Minimiser** | Cliquer sur l'icône ➖ |
| **Fermer** | Cliquer sur l'icône ✕ |
| **Nouvelle conversation** | Cliquer sur l'icône ➕ |

---

## 🔌 API & Intégrations

### Endpoint Chat (`POST /api/chat`)

**Requête :**
```json
{
  "message": "Je cherche un téléphone pas cher",
  "images": [
    {
      "data": "base64_encoded_image_data",
      "mimeType": "image/jpeg"
    }
  ],
  "history": [
    { "role": "user", "content": "Bonjour" },
    { "role": "assistant", "content": "Bonjour ! Comment puis-je vous aider ?" }
  ]
}
```

**Réponse :**
```json
{
  "content": "Voici quelques téléphones dans votre budget...",
  "products": [
    {
      "id": 1234,
      "name": "Samsung Galaxy A54",
      "price_info": {
        "final_price": 85000,
        "formatted_final_price": "85 000 FCFA"
      },
      "images": [{ "url": "https://..." }],
      "url": "https://glotelho.cm/product/..."
    }
  ]
}
```

### Intégration Backend FastAPI

Le chatbot communique avec le backend pour :
- **Authentification** : `/auth/login`, `/auth/register`
- **Profil utilisateur** : `/auth/me`
- **Produits Magento** : `/magento/products` (optionnel)

---

## 📱 Modes d'Affichage

### 1. Mode Widget (par défaut)
- Position : Coin inférieur droit
- Dimensions : 380 × 520 px
- Idéal pour : Navigation sur le site

### 2. Mode Plein Écran
- Occupe 100% de l'écran
- Messages centrés (max 800px)
- Idéal pour : Conversations longues

### 3. Mode Minimisé
- Affiche uniquement l'en-tête
- Économise l'espace écran
- Idéal pour : Garder le chat accessible

### 4. Mode Fermé
- Widget masqué
- Bouton flottant visible
- Badge de notifications actif

---

## 🛠️ Développement

### Scripts Disponibles

```bash
# Développement avec hot-reload
npm run dev

# Build de production
npm run build

# Prévisualisation du build
npm run preview

# Préparation des types TypeScript
npm run postinstall
```

### Technologies Utilisées

| Technologie | Version | Usage |
|-------------|---------|-------|
| **Nuxt.js** | 3.x | Framework Vue.js |
| **Vue.js** | 3.x | Interface utilisateur |
| **Pinia** | 2.x | Gestion d'état |
| **TypeScript** | 5.x | Typage statique |
| **Google Generative AI** | 0.21.x | SDK Gemini |

### Bonnes Pratiques

- 📝 **Commentaires en français** - Code documenté
- 🔒 **Clé API côté serveur** - Sécurité renforcée
- 📦 **Stores séparés** - Auth et Chat isolés
- 🎨 **Variables CSS** - Thème centralisé
- 📱 **Mobile-first** - Design responsive

---

## ❓ FAQ

### Le chatbot ne répond pas ?
1. Vérifiez que le backend est démarré (`http://localhost:8000`)
2. Vérifiez la clé API Gemini dans `nuxt.config.ts`
3. Consultez les logs du serveur Nuxt

### Comment changer le modèle Gemini ?
Modifier dans `server/api/chat.post.ts` :
```typescript
const model = genAI.getGenerativeModel({ model: 'gemini-2.5-flash' })

### Les images ne s'envoient pas ?
- Formats supportés : JPEG, PNG, GIF, WebP
- Taille max recommandée : 5 MB
- Vérifiez la connexion internet

---

## 📄 Licence

Ce projet est propriétaire et développé pour **Glotelho.cm**.

© 2025 Glotelho - Tous droits réservés.

---

<p align="center">
  <strong>Développé avec ❤️ pour Glotelho.cm</strong><br>
  <a href="https://glotelho.cm">Visiter le site</a>
</p>
