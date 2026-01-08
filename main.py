
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
from app.auth.routes import router as auth_router
from app.auth.dependencies import get_current_user, require_superadmin, require_customer
from app.magento import router as magento_router
from app.models import User, UserRole

# Import du nouveau service Magento (Services/)
from Services.magento.routes import router as products_router

# Création automatique des tables de la base de données au démarrage
# Utilise les modèles SQLAlchemy définis dans app.models
Base.metadata.create_all(bind=engine)

# Initialisation de l'application FastAPI avec métadonnées
app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered e-commerce backend with Gemini & Magento 2 - JWT Authentication",
    version=settings.APP_VERSION
)

# Configuration du middleware CORS (Cross-Origin Resource Sharing)
# Permet aux applications frontend d'accéder à l'API depuis différentes origines
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,  # Liste des origines autorisées
    allow_credentials=True,  # Autorise l'envoi de cookies et credentials
    allow_methods=["*"],  # Autorise toutes les méthodes HTTP (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Autorise tous les en-têtes HTTP
)

# Inclusion des routeurs de modules
# auth_router: endpoints d'authentification (/auth/*)
# magento_router: endpoints d'intégration Magento (/magento/*)
# products_router: nouveau service produits (/api/v1/products/*)
app.include_router(auth_router)
app.include_router(magento_router)
app.include_router(products_router)


@app.get("/")
def home():
    """
    Endpoint d'accueil de l'API.
    
    Fournit des informations de base sur l'API et liens utiles.
    Accessible sans authentification.
    
    Returns:
        dict: Message de bienvenue, version de l'API et liens vers la documentation
    """
    return {
        "message": "Welcome, I'm Telia",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "authentication": "JWT Bearer Token"
    }


@app.get("/protected")
def protected_route(current_user: User = Depends(get_current_user)):
    """
    Exemple de route protégée nécessitant une authentification.
    
    Cette route démontre l'utilisation de la dépendance get_current_user
    pour sécuriser un endpoint. L'utilisateur doit fournir un token JWT
    valide dans l'en-tête Authorization.
    
    Args:
        current_user: Utilisateur authentifié, injecté automatiquement par FastAPI
    
    Returns:
        dict: Informations sur l'utilisateur connecté
    
    Raises:
        HTTPException 401: Si le token est invalide ou absent
    """
    return {
        "message": f"Hello {current_user.username}!",
        "user_id": current_user.id,
        "role": current_user.role.value,
        "email": current_user.email
    }


@app.get("/admin-only")
def admin_only_route(current_user: User = Depends(require_superadmin)):
    """
    Exemple de route réservée aux super-administrateurs.
    
    Cette route démontre le contrôle d'accès basé sur les rôles (RBAC).
    Seulement les utilisateurs avec le rôle 'superadmin' peuvent y accéder.
    
    Args:
        current_user: Super-administrateur authentifié
    
    Returns:
        dict: Message de bienvenue et informations d'accès
    
    Raises:
        HTTPException 401: Si le token est invalide ou absent
        HTTPException 403: Si l'utilisateur n'a pas le rôle superadmin
    """
    return {
        "message": f"Welcome superadmin {current_user.username}!",
        "access_level": "superadmin",
        "user_id": current_user.id
    }


@app.get("/customer-area")
def customer_area_route(current_user: User = Depends(require_customer)):
    """
    Exemple de route accessible aux clients et super-administrateurs.
    
    Cette route démontre un endpoint accessible à plusieurs rôles.
    Les clients et les super-administrateurs peuvent y accéder.
    
    Args:
        current_user: Utilisateur authentifié (customer ou superadmin)
    
    Returns:
        dict: Message de bienvenue dans l'espace client
    
    Raises:
        HTTPException 401: Si le token est invalide ou absent
        HTTPException 403: Si l'utilisateur n'a ni le rôle customer ni superadmin
    """
    return {
        "message": f"Welcome to customer area, {current_user.username}!",
        "role": current_user.role.value,
        "user_id": current_user.id
    }


# Point d'entrée pour exécution directe du script
# Lance le serveur de développement Uvicorn avec rechargement automatique
if __name__ == "__main__":
    import uvicorn
    # host="0.0.0.0" permet l'accès depuis n'importe quelle interface réseau
    # reload=True active le rechargement automatique lors des modifications de code
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
