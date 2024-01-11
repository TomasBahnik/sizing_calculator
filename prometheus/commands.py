import logging
from pathlib import Path
from typing import List, Tuple

import pandas as pd
import typer
import urllib3

from prometheus import const
from prometheus.collector import df_tuple_columns, TimeRange, PrometheusCollector, PROMETHEUS_URL
from prometheus.const import TIMESTAMP_COLUMN, NAMESPACE_COLUMN, NON_LINKERD_CONTAINER, NON_EMPTY_CONTAINER
from prometheus.portal import PortalPrometheus
from prometheus.prompt_model import PortalTable
from pycpt_snowflake import dataframe
from pycpt_snowflake.dataframe import add_tz
from pycpt_snowflake.engine import SnowflakeEngine

METRICS = 'metrics'
DEFAULT_LABELS = [NON_LINKERD_CONTAINER, NON_EMPTY_CONTAINER]

app = typer.Typer()
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
    sf_df_data = {const.TIMESTAMP_COLUMN: timestamps}
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


@app.command()
def last_update(namespace: str = typer.Option(..., '-n', '--namespace', help='Last update of given namespace'),
                metrics_folder: Path = typer.Option('./kubernetes/expressions/basic', "--folder", "-f",
                                                    dir_okay=True,
                                                    help="Folder with json files specifying PromQueries to run")):
    """List last timestamps per table and namespace"""
    portal_prometheus: PortalPrometheus = PortalPrometheus(folder=metrics_folder)
    portal_tables: List[PortalTable] = portal_prometheus.load_portal_tables()
    table_names = [f'{t.dbSchema}.{t.tableName}' for t in portal_tables]
    last_timestamp(table_names, namespace)


@app.command()
def portal_metrics(
        start_time: str = typer.Option(None, "--start", "-s",
                                       help="Start time of period in datetime format wo timezone "
                                            "e.g. '2023-07-20T04:43:00' UTC is added. "
                                            "If None, start_time = end_time - delta"),
        end_time: str = typer.Option(None, "--end", "-e",
                                     help="End of period in datetime format wo timezone (UTC is added) "
                                          "e.g. '2023-07-21T00:43:00'. If None, end_time = now in UTC"),
        delta_hours: float = typer.Option(const.DEFAULT_TIME_DELTA_HOURS, "--delta", "-d",
                                          help="hours in the past i.e start time = end_time - delta_hours"),
        namespaces: str = typer.Option(..., "-n", "--namespace",
                                       help=f"list of namespaces separated by | enclosed in \" "
                                            f"or using .+ e.g. for all '{const.PORTAL_ONE_NS}'"),
        metrics_folder: Path = typer.Option('./kubernetes/expressions/basic', "--folder", "-f",
                                            dir_okay=True,
                                            help="Folder with json files specifying PromQueries to run")):
    """
    Loads prom queries from `metrics_folder`, runs them and stores in Snowflake.

    Explicitly specified namespaces are preferred. Regex based ones can be huge.
    Note that double slash is needed in PromQL e.g. for digit regex `\\d+`

    There is no option for just update. It is difficult to resolve last timestamp for each namespace.
    Dedup Snowflake table instead
    https://stackoverflow.com/questions/58259580/how-to-delete-duplicate-records-in-snowflake-database-table/65743216#65743216
    """
    portal_prometheus: PortalPrometheus = PortalPrometheus(folder=metrics_folder)
    portal_tables: List[PortalTable] = portal_prometheus.load_portal_tables()
    time_range = TimeRange(start_time=start_time, end_time=end_time, delta_hours=delta_hours)
    prom_collector: PrometheusCollector = PrometheusCollector(PROMETHEUS_URL, time_range=time_range)
    for portal_table in portal_tables:
        typer.echo(f'Table: {portal_table.dbSchema}.{portal_table.tableName}, '
                   f'period: {time_range.from_time} - {time_range.to_time}')
        # new table for each Portal table
        all_series: List[pd.Series] = []
        all_columns: List[str] = []
        # grp keys ONLY on table level NOT query level - can't be mixed !!
        grp_keys: List[str] = portal_table.prepare_group_keys()
        replaced_pt: PortalTable = portal_prometheus.replace_portal_labels(portal_table=portal_table,
                                                                           labels=DEFAULT_LABELS,
                                                                           namespaces=namespaces)
        #  default = DEFAULT_STEP_SEC
        step_sec: float = portal_table.stepSec
        for prom_query in replaced_pt.queries:
            typer.echo(f'{prom_query.columnName}')
            typer.echo(f'\tquery: {prom_query.query}')
            df: pd.DataFrame = prom_collector.range_query(p_query=prom_query.query, step_sec=step_sec)
            if df.empty:
                typer.echo(f'Query returns empty data. Continue')
                continue
            sf_ser = sf_series(metric_df=df, grp_keys=grp_keys)
            all_series.append(sf_ser)
            all_columns.append(prom_query.columnName)
        # after concat, index stays the same, so we can extract common columns
        if not all_series:
            typer.echo(f'No data after all queries. Continue')
            continue
        all_data_df: pd.DataFrame = pd.concat(all_series, axis=1)
        all_data_df.columns = all_columns
        # extract common columns TIMESTAMP, NAMESPACE, POD
        common_columns_df = common_columns(stacked_df=all_data_df, grp_keys=grp_keys)
        full_df: pd.DataFrame = pd.concat([common_columns_df, all_data_df], axis=1)
        prom_save(dfs=[full_df], portal_table=portal_table)
        unique_ns = set(full_df[NAMESPACE_COLUMN])
        typer.echo(f'shape: {full_df.shape}\n'
                   f'{len(unique_ns)} unique namespaces: {unique_ns}')


if __name__ == "__main__":
    app()
