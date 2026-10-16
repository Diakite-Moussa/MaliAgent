from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuration centrale de l'application.

    Toutes les valeurs sensibles/variables (clé API, URL du provider LLM,
    connexion base de données) passent par ici, jamais en dur dans le code.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"

    database_url: str = "postgresql+psycopg://maliagent:maliagent@127.0.0.1:5434/maliagent"

    # Ollama Cloud (phase MVP) — voir app/llm/providers/ollama_cloud.py
    ollama_api_key: str = ""
    ollama_base_url: str = "https://ollama.com"
    ollama_model: str = "gpt-oss:120b-cloud"
    ollama_embedding_model: str = "nomic-embed-text"

    #meta
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""
    meta_app_secret: str = ""

    # JWT (section 18.1)
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 24h

    # URL publique (factures PDF, webhooks, liens clients)
    public_base_url: str = "http://localhost:8000"

    # CORS (origines autorisées pour le dashboard commerçant)
    cors_origins: str = "http://localhost:4300,http://127.0.0.1:4300"

    # Paiements Mobile Money (V2.1 - Phase 1: simulation, Phase 2: production)
    payment_provider: str = "mock"  # "mock", "wave", "orange_money"
    payment_mode: str = "simulation"  # "simulation", "production"

    # Wave Mali (Réservé Phase 2 - Production)
    wave_api_key: str = ""
    wave_api_url: str = "https://api.wave.com/v1/checkout/sessions"
    wave_webhook_secret: str = ""

    # Orange Money Mali (Réservé Phase 2 - Production)
    orange_client_id: str = ""
    orange_client_secret: str = ""
    orange_api_url: str = "https://api.orange.com/orange-money-webpay/dev/v1"
    orange_webhook_secret: str = ""

    # Moov Money Mali (Réservé Phase 2 - Production)
    moov_client_id: str = ""
    moov_client_secret: str = ""
    moov_api_url: str = "https://api.moov-africa.ml/flooz/v1"
    moov_webhook_secret: str = ""

    # Voice & Multilingual (V0.5)
    stt_provider: str = "mock"  # "mock", "whisper_cloud"
    stt_api_key: str = ""
    stt_base_url: str = "https://api.groq.com/openai/v1"
    stt_model: str = "whisper-large-v3"

    tts_provider: str = "mock"  # "mock", "edge", "mms"
    audio_storage_dir: str = "storage/audio"

    # Sécurité Session & Cookies
    cookie_secure: bool | None = None

    # Rate Limiting Auth
    auth_rate_limit_max_attempts: int = 5
    auth_rate_limit_window_seconds: int = 60

    # Délai de grâce / validité d'une session de paiement en attente (minutes)
    payment_session_expiry_minutes: int = 15

    @property
    def allowed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.env.lower() in ("prod", "production")

    @property
    def is_cookie_secure(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.is_production

    @property
    def is_payment_simulation(self) -> bool:
        return self.payment_mode.lower() == "simulation" or self.payment_provider.lower() == "mock"


settings = Settings()


