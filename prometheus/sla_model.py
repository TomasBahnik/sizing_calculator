from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from metrics import DEFAULT_KUBE_GRP_KEYS
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
    dbSchema: str = "PORTAL"
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
        grp_keys: list[str] = self.groupBy
        grp_keys = sorted({gk.strip() for gk in grp_keys})
        return grp_keys

    @classmethod
    def dummy(cls) -> SlaTable:
        return SlaTable(name="dummy", tableName="dummy")
