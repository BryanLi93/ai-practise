from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    google_api_key: str
    chat_model: str 
    embedding_model: str
    embedding_dim:int = 1536

    # Database
    database_url: str

    # App
    log_level: str = "INFO"

settings = Settings() # type: ignore[call-arg]