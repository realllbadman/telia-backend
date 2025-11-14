from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # JWT Configuration
    SECRET_KEY: str = "your-secret-key-change-this-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Database
    DATABASE_URL: str = "sqlite:///./telia.db"
    
    # Application
    APP_NAME: str = "Glotelho API"
    APP_VERSION: str = "1.0.0"
    
    class Config:
        env_file = ".env"


settings = Settings()
