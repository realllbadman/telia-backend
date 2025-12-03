from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime
from app.models import UserRole


# ============ Schémas Utilisateur ============

class UserBase(BaseModel):
    """Schéma de base pour l'utilisateur"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """Schéma pour l'inscription d'un utilisateur"""
    password: str = Field(..., min_length=8, max_length=100)
    role: Optional[UserRole] = UserRole.CUSTOMER


class UserUpdate(BaseModel):
    """Schéma pour la mise à jour d'un utilisateur"""
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    full_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8, max_length=100)
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """Schéma pour la réponse utilisateur"""
    id: int
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# ============ Schémas d'Authentification ============

class Token(BaseModel):
    """Schéma pour la réponse du token JWT"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Schéma pour les données de la charge utile du token"""
    user_id: Optional[int] = None
    username: Optional[str] = None
    role: Optional[str] = None


class LoginRequest(BaseModel):
    """Schéma pour la requête de connexion"""
    email: Optional[str] = None
    username: Optional[str] = None
    password: str = Field(..., min_length=8)

    def model_post_init(self, __data):
        """S'assure que l'email ou le nom d'utilisateur est fourni"""
        if not self.email and not self.username:
            raise ValueError("L'email ou le nom d'utilisateur doit être fourni")
        super().model_post_init(__data)


class LoginResponse(BaseModel):
    """Schéma pour la réponse de connexion"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse