from enum import StrEnum
from typing import List

from pydantic import BaseModel

from metrics import DEFAULT_STEP_SEC, DEFAULT_PORTAL_GRP_KEYS
from prometheus.prompt_model import PortalPromQuery


class Compare(StrEnum):
    GREATER = ">"
    LESS = "<"
    EQUAL = "="
    # value(end_time) - value(start_time)
    DELTA = "delta"


class BasicSla(BaseModel):
    resource: str
    resource_limit_column: str = None
    limit_pct: float = None
    # compare if resource is greater or lower
    resource_limit_value: float = None
    # default compare, business ready has 0 = false, 1 = true and compares < 1
    compare = Compare.GREATER


class SlaTable(BaseModel):
    """
    Prometheus' expressions with SLAs to Snowflake table
    queries correspond to (Snowflake) table columns
    """
    name: str
    tableName: str
    # e.g. minio_cluster_capacity has no container/pod and sets "useGroupByDefaults": false
    useGroupByDefaults: bool = True
    dbSchema: str = 'PORTAL'
    # dbSchema: str = 'ONDEMAND'
    tableKeys: List[str] = None
    stepSec: float = DEFAULT_STEP_SEC
    groupBy: List[str] = DEFAULT_PORTAL_GRP_KEYS if useGroupByDefaults else []
    queries: List[PortalPromQuery] = []
    rules: List[BasicSla] = []

    def __init__(self, **data):
        super().__init__(**data)
        self.tableKeys = [k.upper() for k in self.prepare_group_keys()]

    def prepare_group_keys(self) -> List[str]:
        """
        Strips trailing/leading whitespaces.
        The order of groupBy keys irrelevant - Prometheus returns columns in alphabetical order
        Ensure that DEFAULT_PORTAL_GRP_KEYS are always present. Exclude possible duplicates using `set`
        and subsequent sorted created ordered list
        """
        grp_keys: List[str] = DEFAULT_PORTAL_GRP_KEYS + self.groupBy if self.useGroupByDefaults else self.groupBy
        grp_keys: List[str] = sorted(set([gk.strip() for gk in grp_keys]))
        return grp_keys
