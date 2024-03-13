from __future__ import annotations

import os

import snowflake.connector

from loguru import logger
from pandas import DataFrame
from snowflake.connector import SnowflakeConnection
from snowflake.connector.cursor import SnowflakeCursor
from snowflake.connector.pandas_tools import write_pandas
from snowflake.sqlalchemy import URL
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from storage.snowflake import DEFAULT_SCHEMA
from storage.snowflake.queries import q_from_to_by_uuid


class SnowflakeEngine:
    DATABASE = "PERFORMANCE_TESTS"
    ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
    USER = os.getenv("SNOWFLAKE_USER")
    PASSWORD = os.getenv("SNOWFLAKE_PASSWORD")

    # The provided table name 'TEST_DF' is not found exactly as such in the database after writing the table,
    # possibly due to case sensitivity issues. Consider using lower case table names. => use lower() for pd_writer
    # even if table looks in Snowflake in upper

    def __init__(self, schema: str = DEFAULT_SCHEMA):
        self.schema = schema
        self.sf_engine: Engine = self.create_sf_engine()
        self.connection: SnowflakeConnection = self.create_con()

    def __str__(self):
        return f"account {self.ACCOUNT}, schema {self.DATABASE}.{self.schema}"

    def close(self):
        logger.info("Closing sf engine")
        self.connection.close()
        self.sf_engine.dispose()

    # 'snowflake://<user_login_name>:<password>@<account_identifier>/<database_name>/<schema_name>?warehouse=<warehouse_name>&role=<role_name>'
    def create_sf_engine(self) -> Engine:
        url = URL(
            account=self.ACCOUNT,
            user=self.USER,
            password=self.PASSWORD,
            database=self.DATABASE,
            schema=self.schema,
        )
        logger.info(f"Create {self.__class__.__name__}: {self}")
        engine = create_engine(url)
        return engine

    def create_con(self) -> SnowflakeConnection:
        con = snowflake.connector.connect(
            user=self.USER,
            password=self.PASSWORD,
            account=self.ACCOUNT,
            database=self.DATABASE,
            schema=self.schema,
        )
        return con

    def write_df(self, df: DataFrame, table: str):
        # Specify that the to_sql method should use the pd_writer function
        # to write the data from the DataFrame to the table named "stats"
        # in the Snowflake database.
        logger.info(f"Writing to table : {self.DATABASE}.{self.schema}.{table.upper()}")
        success, n_chunks, n_rows, _ = write_pandas(
            conn=self.connection,
            df=df,
            table_name=table,
            database=self.DATABASE,
            schema=self.schema,
            auto_create_table=True,
            use_logical_type=True,
        )
        logger.info(f"Success: {success}, chunks: {n_chunks}, rows: {n_rows}")

    def fetch_df(self, query: str) -> DataFrame:
        cursor: SnowflakeCursor | None = self.connection.cursor().execute(query)
        if cursor:
            df: DataFrame = cursor.fetch_pandas_all()
            return df
        else:
            raise ValueError(f"Cursor is None for query: {query}")

    def from_to_by_uuid_df(self, timestamp_field: str, table_name: str) -> DataFrame:
        """
        Generate list of tests from data table instead from list table.

        By default, list table is used in snowflake_engine.api_list
        """
        q = q_from_to_by_uuid(timestamp_field=timestamp_field, table_name=table_name)
        return self.fetch_df(query=q)

    def all_df(self, table_name: str) -> DataFrame:
        q = f"SELECT * FROM {table_name}"
        return self.fetch_df(query=q)
