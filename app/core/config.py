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


settings = Settings()
