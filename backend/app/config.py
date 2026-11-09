from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_SECRET_KEY_LENGTH = 32


class Settings(BaseSettings):
    """
    Settings read from environment variables, then from backend/.env.

    SECRET_KEY has no default on purpose: if it is missing, Settings() raises
    a ValidationError when this module is imported, so the app refuses to start.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Application
    APP_NAME: str = "DocuMind"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    # Passed to FastAPI(debug=...). When true, unhandled errors return a traceback
    # in the HTTP response, so it must stay off outside local development.

    # Database
    # postgresql://username:password@host:port/database_name
    # The default only matches the local container in docker-compose.yml.
    DATABASE_URL: str = "postgresql://documind_user:documind_pass@localhost:5432/documind"

    # JWT Settings
    SECRET_KEY: str
    # Signs every JWT. Anyone who knows it can forge a token for any user,
    # so it comes from the environment and is never committed.
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_long(cls, value: str) -> str:
        # Rejects an empty value too (e.g. "SECRET_KEY=" copied from .env.example).
        # HS256 uses a 256-bit key; 32 random characters is the floor we accept.
        if len(value) < MIN_SECRET_KEY_LENGTH:
            raise ValueError(
                f"SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters. "
                'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        return value


# Single instance imported everywhere
settings = Settings()
