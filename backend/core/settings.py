from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = ""

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_SECRET_KEY: str = ""  # sb_secret_* — server-side admin operations

    # Clerk
    CLERK_SECRET_KEY: str = ""
    CLERK_WEBHOOK_SECRET: str = ""
    CLERK_JWKS_URL: str = ""
    CLERK_AUDIENCE: str = ""  # optional; set to verify JWT aud claim
    CLERK_ISSUER: str = ""  # optional; set to verify JWT iss claim (e.g. https://<clerk-domain>)

    # CORS — comma-separated list of allowed origins
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"

    # Google Cloud
    GOOGLE_CLOUD_PROJECT: str = ""
    GCS_BUCKET: str = ""
    GCS_SIGNED_URL_EXPIRY_DAYS: int = 7

    # Inngest
    INNGEST_EVENT_KEY: str = ""
    INNGEST_SIGNING_KEY: str = ""

    # Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3-flash-preview"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"

    # TTS
    TTS_VOICE: str = "ja-JP-Chirp3-HD-Aoede"
    TTS_LANGUAGE: str = "ja-JP"

    # Stripe (Phase 4)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_ID_MONTHLY: str = ""

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
