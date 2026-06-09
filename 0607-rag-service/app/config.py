from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM —— chat 和 embedding 都走 OpenAI 兼容中转站
    openai_api_key: str          # 中转站 key
    openai_base_url: str         # 中转站 baseURL,通常以 /v1 结尾
    chat_model: str              # chat 模型名,如 gpt-5.4
    embedding_model: str         # embedding 模型名,如 text-embedding-3-small
    embedding_dim:int = 1536

    # Database
    database_url: str
    redis_url: str = "redis://localhost:6380/0"

    # App
    log_level: str = "INFO"
    log_json: bool = False       # True=输出 JSON(生产);False=彩色控制台(本地开发)

settings = Settings() # type: ignore[call-arg]