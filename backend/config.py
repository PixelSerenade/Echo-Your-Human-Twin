import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(ENV_PATH)

class Settings(BaseSettings):
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8003"))
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "true").lower() in ("true", "1", "yes")
    MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
    VAPID_PUBLIC_KEY: str = os.getenv("VAPID_PUBLIC_KEY", "")
    VAPID_PRIVATE_KEY_PATH: str = os.getenv("VAPID_PRIVATE_KEY_PATH", "")
    VAPID_SUBJECT: str = os.getenv("VAPID_SUBJECT", "mailto:admin@example.com")
    UPLOAD_DIR: str = os.getenv(
        "UPLOAD_DIR", os.path.join(os.path.dirname(__file__), "data", "uploads")
    )

    model_config = {
        "env_file": ".env",
        "extra": "allow"
    }

settings = Settings()

if settings.VAPID_PRIVATE_KEY_PATH and not os.path.isabs(settings.VAPID_PRIVATE_KEY_PATH):
    settings.VAPID_PRIVATE_KEY_PATH = os.path.join(os.path.dirname(__file__), settings.VAPID_PRIVATE_KEY_PATH)
