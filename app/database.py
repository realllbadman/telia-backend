from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Création du moteur de base de données
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

# Création de la classe SessionLocal pour la gestion des sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Création de la classe Base pour les modèles
Base = declarative_base()


# Dépendance pour obtenir une session de base de données
def get_db():
    """
    Générateur de session de base de données.
    Assure que la session est correctement fermée après utilisation.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()