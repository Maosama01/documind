from typing import Literal, Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.services.chunking_service import MIN_CHUNK_WORDS, validate_chunk_settings

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

    # Chunking, measured in words
    # all-MiniLM-L6-v2 embeds at most 256 tokens per text (max_seq_length in its
    # sentence_bert_config.json, counting the [CLS] and [SEP] tokens). Anything
    # longer is cut off without an error, so the end of an oversized chunk is never
    # embedded and can never be found by search. The old 500-word chunks ran to
    # 565-660 tokens on the one PDF measured.
    # 180 words aims to stay under 256: on that PDF (930 words of English prose)
    # MiniLM's tokenizer averaged 1.35 tokens per word, and the largest 180-word
    # chunk was 255 tokens. That is one document, not a guarantee: numbers, names
    # and code produce more tokens per word, so process_document logs how many
    # chunks still exceed the limit.
    CHUNK_SIZE_WORDS: int = 180
    CHUNK_OVERLAP_WORDS: int = 30
    # Words repeated at the start of the next chunk on the same page, so text cut
    # at a boundary keeps some context. Must be at least MIN_CHUNK_WORDS (20) and
    # less than CHUNK_SIZE_WORDS; see validate_chunk_settings.

    # Answer generation for POST /query/
    LLM_PROVIDER: Literal["none", "gemini", "anthropic"] = "none"
    # "none" answers with the extractive fallback in llm_service: no external
    # call and no API key; it returns the document's own sentences.
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.8-flash"
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-opus-5-5"
    # Anthropic's most capable model, and its most expensive.
    # claude-haiku-5-5 costs less per query.
    LLM_TIMEOUT_SECONDS: float = 30.0

    @model_validator(mode="after")
    def provider_key_must_be_set(self) -> "Settings":
        # Refuse to start with a provider that cannot answer, instead of
        # failing on the first question.
        key_name = {"gemini": "GEMINI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}.get(self.LLM_PROVIDER)
        if key_name and not getattr(self, key_name):
            raise ValueError(f"LLM_PROVIDER={self.LLM_PROVIDER} needs {key_name} to be set")
        return self

    @model_validator(mode="after")
    def chunk_settings_must_be_safe(self) -> "Settings":
        # The app refuses to start with chunk settings that would crash the
        # chunker, produce no chunks, or drop words at the end of a page.
        validate_chunk_settings(self.CHUNK_SIZE_WORDS, self.CHUNK_OVERLAP_WORDS, MIN_CHUNK_WORDS)
        return self

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
