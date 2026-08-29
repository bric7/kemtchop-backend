from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

class Settings(BaseSettings):
    # API Settings
    PROJECT_NAME: str = "KemTchop API"
    VERSION: str = "2.0.0"
    API_V1_STR: str = ""

    # Security
    SECRET_KEY: str
    ADMIN_SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days

    # Database
    DATABASE_URL: str = "sqlite:///./dev-fallback.db"

    # Cloudinary
    CLOUDINARY_CLOUD_NAME: Optional[str] = None
    CLOUDINARY_API_KEY: Optional[str] = None
    CLOUDINARY_API_SECRET: Optional[str] = None

    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:8081",
        "exp://*",
        "https://*.expo.dev"
    ]

    # Environment
    ENV: str = "development"
    BASE_URL: str = "http://localhost:8000"
    MEDIA_BASE_URL: str = "https://tchopiol-production.up.railway.app"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
