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

    # Google Cloud
    GOOGLE_CLOUD_PROJECT: str = "moment-clone"
    GCS_BUCKET: str = "moment-clone-media"
    GCS_SIGNED_URL_EXPIRY_DAYS: int = 7

    # Inngest
    INNGEST_EVENT_KEY: str = ""
    INNGEST_SIGNING_KEY: str = ""

    # Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3-flash"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"

    # TTS
    TTS_VOICE: str = "ja-JP-Chirp3-HD-Aoede"
    TTS_LANGUAGE: str = "ja-JP"

    # Stripe (Phase 4)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_ID_MONTHLY: str = ""


settings = Settings()
