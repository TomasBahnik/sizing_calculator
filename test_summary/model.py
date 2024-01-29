"""Model for reading test summary json files"""

from __future__ import annotations

import datetime

from typing import List

from pydantic import BaseModel

from metrics.collector import TimeRange


class TestTimeRange(BaseModel):
    """Test time range"""

    start: datetime.datetime
    end: datetime.datetime

    def to_time_range(self) -> TimeRange:
        return TimeRange.from_timestamps(from_time=self.start, to_time=self.end)


class TestDetails(BaseModel):
    """Test result"""

    testTimeRange: TestTimeRange
    description: str


class TestSummary(BaseModel):
    """Summary of test run"""

    name: str
    namespace: str
    catalogItems: int
    tests: List[TestDetails] = []
