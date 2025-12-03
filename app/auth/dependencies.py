from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, UserRole
from app.schemas import TokenData
from app.auth.utils import decode_access_token

# Schéma de sécurité
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Récupérer l'utilisateur actuellement authentifié à partir du token JWT
    
    Args:
        credentials: Identifiants d'autorisation HTTP avec token Bearer
        db: Session de base de données
        
    Returns:
        User: Utilisateur actuellement authentifié
        
    Raises:
        HTTPException: Si le token est invalide ou l'utilisateur non trouvé
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Impossible de valider les identifiants",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Décoder le token
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if payload is None:
        raise credentials_exception
    
    user_id: int = payload.get("user_id")
    username: str = payload.get("username")
    
    if user_id is None or username is None:
        raise credentials_exception
    
    # Récupérer l'utilisateur depuis la base de données
    user = db.query(User).filter(User.id == user_id).first()
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Utilisateur inactif"
        )
    
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    S'assurer que l'utilisateur actuel est actif
    
    Args:
        current_user: Utilisateur actuellement authentifié
        
    Returns:
        User: Utilisateur actuel actif
        
    Raises:
        HTTPException: Si l'utilisateur est inactif
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Utilisateur inactif"
        )
    return current_user


def require_role(allowed_roles: List[UserRole]):
    """
    Fabrique de dépendance pour vérifier si l'utilisateur a le(s) rôle(s) requis
    
    Args:
        allowed_roles: Liste des rôles autorisés
        
    Returns:
        Function: Fonction de dépendance qui vérifie le rôle de l'utilisateur
    """
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accès interdit. Rôles requis : {[role.value for role in allowed_roles]}"
            )
        return current_user
    
    return role_checker


# Dépendances de rôle pré-configurées
require_superadmin = require_role([UserRole.SUPERADMIN])
require_customer = require_role([UserRole.CUSTOMER, UserRole.SUPERADMIN])