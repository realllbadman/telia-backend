from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings

# Utiliser PBKDF2 pour une meilleure compatibilité
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Vérifier un mot de passe en clair par rapport à un mot de passe hashé
    
    Args:
        plain_password: Mot de passe en clair
        hashed_password: Mot de passe hashé provenant de la base de données
        
    Returns:
        bool: True si le mot de passe correspond, False sinon
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """
    Hasher un mot de passe en utilisant PBKDF2
    
    Args:
        password: Mot de passe en clair
        
    Returns:
        str: Mot de passe hashé
    """
    try:
        return pwd_context.hash(password)
    except Exception as e:
        raise ValueError(f"Échec du hachage du mot de passe : {str(e)}")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Créer un token d'accès JWT
    
    Args:
        data: Dictionnaire contenant les données à encoder dans le token
        expires_delta: Delta de temps d'expiration optionnel
        
    Returns:
        str: Token JWT encodé
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    Décoder et vérifier un token d'accès JWT
    
    Args:
        token: Chaîne du token JWT
        
    Returns:
        dict: Charge utile du token décodé ou None si invalide
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None