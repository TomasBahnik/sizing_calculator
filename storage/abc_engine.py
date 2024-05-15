from __future__ import annotations

import abc

import pandas as pd


class AbstractEngine(abc.ABC):

    @abc.abstractmethod
    def close(self):
        """Close connections in finally block"""

    @abc.abstractmethod
    def read_df(self, query: str) -> pd.DataFrame:
        """Read from database via query."""

    @abc.abstractmethod
    def write_df(self, df: pd.DataFrame, table: str, schema: str):
        """Write DataFrame to database to table in schema."""
