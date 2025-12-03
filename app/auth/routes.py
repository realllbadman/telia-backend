from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, UserRole
from app.schemas import (
    UserCreate, 
    UserResponse, 
    LoginRequest, 
    LoginResponse,
    Token
)
from app.auth.utils import verify_password, get_password_hash, create_access_token
from app.auth.dependencies import get_current_user, require_superadmin

router = APIRouter(prefix="/auth", tags=["Authentification"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Inscrire un nouvel utilisateur
    
    - **email**: Email de l'utilisateur (doit être unique)
    - **username**: Nom d'utilisateur (doit être unique)
    - **password**: Mot de passe de l'utilisateur (min 8 caractères)
    - **full_name**: Nom complet de l'utilisateur (optionnel)
    - **role**: Rôle de l'utilisateur (défaut : customer)
    
    Retourne les informations de l'utilisateur créé
    """
    # Vérifier si l'email existe déjà
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email déjà enregistré"
        )
    
    # Vérifier si le nom d'utilisateur existe déjà
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nom d'utilisateur déjà pris"
        )
    
    # Créer un nouvel utilisateur
    hashed_password = get_password_hash(user_data.password)
    
    new_user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        role=user_data.role
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user


@router.post("/login", response_model=LoginResponse)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """
    Connexion avec email/nom d'utilisateur et mot de passe
    
    - **email**: Email de l'utilisateur (optionnel si le nom d'utilisateur est fourni)
    - **username**: Nom d'utilisateur de l'utilisateur (optionnel si l'email est fourni)  
    - **password**: Mot de passe de l'utilisateur
    
    Retourne un token d'accès et les informations de l'utilisateur
    """
    # Trouver l'utilisateur par email ou nom d'utilisateur
    query_conditions = []
    if login_data.email:
        query_conditions.append(User.email == login_data.email)
    if login_data.username:
        query_conditions.append(User.username == login_data.username)
    
    user = db.query(User).filter(
        User.email.in_([login_data.email, login_data.username]) |
        User.username.in_([login_data.email, login_data.username])
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nom d'utilisateur ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Vérifier le mot de passe
    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nom d'utilisateur ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Vérifier si l'utilisateur est actif
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte utilisateur inactif"
        )
    
    # Créer un token d'accès
    access_token = create_access_token(
        data={
            "user_id": user.id,
            "username": user.username,
            "role": user.role.value
        }
    )
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Obtenir les informations de l'utilisateur actuellement authentifié
    
    Nécessite un token JWT valide dans l'en-tête Authorization
    """
    return current_user


@router.get("/users", response_model=list[UserResponse])
def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_superadmin),
    db: Session = Depends(get_db)
):
    """
    Lister tous les utilisateurs (Superadmin uniquement)
    
    - **skip**: Nombre d'enregistrements à ignorer (pagination)
    - **limit**: Nombre maximum d'enregistrements à retourner
    
    Nécessite le rôle superadmin
    """
    users = db.query(User).offset(skip).limit(limit).all()
    return users