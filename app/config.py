from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional
from pydantic import ConfigDict, field_validator


class Settings(BaseSettings):
    # JWT Configuration
    SECRET_KEY: str = "telia-super-secret-key-2024-glotelho"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Database
    DATABASE_URL: str = "sqlite:///./telia.db"

    # Application
    APP_NAME: str = "Glotelho API"
    APP_VERSION: str = "1.0.0"

    # Magento Configuration
    MAGENTO_BASE_URL: Optional[str] = None
    MAGENTO_ACCESS_TOKEN: Optional[str] = None
    MAGENTO_TIMEOUT: int = 15
    MAGENTO_RETRIES: int = 2
    MAGENTO_STORE_VIEW_EN: str = "en"
    MAGENTO_STORE_VIEW_FR: str = "fr"

    # Mistral Configuration
    MISTRAL_API_KEY: Optional[str] = None
    MISTRAL_RETRIES: int = 2

    # Text-only LLM (chat, search, reasoning)
    MISTRAL_TEXT_MODEL: str = "mistral-small-latest"

    # Vision-capable LLM (image captioning, visual search)
    MISTRAL_VISION_MODEL: str = "pixtral-large-latest"

    # AssemblyAI ASR Configuration (audio search)
    ASSEMBLYAI_API_KEY: Optional[str] = None
    ASSEMBLYAI_SPEECH_MODELS: str = "universal-2"
    ASSEMBLYAI_POLL_INTERVAL_SECONDS: float = 2.0
    ASSEMBLYAI_POLL_TIMEOUT_SECONDS: int = 120

    _ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

    model_config = ConfigDict(
        env_file=str(_ENV_PATH),
        extra="ignore"
    )

    # Validate Magento credentials
    @field_validator("MAGENTO_BASE_URL", "MAGENTO_ACCESS_TOKEN")
    @classmethod
    def validate_magento_config(cls, v: Optional[str], info) -> Optional[str]:
        field_name = info.field_name
        if v is None or not v.strip():
            raise ValueError(
                f"{field_name} is required. Please set it in your .env file.\n"
                f"Example: {field_name}=your_value"
            )
        return v.strip()

    # Validate Mistral key
    @field_validator("MISTRAL_API_KEY")
    @classmethod
    def validate_mistral_key(cls, v: Optional[str]) -> str:
        if v is None or not v.strip():
            raise ValueError(
                "MISTRAL_API_KEY is required. Set it in your .env file.\n"
                "Example: MISTRAL_API_KEY=your_mistral_key"
            )
        return v.strip()


# Load settings at application startup
try:
    settings = Settings()
except ValueError as e:
    raise RuntimeError(f"Configuration Error: {e}") from e
