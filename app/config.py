from pydantic import field_validator
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

    @field_validator("default_domain_id", "default_group_id", "default_source_id", mode="before")
    @classmethod
    def empty_default_ids_are_none(cls, value):
        return None if value == "" else value


settings = Settings()