from __future__ import annotations

import pandas as pd

from loguru import logger
from pandas import DataFrame
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from settings import settings


postgres_connection: str = (
    f"{settings.postgres_user}:{settings.postgres_password}@"
    f"{settings.postgres_hostname}:{settings.postgres_port}/{settings.postgres_db}"
)


class PostgresEngine:
    def __init__(self):
        self.engine: Engine = create_engine(f"postgresql://{postgres_connection}")

    def close(self):
        logger.info(f"Closing {self.engine}")
        self.engine.dispose()

    def read_df(self, query: str) -> pd.DataFrame:
        df = pd.read_sql_query(query, con=self.engine)
        return df

    def write_df(self, df: DataFrame, table: str, schema: str):
        df.to_sql(name=table, con=self.engine, schema=schema, if_exists="append", index=False)
