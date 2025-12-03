"""
Modèles de base de données SQLAlchemy pour l'authentification.

Ce module définit les tables et structures de données pour la gestion
des utilisateurs et de leurs rôles dans le système.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from sqlalchemy.sql import func
from app.database import Base
import enum


class UserRole(str, enum.Enum):
    """
    Énumération des rôles utilisateur disponibles dans le système.
    
    Hérite de str pour permettre la sérialisation JSON directe.
    
    Valeurs:
        SUPERADMIN: Administrateur avec tous les privilèges (gestion utilisateurs, accès Magento)
        CUSTOMER: Client standard avec accès limité aux fonctionnalités publiques
    """
    SUPERADMIN = "superadmin"
    CUSTOMER = "customer"


class User(Base):
    """
    Modèle de base de données représentant un utilisateur du système.
    
    Cette table stocke les informations d'authentification et de profil
    des utilisateurs. Les mots de passe sont toujours stockés hashés.
    
    Attributs:
        id: Identifiant unique auto-incrémenté (clé primaire)
        email: Adresse email unique de l'utilisateur (indexée)
        username: Nom d'utilisateur unique (indexé)
        hashed_password: Mot de passe hashé avec PBKDF2-SHA256
        full_name: Nom complet de l'utilisateur (optionnel)
        role: Rôle de l'utilisateur (superadmin ou customer, défaut: customer)
        is_active: Indique si le compte est actif (défaut: True)
        created_at: Date et heure de création du compte (automatique)
        updated_at: Date et heure de dernière modification (automatique)
    """
    __tablename__ = "users"
    
    # Identifiant unique de l'utilisateur
    id = Column(Integer, primary_key=True, index=True)
    
    # Informations de connexion (uniques et indexées pour recherche rapide)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    
    # Informations de profil
    full_name = Column(String, nullable=True)
    
    # Contrôle d'accès et statut
    role = Column(Enum(UserRole), default=UserRole.CUSTOMER, nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Horodatage automatique (timezone-aware)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        """Représentation textuelle de l'utilisateur pour débogage."""
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"
