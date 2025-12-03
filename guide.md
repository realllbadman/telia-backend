# Guide de recherche produit Magento

Ce guide explique comment interroger la base produits Magento (Glotelho) via les services ajoutés dans cette API FastAPI.

## 1. Pré-requis
- Variables d’environnement configurées (`MAGENTO_BASE_URL`, `MAGENTO_ACCESS_TOKEN`, `MAGENTO_TIMEOUT`, `MAGENTO_STORE_ID`, `MAGENTO_CURRENCY`). Voir `.env.example`.
- Serveur FastAPI lancé (`uvicorn main:app --reload`) et compte superadmin disposant d’un token JWT.

## 2. Authentification
1. Créez (si besoin) un superadmin via `python create_superadmin.py create-superadmin`.
2. Connectez-vous à `/auth/login` (email/username + mot de passe) pour obtenir `access_token`.
3. Ajoutez l’en-tête `Authorization: Bearer <token>` à chaque requête `/magento/*`.

## 3. Vérifier la connexion Magento
```bash
curl -H "Authorization: Bearer <token>" \
     http://localhost:8000/magento/health
```
Réponse attendue : `ok: true`, `store_id`, `currency_code`, `sample_product_id`. Si une erreur apparaît, vérifier le jeton ou la connectivité réseau.

## 4. Rechercher des produits
Endpoint principal : `GET /magento/products`

Paramètres disponibles:
- `page` (défaut 1)
- `page_size` (1–100)
- `product_id` (optionnel, filtre exact sur `entity_id` Magento)
- `search` (optionnel, filtre partiel sur le nom)

Exemple : récupérer 5 produits contenant “ipad”.
```bash
curl -G \
  -H "Authorization: Bearer <token>" \
  --data-urlencode "page=1" \
  --data-urlencode "page_size=5" \
  --data-urlencode "search=ipad" \
  http://localhost:8000/magento/products
```
Réponse:
```json
{
  "items": [
    {
      "id": 8145,
      "name": "Apple iPad Pro ...",
      "price_info": {
        "final_price": 600300.0,
        "formatted_final_price": "<span class=\"price\">600 300,00 FCFA</span>"
      },
      "images": [
        {"url": "https://staging-site.glotelho.cm/media/catalog/product/...png"}
      ],
      "is_salable": true
    }
  ],
  "total_count": 1,
  "page": 1,
  "page_size": 5
}
```

### Recherche par ID précis
```bash
curl -G \
  -H "Authorization: Bearer <token>" \
  --data-urlencode "product_id=8145" \
  http://localhost:8000/magento/products
```

## 5. Récupérer un produit unique
Endpoint : `GET /magento/products/{product_id}`
```bash
curl -H "Authorization: Bearer <token>" \
     http://localhost:8000/magento/products/8145
```
Renvoie le même schéma qu’une ligne `items`.

## 6. Notes importantes
- Le token Magento courant n’autorise pas l’API “admin” `/V1/products`; nous utilisons `products-render-info`. L’identifiant est donc l’`entity_id`.
- `total_count` reflète les éléments renvoyés par Magento; si vous avez besoin du nombre global, demander un token avec les permissions `Magento_Catalog::products`.
- Tous les endpoints exigent un superadmin (dépendance `require_superadmin`). Assurez-vous que votre JWT appartient à ce rôle.

## 7. Debug
- 401 côté /magento → token JWT invalide ou rôle insuffisant.
- 502 renvoyé par FastAPI → `MagentoAPIError`. Inspectez `detail` (souvent “The consumer isn't authorized...”) et ajustez le token Magento.
- Pour tester directement la couche service : lancer un shell Python et instancier `MagentoService` avec `settings`.
