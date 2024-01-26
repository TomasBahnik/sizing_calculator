"""This module defines the application-wide settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    A class that defines the application settings.

    Settings are automatically loaded from .env files and environment variables. The load order is:
    1. the default values here in the code
    2. .env, and then
    3. the system's environment variables.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", env_nested_delimiter="__")

    # Paths
    pycpt_home: Path = Path(__file__).parent
    pycpt_artefacts: Path = Path(pycpt_home, '../cpt_artefacts').resolve()
    sla_tables: Path = Path(pycpt_home, 'sla_tables')
    data: Path = Path(pycpt_artefacts, 'data')


# singleton instance of the Settings class. Use this instead of creating your own instance.
settings = Settings()
