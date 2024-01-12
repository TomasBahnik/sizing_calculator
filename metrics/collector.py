import logging
from typing import Optional, List, Tuple, Dict

import pandas as pd
import pytz
import typer
from prometheus_pandas import query

from metrics.prom_ql.queries import sum_irate

from metrics import DEFAULT_TIME_DELTA_HOURS, GIBS, MIBS, DEFAULT_STEP_SEC, NON_EMPTY_LABEL, DEFAULT_RATE_INTERVAL

logger = logging.getLogger(__name__)


def mem_gibs(df: pd.DataFrame) -> pd.DataFrame:
    return (df / GIBS).round(2)


def mem_mibs(df: pd.DataFrame) -> pd.DataFrame:
    return (df / MIBS).round(2)


class TimeRange:
    def __init__(self, start_time: Optional[str] = None, end_time: Optional[str] = None,
                 delta_hours: float = DEFAULT_TIME_DELTA_HOURS):
        """
        :param start_time: fixed start time. If None, start_time = end_time - delta
        :param end_time: fixed end time. If None, end_time = now in GMT
        :param delta_hours: interval in past in hours from now
        """
        # rounded to minutes down - do not ask for future
        self.to_time = pd.Timestamp(ts_input=end_time, tz=pytz.UTC) if end_time \
            else pd.Timestamp.now(tz=pytz.UTC).floor('T')
        self.from_time = pd.Timestamp(ts_input=start_time, tz=pytz.UTC) if start_time \
            else self.to_time - pd.Timedelta(hours=delta_hours)

    def __format__(self, format_spec=''):
        return f'period: {self.from_time.isoformat()} - {self.to_time.isoformat()}\n'

    def __str__(self):
        from prometheus.common import DATE_TIME_FORMAT_FOLDER
        return f'{self.from_time.strftime(DATE_TIME_FORMAT_FOLDER)}_{self.to_time.strftime(DATE_TIME_FORMAT_FOLDER)}'


class PrometheusCollector:

    def __init__(self, url: str, time_range: TimeRange):
        self.promQuery = query.Prometheus(url)
        self.timeRange: TimeRange = time_range

    def __format__(self, format_spec=''):
        return f'url: {self.promQuery.api_url}\n' \
               f'period: {self.timeRange.from_time.isoformat()} - {self.timeRange.to_time.isoformat()}\n'

    def range_query(self, p_query: str, step_sec: float = DEFAULT_STEP_SEC) -> pd.DataFrame:
        """
        Time range query
        :param p_query: Prometheus expression
        :param step_sec: step as float if not specified DEFAULT_STEP_SEC
        :return: DataFrame with values of query
        """
        logger.info(p_query)
        df: pd.DataFrame = self.promQuery.query_range(query=p_query, start=self.timeRange.from_time,
                                                      end=self.timeRange.to_time, step=step_sec)
        return df

    def container_cpu_portal(self, namespace: str, grp_keys: List[str], rate_interval: str) -> pd.DataFrame:
        """
        CPU of pods in given namespaces grouped by grp_keys
        :param grp_keys: keys names separated by ',' without parenthesis
        :param rate_interval: period for irate
        :param namespace list of namespaces separated by |
        :return:
        """
        portal_pod_cpu_metric: str = "container_cpu_usage_seconds_total"
        q = sum_irate(metric=portal_pod_cpu_metric, containers=NON_EMPTY_LABEL,
                      namespace=namespace, grp_keys=grp_keys, rate_interval=rate_interval)
        return self.range_query(p_query=q)

    def portal_cpu_df(self, namespace: str, grp_keys: List[str]) -> pd.DataFrame:
        """Read raw df and convert its columns to tuples"""
        raw_df: pd.DataFrame = self.container_cpu_portal(namespace=namespace,
                                                         grp_keys=grp_keys, rate_interval=DEFAULT_RATE_INTERVAL)
        typer.echo(f'timerange {min(raw_df.index)} - {max(raw_df.index)}, df shape: {raw_df.shape}')
        df_tuple_columns(grp_keys, raw_df)
        return raw_df


def col_tuple(column_name: str, grp_keys: List[str]) -> Tuple[str, ...]:
    """Convert column names returned by range query with grp keys to tuples
    used as DataFrame keys
    """
    d: Dict[str] = col_dict(column_name, grp_keys=grp_keys)
    return tuple([v for v in d.values()])


def df_tuple_columns(grp_keys: List[str], raw_df):
    # covert string column names to tuples corresponding to grp_keys
    tuple_columns: List[Tuple[str, ...]] = [col_tuple(str(c), grp_keys) for c in raw_df.columns]
    raw_df.columns = tuple_columns


def col_dict(column_name: str, grp_keys: List[str]) -> dict:
    """Convert columns names returned by range query with grp keys to dict. """
    column_name = column_name.replace('=', ':')
    for key in grp_keys:
        column_name = column_name.replace(key, f'\"{key}\"')
    parts = column_name.split(',')
    filtered_parts = [p for p in parts if any([gk in p for gk in grp_keys])]
    column_name: str = ','.join(filtered_parts)
    # add ending } in case when there is more grp keys
    column_name = column_name if column_name.endswith('}') else column_name + '}'
    return eval(column_name)
