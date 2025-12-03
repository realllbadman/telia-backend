from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Configuration JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Base de données
    DATABASE_URL: str = "sqlite:///./telia.db"
    
    # Application
    APP_NAME: str = "Glotelho API"
    APP_VERSION: str = "1.0.0"
    
    # CORS (Cross-Origin Resource Sharing)
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Intégration Magento
    MAGENTO_BASE_URL: str
    MAGENTO_ACCESS_TOKEN: str
    MAGENTO_TIMEOUT: int = 15
    MAGENTO_STORE_ID: int = 1
    MAGENTO_CURRENCY: str = "XAF"
    
    class Config:
        env_file = ".env"


settings = Settings()