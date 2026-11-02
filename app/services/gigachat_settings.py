"""Client settings are loaded explicitly, independently of FastAPI globals."""
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class GigaChatSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GIGACHAT_", env_file=".env", env_file_encoding="utf-8-sig",
        extra="ignore", hide_input_in_errors=True, env_ignore_empty=True,
    )

    auth_key: SecretStr | None = None
    client_id: str | None = Field(default=None, repr=False)
    client_secret: SecretStr | None = None
    scope: str = "GIGACHAT_API_PERS"
    model: str = "GigaChat-2-Max"
    auth_url: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    chat_url: str = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    ca_bundle: Path | None = None
    timeout_seconds: float = Field(default=8.0, gt=0, le=180)
    cache_ttl_seconds: float = Field(default=300, ge=0, le=86400)
    max_attempts: int = Field(default=2, ge=1, le=3)

    @classmethod
    def from_env_file(cls, path: str | Path) -> "GigaChatSettings":
        env_path = Path(path).resolve()
        if not env_path.is_file():
            raise ValueError("Local environment file not found")
        settings = cls(_env_file=env_path)
        if settings.ca_bundle and not settings.ca_bundle.is_absolute():
            settings.ca_bundle = env_path.parent / settings.ca_bundle
        return settings
