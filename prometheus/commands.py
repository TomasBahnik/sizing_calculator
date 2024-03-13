from __future__ import annotations

import pandas as pd
import urllib3

from loguru import logger

from metrics import NON_EMPTY_CONTAINER, TIMESTAMP_COLUMN
from prometheus import NON_LINKERD_CONTAINER
from prometheus.sla_model import SlaTable
from storage.snowflake import dataframe
from storage.snowflake.engine import SnowflakeEngine


METRICS = "metrics"
DEFAULT_LABELS = [NON_LINKERD_CONTAINER, NON_EMPTY_CONTAINER]


urllib3.disable_warnings()


def prom_save(dfs: list[pd.DataFrame], portal_table: SlaTable):
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


def last_ns_update_query(
    table_name: str,
    column_name: str,
    namespace: str,
    timestamp_field: str = TIMESTAMP_COLUMN,
):
    """
    select NAMESPACE, max(TIMESTAMP) as LAST_UPDATE
    from PORTAL.POD_BASIC_RESOURCES
    WHERE NAMESPACE = 'one-b59x5'
    GROUP BY NAMESPACE;
    :param table_name:
    :param column_name:
    :param timestamp_field:
    :param namespace:
    :return:
    """
    q = f"SELECT max({timestamp_field}) as {column_name} FROM {table_name} WHERE NAMESPACE='{namespace}'"
    return q


def last_timestamp(table_names: list[str], namespace: str):
    sf = SnowflakeEngine()
    # column name is used to get values
    column_name = "MAX_TIMESTAMP"
    try:
        for table_name in table_names:
            q = last_ns_update_query(table_name=table_name, column_name=column_name, namespace=namespace)
            df: pd.DataFrame = dataframe.get_df(query=q, con=sf.connection)
            max_timestamps = df[column_name].values
            assert len(max_timestamps) == 1
            logger.info(f"Last update: {table_name}.{namespace}: {max_timestamps[0]}")
            # return str(max_timestamps[0])
    finally:
        sf.sf_engine.dispose()
