from __future__ import annotations

from pandas import Timestamp
from pydantic import BaseModel


class CommonTest(BaseModel):
    UUID: str
    FROM_TIME: Timestamp
    TO_TIME: Timestamp
    TEST_ENV: str
    MMM_BUILD_VERSION: str = None
    DEPLOYMENT_INFO: str = None
    MMM_DB_METRICS: str = None
    COMMENT: str = None


class ApiCuTest(CommonTest):
    IS_FE_TEST: bool = False


class ApiSuTest(CommonTest):
    SOURCE_FE_TEST: str = None


class DocFlowTest(CommonTest):
    DATA_SOURCES: str = None
    DPM_JOB_INFO: str = None
