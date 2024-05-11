from __future__ import annotations

from enum import StrEnum
from typing import Optional

from loguru import logger
from pydantic import BaseModel

from prometheus.prompt_model import ColumnPromExpression
from settings import settings


class Compare(StrEnum):
    GREATER: str = ">"
    LESS: str = "<"
    EQUAL: str = "="
    # value(end_time) - value(start_time)
    DELTA: str = "delta"


class BasicSla(BaseModel):
    resource: str
    resource_limit_column: str = ""
    limit_pct: float = 0
    # compare if resource is greater or lower
    resource_limit_value: float = 0
    # default compare, business ready has 0 = false, 1 = true and compares < 1
    compare: Compare = Compare.GREATER


class SlaTable(BaseModel):
    """
    Prometheus' expressions with SLAs to Snowflake table
    queries correspond to (Snowflake) table columns
    """

    name: str
    tableName: str
    dbSchema: str = settings.prometheus_db_schema
    tableKeys: list[str] = []
    stepSec: float = settings.step_sec
    groupBy: list[str] = []
    defaultLabels: list[str] = []
    queries: list[ColumnPromExpression] = []
    rules: list[BasicSla] = []

    # override BaseModel's __init__ to prepare groupBy keys
    # self is not available fields definition
    def __init__(self, **data):
        super().__init__(**data)
        self.tableKeys = [k.upper() for k in self.prepare_group_keys()]

    def prepare_group_keys(self) -> list[str]:
        """
        Strips trailing/leading whitespaces.
        The order of groupBy keys irrelevant - Prometheus returns columns in alphabetical order
        """
        return sorted({gk.strip() for gk in self.groupBy})

    def replace_labels(
        self,
        namespace: Optional[str],
        debug: bool = False,
    ):
        """
        Replace `groupBy`, `rateInterval` and `labels` placeholders
        groupBy is taken from PortalTable
        rateInterval is part of the query definition in json file
        labels are passed as argument or from PromQuery
        """
        for prom_query in self.queries:
            grp_by_list: list[str] = self.prepare_group_keys()
            use_group_by: str = f'{",".join(grp_by_list)}'
            prom_query.query = prom_query.query.replace("groupBy", use_group_by)
            # set for queries with rate, increase - presence indicates usage
            if prom_query.rateInterval:
                prom_query.query = prom_query.query.replace("rateInterval", prom_query.rateInterval)
            ns_label = f'namespace="{namespace}"' if namespace is not None else None
            use_labels_list = prom_query.labels if prom_query.labels else self.defaultLabels
            all_labels_list = [ns_label] + use_labels_list if ns_label is not None else use_labels_list
            use_labels = ",".join(all_labels_list)
            # staticLabels is by default empty list no need to check for None
            static_labels = ",".join(prom_query.staticLabels)
            if static_labels:
                use_labels = use_labels + "," + static_labels if use_labels else static_labels
            prom_query.query = prom_query.query.replace("labels", use_labels)
            if debug:
                logger.info(f"{prom_query.columnName}")
                logger.info(f"query          : {prom_query.query}")
