"""This module defines the application-wide settings."""

from __future__ import annotations

import os

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
    pycpt_artefacts: Path = Path(pycpt_home, "../cpt_artefacts").resolve()
    sla_tables: Path = Path(pycpt_home, "sla_tables")
    data: Path = Path(pycpt_artefacts, "data")
    # test data is in the repo
    test_data: Path = Path(pycpt_home, "tests", "data")
    test_output: Path = Path(pycpt_home, "tests", "output")
    prometheus_report_folder: Path = Path(pycpt_artefacts, "prometheus")
    # keep trailing `/`
    prometheus_url: str = "http://localhost:9090/"
    prometheus_user: str = "admin"
    prometheus_password: str | None = None
    prometheus_verify_ssl: bool = False
    prometheus_db_schema: str = "public"
    postgres_user: str = os.getenv("PGUSER")
    postgres_password: str = os.getenv("PGPASSWORD")
    postgres_db: str = os.getenv("PGDATABASE")
    postgres_hostname: str = os.getenv("PGHOST")
    postgres_port: int = int(os.getenv("PGPORT"))

    # Prometheus
    time_delta_hours: float = 1  # time delta from now in hours for timeseries queries
    step_sec: float = 30  # prometheus sample step in sec

    # Snowflake
    # sf_account: str
    # sf_user: str
    # sf_password: str
    # sf_db: str
    # sf_schema: str


# singleton instance of the Settings class. Use this instead of creating your own instance.
settings = Settings()
