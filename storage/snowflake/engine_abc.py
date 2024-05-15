from __future__ import annotations

import pandas as pd
import snowflake.connector

from loguru import logger
from snowflake.connector import SnowflakeConnection
from snowflake.connector.pandas_tools import write_pandas
from snowflake.sqlalchemy import URL
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from storage.abc_engine import AbstractEngine
from storage.snowflake import dataframe


class SnowflakeEngine(AbstractEngine):

    def __init__(self, account: str, db: str, schema: str, user: str, password: str):
        self.schema = schema
        self.account = account
        self.db = db
        self.user = user
        self.password = password
        self.engine: Engine = self.create_engine()
        self.connection: SnowflakeConnection = self.create_con()

    def close(self):
        self.connection.close()
        self.engine.dispose()

    def read_df(self, query: str) -> pd.DataFrame:
        return dataframe.get_df(query=query, con=self.connection)

    def write_df(self, df: pd.DataFrame, table: str, schema: str):
        # The to_sql method should use the pd_writer function
        # write_pandas is used because of type resolution
        logger.info(f"Writing to table : {self.db}.{self.schema}.{table.upper()}")
        success, n_chunks, n_rows, _ = write_pandas(
            conn=self.connection,
            df=df,
            table_name=table,
            database=self.db,
            schema=self.schema,
            auto_create_table=True,
            use_logical_type=True,
        )
        logger.info(f"Success: {success}, chunks: {n_chunks}, rows: {n_rows}")

    def create_engine(self) -> Engine:
        """Create Engine from URL.
        snowflake://<user_login_name>:<password>@<account_identifier>/<database_name>/<schema_name>?warehouse=<warehouse_name>&role=<role_name>'

        """
        url = URL(
            account=self.account,
            database=self.db,
            schema=self.schema,
            user=self.user,
            password=self.password,
        )
        engine = create_engine(url)
        logger.info(f"Create Snowflake engine:  {engine}")
        return engine

    def create_con(self) -> SnowflakeConnection:
        con = snowflake.connector.connect(
            user=self.user,
            password=self.password,
            account=self.account,
            database=self.db,
            schema=self.schema,
        )
        logger.info(f"Create Snowflake connection:  {con}")
        return con
