from __future__ import annotations

from typing import List

import pandas as pd
from pydantic import BaseModel

from metrics.collector import TimeRange


class TestTimeRange(BaseModel):
    """Test time range"""
    start: pd.Timestamp
    end: pd.Timestamp

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
