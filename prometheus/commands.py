import logging
from typing import List, Tuple

import pandas as pd
import typer
import urllib3

import metrics
from metrics import TIMESTAMP_COLUMN, NON_EMPTY_CONTAINER
from metrics.collector import df_tuple_columns
from prometheus.const import NON_LINKERD_CONTAINER
from prometheus.prompt_model import PortalTable
from pycpt_snowflake import dataframe
from pycpt_snowflake.dataframe import add_tz
from pycpt_snowflake.engine import SnowflakeEngine

METRICS = 'metrics'
DEFAULT_LABELS = [NON_LINKERD_CONTAINER, NON_EMPTY_CONTAINER]

logger = logging.getLogger(__name__)
urllib3.disable_warnings()


def prom_save(dfs: List[pd.DataFrame], portal_table: PortalTable):
    sf = SnowflakeEngine(schema=portal_table.dbSchema)
    try:
        # Snowflake table
        # use lower case for SF table name - even if it appears in upper case in Database view
        # UserWarning: The provided table name ... is not found exactly as such in the database after writing
        # the table, possibly due to case sensitivity issues. Consider using lower case table names
        table = portal_table.tableName.lower()
        typer.echo(f'Saving {len(dfs)} DataFrames to {table.upper()}')
        for df in dfs:
            sf.write_df(df=df, table=table)
    finally:
        sf.sf_engine.dispose()


def stack_timestamps(df: pd.DataFrame, columns_to_tuple: bool) -> pd.Series:
    """
    Stack the prescribed level(s) from columns to index
    transpose df has single level column - timestamp
    if the columns have a single level, the output is a Series
    dropna = True by default
    When reading from json file columns are strings and needs to be converted to tuples
    :param df: Dataframe from Prometheus API
    :param columns_to_tuple to covert string columns to tuples
    :return: DataFrame to store in snowflake
    """
    localized_ts = add_tz(pd.Series(df.index))
    df.index = localized_ts
    # (ns, pod)
    tuple_columns: List[Tuple[str, ...]] = [eval(c) for c in df.columns] if columns_to_tuple else df.columns
    multi_idx = pd.MultiIndex.from_tuples(tuple_columns)
    df.columns = multi_idx
    stacked: pd.Series = df.T.stack(dropna=False)
    return stacked


def common_columns(stacked_df: pd.DataFrame, grp_keys: List[str]):
    """ Extract first columns used as MultiIndex
        (namespace, pod, timestamp)
    """
    idx_list: List[str, str, pd.Timestamp] = stacked_df.index.to_list()
    #  timestamps are last - because of stack
    timestamps = [t[len(grp_keys)] for t in idx_list]
    sf_df_data = {metrics.TIMESTAMP_COLUMN: timestamps}
    for i in range(len(grp_keys)):
        key: str = grp_keys[i].upper()
        values = [t[i] for t in idx_list]
        sf_df_data[key] = values
    sf_df: pd.DataFrame = pd.DataFrame(sf_df_data, index=stacked_df.index)
    return sf_df


def sf_series(metric_df: pd.DataFrame, grp_keys: list[str]) -> pd.Series:
    """ Add tuple columns and move timestamps to index"""
    df_tuple_columns(grp_keys, metric_df)
    return stack_timestamps(metric_df, columns_to_tuple=False)


def last_ns_update_query(table_name: str, column_name: str, namespace: str,
                         timestamp_field: str = TIMESTAMP_COLUMN):
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


def last_timestamp(table_names: List[str], namespace: str):
    sf = SnowflakeEngine()
    # column name is used to get values
    column_name = 'MAX_TIMESTAMP'
    try:
        for table_name in table_names:
            q = last_ns_update_query(table_name=table_name, column_name=column_name, namespace=namespace)
            df: pd.DataFrame = dataframe.get_df(query=q, con=sf.connection)
            max_timestamps = df[column_name].values
            assert len(max_timestamps) == 1
            typer.echo(f'Last update: {table_name}.{namespace}: {max_timestamps[0]}')
            # return str(max_timestamps[0])
    finally:
        sf.sf_engine.dispose()
