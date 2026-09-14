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

    @property
    def allowed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()

