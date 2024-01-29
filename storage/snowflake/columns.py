from __future__ import annotations

from typing import Optional

from pandas import Timestamp
from pydantic import BaseModel


class CommonTest(BaseModel):
    UUID: str
    FROM_TIME: Timestamp
    TO_TIME: Timestamp
    TEST_ENV: str
    MMM_BUILD_VERSION: Optional[str] = None
    DEPLOYMENT_INFO: Optional[str] = None
    MMM_DB_METRICS: Optional[str] = None
    COMMENT: Optional[str] = None


class ApiCuTest(CommonTest):
    IS_FE_TEST: bool = False


class ApiSuTest(CommonTest):
    SOURCE_FE_TEST: Optional[str] = None


class DocFlowTest(CommonTest):
    DATA_SOURCES: Optional[str] = None
    DPM_JOB_INFO: Optional[str] = None
