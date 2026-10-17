from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "literature-reader-backend"
    app_version: str = "0.1.0"
    debug: bool = False
    gigachat_api_key: str | None = None


settings = Settings()