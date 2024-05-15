from __future__ import annotations

import os

from pathlib import Path
from typing import Optional

import pandas as pd

from loguru import logger

from metrics import CONTAINER_COLUMN, MIBS, NAMESPACE_COLUMN, POD_COLUMN, TIMESTAMP_COLUMN
from metrics.collector import TimeRange
from prometheus.sla_model import SlaTable
from settings import settings
from sizing.calculator import CPU_RESOURCE, MEMORY_RESOURCE
from storage.postgres.engine import PostgresEngine


time_delta = pd.Timedelta(seconds=1)
cpu_data = {
    TIMESTAMP_COLUMN: [pd.Timestamp.now() - time_delta, pd.Timestamp.now()],
    CONTAINER_COLUMN: ["container1", "container2"],
    POD_COLUMN: ["pod1", "pod2"],
    CPU_RESOURCE.limit: [1, 0.9],
    CPU_RESOURCE.request: [0.5, 0.4],
    CPU_RESOURCE.measured: [0.6, 0.7],
}
CPU_DF = pd.DataFrame(cpu_data)

mem_data = {
    TIMESTAMP_COLUMN: [pd.Timestamp.now() - time_delta, pd.Timestamp.now()],
    CONTAINER_COLUMN: ["container1", "container2"],
    POD_COLUMN: ["pod1", "pod2"],
    MEMORY_RESOURCE.limit: [10 * MIBS, 9 * MIBS],
    MEMORY_RESOURCE.request: [5 * MIBS, 4 * MIBS],
    MEMORY_RESOURCE.measured: [6 * MIBS, 7 * MIBS],
}
MEM_DF = pd.DataFrame(mem_data)


class DataLoader:
    def __init__(
        self,
        start_time: Optional[str],
        end_time: Optional[str],
        delta_hours: Optional[float] = settings.time_delta_hours,
        time_range: Optional[TimeRange] = None,
    ):
        self.startTime = start_time
        self.endTime = end_time
        self.deltaHours = delta_hours
        self.timeRange = (
            time_range if time_range else TimeRange(start_time=start_time, end_time=end_time, delta_hours=delta_hours)
        )

    def time_range_query(self, table_name: str) -> str:
        """Create query for time range."""
        lower_bound = f""""{TIMESTAMP_COLUMN}" >= '{self.timeRange.from_time}'"""
        upper_bound = f""""{TIMESTAMP_COLUMN}" <= '{self.timeRange.to_time}'"""
        q = f"SELECT * FROM {table_name} WHERE {lower_bound} AND {upper_bound}"
        return q

    def load_range_table(self, sla_table: SlaTable) -> pd.DataFrame:
        """Load df from storage table for time range."""
        # sf = SnowflakeEngine(schema=sla_table.dbSchema)
        engine = PostgresEngine()
        try:
            table_name = f'"{sla_table.tableName}"'
            table_keys = [TIMESTAMP_COLUMN] + sla_table.tableKeys if sla_table.tableKeys else []
            q = self.time_range_query(table_name=table_name)
            msg = f"Table: {table_name}, {self.timeRange}"
            logger.info(msg)
            # df: pd.DataFrame = dataframe.get_df(query=q, con=sf.connection)
            df = engine.read_df(q)
            dedup_df = df.drop_duplicates(subset=table_keys)
            removed = len(df) - len(dedup_df)
            if removed > 0:
                msg = f"Removed {removed} duplicates from {table_name}"
                logger.info(msg)
            return dedup_df
        finally:
            # sf.sf_engine.dispose()
            engine.close()

    def load_df_db(self, sla_table: SlaTable, namespace: Optional[str]) -> tuple[pd.DataFrame, tuple[str, ...]]:
        """Load data for given range from DB, optionally filter by namespace.

        Namespace has a role of higher level entity. Data is loaded only for given time range potentially
        containing more than one higher level entity (called namespace here).
        namespace = None returns the whole time range dataframe
        :param sla_table: SlaTable
        :param namespace: optional namespace filter
        :return: namespace df and list of namespaces, when namespace is None all namespaces are returned
        """
        df: pd.DataFrame = self.load_range_table(sla_table=sla_table)
        if df.empty:
            raise ValueError(f"No data for {sla_table.tableName} in {self.timeRange}")
        if namespace is None:
            return df, tuple()
        all_ns: list[str] = sorted(set(df[NAMESPACE_COLUMN]))
        if namespace is not None and namespace not in all_ns:
            raise ValueError(f"Namespace {namespace} not found in {all_ns}")
        if namespace:
            return df[df[NAMESPACE_COLUMN] == namespace], (namespace,)
        else:
            return df, tuple(all_ns)

    def save_df(self, sla_table: SlaTable, namespace: Optional[str]):
        """Save df to json file."""
        df: pd.DataFrame = self.load_df_db(sla_table=sla_table, namespace=namespace)[0]
        filename = f"{sla_table.tableName}_{str(self.timeRange)}.json"
        df_path = Path(settings.data, filename)
        msg = f"Save df with shape {df.shape} to {df_path}"
        logger.info(msg)
        os.makedirs(df_path.parent, exist_ok=True)
        df.to_json(df_path)

    def load_df_file(self, sla_table: SlaTable, df_path: Path | None) -> pd.DataFrame:
        """Load df from json file.
        :param sla_table: SlaTable, used for filename
        :param df_path: optional path to df json file.

        If df_path is None the file in settings data folder named as tableName_timeRange is used.
        """
        filename = f"{sla_table.tableName}_{str(self.timeRange)}.json"
        df_path = df_path if df_path else Path(settings.data, filename)
        if df_path.exists():
            msg = f"Load df from {df_path}"
            logger.info(msg)
            return pd.read_json(df_path)
        else:
            raise FileNotFoundError(f"File {df_path} not found")
