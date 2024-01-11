import logging
import os

import snowflake.connector
import typer
from pandas import DataFrame
from snowflake.connector import SnowflakeConnection
from snowflake.connector.pandas_tools import pd_writer
from snowflake.sqlalchemy import URL
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from pycpt_snowflake import DEFAULT_SCHEMA
from pycpt_snowflake.queries import q_from_to_by_uuid

logger = logging.getLogger(__name__)


class SnowflakeEngine:
    DATABASE = 'PERFORMANCE_TESTS'
    ACCOUNT = 'ef97109.eu-central-1'
    USER = os.getenv('SNOWFLAKE_USER')
    PASSWORD = os.getenv('SNOWFLAKE_PASSWORD')

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
        typer.echo(f"Closing sf engine")
        self.connection.close()
        self.sf_engine.dispose()

    # 'snowflake://<user_login_name>:<password>@<account_identifier>/<database_name>/<schema_name>?warehouse=<warehouse_name>&role=<role_name>'
    def create_sf_engine(self) -> Engine:
        url = URL(account=self.ACCOUNT, user=self.USER,
                  password=self.PASSWORD, database=self.DATABASE, schema=self.schema)
        logger.info(f"Create {self.__class__.__name__}: {self}")
        engine = create_engine(url)
        return engine

    def create_con(self) -> SnowflakeConnection:
        con = snowflake.connector.connect(
            user=self.USER,
            password=self.PASSWORD,
            account=self.ACCOUNT,
            database=self.DATABASE,
            schema=self.schema)
        return con

    def write_df(self, df: DataFrame, table: str):
        # Specify that the to_sql method should use the pd_writer function
        # to write the data from the DataFrame to the table named "stats"
        # in the Snowflake database.
        typer.echo(f"Writing to table : {self.DATABASE}.{self.schema}.{table.upper()}")
        # noinspection PyTypeChecker
        df.to_sql(name=table, con=self.sf_engine, index=False, method=pd_writer, if_exists='append')

    def from_to_by_uuid_df(self, timestamp_field: str, table_name: str) -> DataFrame:
        """
        Generates list of tests from data table instead from list table as consistency check
        By default list table is used in snowflake_engine.api_list
        """
        q = q_from_to_by_uuid(timestamp_field=timestamp_field, table_name=table_name)
        df: DataFrame = self.connection.cursor().execute(q).fetch_pandas_all()
        return df

    def all_df(self, table_name: str) -> DataFrame:
        q = f"SELECT * FROM {table_name}"
        df: DataFrame = self.connection.cursor().execute(q).fetch_pandas_all()
        return df
