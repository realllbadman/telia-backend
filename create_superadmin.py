"""
Script pour créer le premier superadmin
Usage: python create_superadmin.py
"""

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models import User, UserRole
from app.auth.utils import get_password_hash
from getpass import getpass


def create_superadmin():
    """Create the first superadmin user"""
    
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    # Create database session
    db: Session = SessionLocal()
    
    try:
        print("\n" + "=" * 60)
        print("🔐 Création d'un compte Superadmin")
        print("=" * 60 + "\n")
        
        # Get user input
        email = input("📧 Email: ").strip()
        username = input("👤 Username: ").strip()
        full_name = input("📝 Nom complet (optionnel): ").strip() or None
        password = getpass("🔑 Mot de passe (min 8 caractères): ")
        password_confirm = getpass("🔑 Confirmer le mot de passe: ")
        
        # Validation
        if not email or not username or not password:
            print("\n❌ Email, username et mot de passe sont obligatoires!")
            return
        
        if password != password_confirm:
            print("\n❌ Les mots de passe ne correspondent pas!")
            return
        
        if len(password) < 8:
            print("\n❌ Le mot de passe doit contenir au moins 8 caractères!")
            return
        
        # Check if email already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            print(f"\n❌ Un utilisateur avec l'email '{email}' existe déjà!")
            return
        
        # Check if username already exists
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            print(f"\n❌ Un utilisateur avec le username '{username}' existe déjà!")
            return
        
        # Create superadmin user
        hashed_password = get_password_hash(password)
        
        superadmin = User(
            email=email,
            username=username,
            hashed_password=hashed_password,
            full_name=full_name,
            role=UserRole.SUPERADMIN,
            is_active=True
        )
        
        db.add(superadmin)
        db.commit()
        db.refresh(superadmin)
        
        print("\n" + "=" * 60)
        print("✅ Superadmin créé avec succès!")
        print("=" * 60)
        print(f"📧 Email: {superadmin.email}")
        print(f"👤 Username: {superadmin.username}")
        print(f"🆔 ID: {superadmin.id}")
        print(f"👑 Role: {superadmin.role.value}")
        print(f"📅 Créé le: {superadmin.created_at}")
        print("=" * 60)
        print("\n💡 Vous pouvez maintenant vous connecter avec ces identifiants!")
        print("   Endpoint: POST http://localhost:8000/auth/login\n")
        
    except Exception as e:
        print(f"\n❌ Erreur lors de la création du superadmin: {e}")
        db.rollback()
    finally:
        db.close()


def list_superadmins():
    """List all superadmin users"""
    
    db: Session = SessionLocal()
    
    try:
        superadmins = db.query(User).filter(User.role == UserRole.SUPERADMIN).all()
        
        print("\n" + "=" * 60)
        print(f"👑 Liste des Superadmins ({len(superadmins)})")
        print("=" * 60 + "\n")
        
        if not superadmins:
            print("Aucun superadmin trouvé.\n")
        else:
            for admin in superadmins:
                status = "✅ Actif" if admin.is_active else "❌ Inactif"
                print(f"🆔 ID: {admin.id}")
                print(f"   Username: {admin.username}")
                print(f"   Email: {admin.email}")
                print(f"   Full Name: {admin.full_name or 'N/A'}")
                print(f"   Status: {status}")
                print(f"   Created: {admin.created_at}")
                print("-" * 60)
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
    finally:
        db.close()


def main():
    """Main menu"""
    
    while True:
        print("\n" + "=" * 60)
        print("🛠️  Gestion des Superadmins")
        print("=" * 60)
        print("\n1. Créer un nouveau superadmin")
        print("2. Liste des superadmins existants")
        print("3. Quitter")
        
        choice = input("\n👉 Choix: ").strip()
        
        if choice == "1":
            create_superadmin()
        elif choice == "2":
            list_superadmins()
        elif choice == "3":
            print("\n👋 Au revoir!\n")
            break
        else:
            print("\n❌ Choix invalide. Essayez encore.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Opération annulée. Au revoir!\n")
    except Exception as e:
        print(f"\n❌ Erreur inattendue: {e}\n")
