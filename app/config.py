from secrets import token_urlsafe

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    keitaro_url: str = "https://tlgk.host"
    keitaro_api_key: str = ""
    database_url: str = "sqlite:///./adrobot.db"
    default_domain_id: int | None = None
    default_group_id: int | None = None
    default_source_id: int | None = None
    redirect_url: str = "https://www.google.com"
    admin_username: str = ""
    admin_password_hash: str = ""
    session_secret_key: str = Field(default_factory=lambda: token_urlsafe(48))
    session_cookie_secure: bool = False

    @field_validator("default_domain_id", "default_group_id", "default_source_id", mode="before")
    @classmethod
    def empty_default_ids_are_none(cls, value):
        return None if value == "" else value

    @field_validator("session_secret_key", mode="before")
    @classmethod
    def generate_session_key_if_empty(cls, value):
        return value or token_urlsafe(48)


settings = Settings()