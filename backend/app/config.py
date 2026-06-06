from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "DocuMind"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Database
    # This is the connection string PostgreSQL uses:
    # postgresql://username:password@host:port/database_name
    DATABASE_URL: str = "postgresql://documind_user:documind_pass@localhost:5432/documind"

    # JWT Settings
    SECRET_KEY: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Single instance imported everywhere
settings = Settings()
