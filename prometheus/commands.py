from __future__ import annotations

from typing import Optional

import pandas as pd
import urllib3

from loguru import logger
from sqlalchemy.exc import OperationalError

import metrics

from metrics import TIMESTAMP_COLUMN
from prometheus.sla_model import SlaTable
from storage.postgres.engine import PostgresEngine
from storage.snowflake.engine import SnowflakeEngine


METRICS = "metrics"

urllib3.disable_warnings()


def sf_save(dfs: list[pd.DataFrame], portal_table: SlaTable):
    sf = SnowflakeEngine(schema=portal_table.dbSchema)
    try:
        # Snowflake table
        # use lower case for SF table name - even if it appears in upper case in Database view
        # UserWarning: The provided table name ... is not found exactly as such in the database after writing
        # the table, possibly due to case sensitivity issues. Consider using lower case table names
        table = portal_table.tableName
        logger.info(f"Saving {len(dfs)} DataFrames to {table}.")
        for df in dfs:
            sf.write_df(df=df, table=table)
    finally:
        sf.sf_engine.dispose()


def pg_save(dfs: list[pd.DataFrame], portal_table: SlaTable):
    engine = PostgresEngine()
    try:
        table = portal_table.tableName
        logger.info(f"Saving {len(dfs)} DataFrames to {table}.")
        for df in dfs:
            engine.write_df(df=df, table=table)
    except OperationalError as e:
        logger.error(e)
    finally:
        engine.close()


def last_update_query(
    table_name: str,
    column_name: str,
    namespace: Optional[str],
    timestamp_field: str = TIMESTAMP_COLUMN,
):
    """
    Select max timestamp from table with table_name as column_name

    Use quoted identifiers to keep upper case for PG
    :param table_name: table to search for max timestamp
    :param column_name: name of the column to return
    :param timestamp_field: name of the timestamp field
    :param namespace:  optional namespace filter
    :return: SQL query
    """
    timestamp_field_quoted = f'"{timestamp_field}"'
    q = f'SELECT max({timestamp_field_quoted}) as "{column_name}" FROM {table_name}'
    if namespace is not None:
        q = q + f" WHERE \"{metrics.NAMESPACE_COLUMN}\"='{namespace}'"
    return q


def last_timestamp(table_names: list[str], namespace: Optional[str]):
    # TODO use generic abstract class for Snowflake, Postgres ...
    # sf = SnowflakeEngine()
    pg = PostgresEngine()
    # column name is used to get values
    # if quoted in query PG keeps upper case
    column_name = "MAX_TIMESTAMP"
    try:
        for table_name in table_names:
            q = last_update_query(table_name=table_name, column_name=column_name, namespace=namespace)
            logger.debug(f"Query: {q}")
            # df: pd.DataFrame = dataframe.get_df(query=q, con=sf.connection)
            df = pd.read_sql_query(q, con=pg.engine)
            try:
                max_timestamps = df[column_name].dt.tz_convert(tz="UTC")
            except TypeError as e:
                # Older version of snowflake pandas
                # TypeError: Cannot convert tz-naive timestamps, use tz_localize to localize
                max_timestamps = df[column_name].dt.tz_localize(tz="UTC")
            assert len(max_timestamps) == 1
            msg = (
                f"Last update: {table_name}[{namespace}]: {max_timestamps[0]}"
                if namespace
                else f"Last update: {table_name}: {max_timestamps[0]}"
            )
            logger.info(msg)
    finally:
        # sf.sf_engine.dispose()
        pg.close()
