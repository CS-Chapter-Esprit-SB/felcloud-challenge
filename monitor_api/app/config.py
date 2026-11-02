from __future__ import annotations

import os
from typing import ClassVar

from pydantic_settings import BaseSettings,SettingsConfigDict
from pydantic import AnyUrl



class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )
    APP_NAME: str = "Sandbox Lifecycle Manager"
    APP_VERSION: str = "0.2.0"

    AUTH0_DOMAIN: str = os.environ["AUTH0_DOMAIN"]
    AUTH0_CLIENT_ID: str = os.environ["AUTH0_CLIENT_ID"]
    AUTH0_CLIENT_SECRET: str = os.environ["AUTH0_CLIENT_SECRET"]
    AUTH0_SECRET: str = os.environ["AUTH0_SECRET"]
    AUTH0_AUDIENCE: str = os.environ["AUTH0_AUDIENCE"]

    APP_BASE_URL: str = os.environ["APP_BASE_URL"]

    IDLE_TIMEOUT_MINUTES: int = int(
        os.getenv("SANDBOX_IDLE_TIMEOUT_MINUTES", "60")
    )

    AUTO_STOP_ENABLED: bool = (
        os.getenv("SANDBOX_AUTO_STOP_ENABLED", "false").lower() == "true"
    )



settings:Settings = Settings()