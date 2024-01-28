import os
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import typer
from loguru import logger

from metrics import TIMESTAMP_COLUMN, CONTAINER_COLUMN, POD_COLUMN, MIBS, NAMESPACE_COLUMN
from metrics.collector import TimeRange
from prometheus.sla_model import SlaTable
from settings import settings
from sizing.calculator import CPU_RESOURCE, MEMORY_RESOURCE
from storage.snowflake import dataframe
from storage.snowflake.engine import SnowflakeEngine

time_delta = pd.Timedelta(seconds=1)
cpu_data = {TIMESTAMP_COLUMN: [pd.Timestamp.now() - time_delta, pd.Timestamp.now()],
            CONTAINER_COLUMN: ['container1', 'container2'],
            POD_COLUMN: ['pod1', 'pod2'],
            CPU_RESOURCE.limit: [1, 0.9],
            CPU_RESOURCE.request: [0.5, 0.4],
            CPU_RESOURCE.measured: [0.6, 0.7]}
CPU_DF = pd.DataFrame(cpu_data)

mem_data = {TIMESTAMP_COLUMN: [pd.Timestamp.now() - time_delta, pd.Timestamp.now()],
            CONTAINER_COLUMN: ['container1', 'container2'],
            POD_COLUMN: ['pod1', 'pod2'],
            MEMORY_RESOURCE.limit: [10 * MIBS, 9 * MIBS],
            MEMORY_RESOURCE.request: [5 * MIBS, 4 * MIBS],
            MEMORY_RESOURCE.measured: [6 * MIBS, 7 * MIBS]}
MEM_DF = pd.DataFrame(mem_data)
DATA_FOLDER = Path(settings.pycpt_artefacts, 'data')


class DataLoader:
    def __init__(self,
                 delta_hours: Optional[float],
                 start_time: Optional[str],
                 end_time: Optional[str],
                 time_range: Optional[TimeRange] = None):
        self.startTime = start_time
        self.endTime = end_time
        self.deltaHours = delta_hours
        self.timeRange = time_range if time_range else \
            TimeRange(start_time=start_time, end_time=end_time, delta_hours=delta_hours)

    def time_range_query(self, table_name: str):
        lower_bound = f""""{TIMESTAMP_COLUMN}" >= '{self.timeRange.from_time}'"""
        upper_bound = f""""{TIMESTAMP_COLUMN}" <= '{self.timeRange.to_time}'"""
        q = f"SELECT * FROM {table_name} WHERE {lower_bound} AND {upper_bound}"
        return q

    def load_range_table(self, sla_table: SlaTable) -> pd.DataFrame:
        sf = SnowflakeEngine(schema=sla_table.dbSchema)
        try:
            table_name = sla_table.tableName
            table_keys = [TIMESTAMP_COLUMN] + sla_table.tableKeys
            q = self.time_range_query(table_name=table_name)
            msg = f'Snowflake table: {sf.schema}.{table_name}, {self.timeRange}'
            logger.info(msg)
            df: pd.DataFrame = dataframe.get_df(query=q, con=sf.connection)
            dedup_df = df.drop_duplicates(subset=table_keys)
            removed = len(df) - len(dedup_df)
            if removed > 0:
                msg = f'Removed {removed} duplicates from {table_name}'
                typer.echo(message=msg)
                logger.info(msg)
            return dedup_df
        finally:
            sf.sf_engine.dispose()

    def ns_df(self, sla_table: SlaTable, namespace: Optional[str]) -> (pd.DataFrame, Tuple[str]):
        """Optionally filter time range df by namespace
        :param sla_table: SlaTable
        :param namespace: optional namespace filter
        :return: namespace df and list of namespaces, when namespace is None all namespaces are returned
        """
        df = self.load_range_table(sla_table=sla_table)
        all_ns = sorted(set(df[NAMESPACE_COLUMN]))
        if namespace and namespace not in all_ns:
            raise ValueError(f'Namespace {namespace} not found in {all_ns}')
        if namespace:
            return df[df[NAMESPACE_COLUMN] == namespace], (namespace,)
        else:
            return df, tuple(all_ns)

    def save_df(self, sla_table: SlaTable, namespace: Optional[str]):
        """Save df to json file"""
        df: pd.DataFrame = self.ns_df(sla_table=sla_table, namespace=namespace)
        filename = f'{sla_table.tableName}_{str(self.timeRange)}.json'
        df_path = Path(DATA_FOLDER, filename)
        msg = f'Save df with shape {df.shape} to {df_path}'
        typer.echo(message=msg)
        logger.info(msg)
        os.makedirs(df_path.parent, exist_ok=True)
        df.to_json(df_path)

    def load_df(self, sla_table: SlaTable) -> pd.DataFrame:
        """Load df from json file named as table name and time range located in data folder"""
        filename = f'{sla_table.tableName}_{str(self.timeRange)}.json'
        df_path = Path(DATA_FOLDER, filename)
        if df_path.exists():
            msg = f'Load df from {df_path}'
            typer.echo(message=msg)
            logger.info(msg)
            return pd.read_json(df_path)
        else:
            raise FileNotFoundError(f'File {df_path} not found')
