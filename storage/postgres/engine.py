from __future__ import annotations

import pandas as pd
import typer

from sqlalchemy import create_engine

from settings import settings


class PostgresEngine:
    def __init__(self):
        self.engine = create_engine(f"postgresql://{settings.postgres_connection}")

    def close(self):
        typer.echo(f"Closing engine")
        self.engine.dispose()

    def read_df(self, query: str) -> pd.DataFrame:
        df = pd.read_sql_query(query, con=self.engine)
        return df
