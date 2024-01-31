from __future__ import annotations

import os

from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from loguru import logger

from metrics.collector import TimeRange
from prometheus.sla_model import SlaTable
from settings import settings
from test_summary.model import TestDetails, TestSummary


def sla_report_header(sla_table: SlaTable, time_range: TimeRange) -> str:
    data: Dict[str, List[str]] = {
        "table_name": [sla_table.tableName],
        "time_range": [f"{time_range.from_time}-{time_range.to_time}"],
    }
    df: pd.DataFrame = pd.DataFrame(data=data)
    return df.T.to_html()


def sla_report(main_report: str, sla_table: SlaTable, time_range: TimeRange):
    from shared.utils import DATE_TIME_FORMAT_FOLDER

    ft = time_range.from_time.strftime(DATE_TIME_FORMAT_FOLDER)
    tt = time_range.to_time.strftime(DATE_TIME_FORMAT_FOLDER)
    folder = Path(settings.prometheus_report_folder, sla_table.dbSchema, sla_table.tableName)
    os.makedirs(folder, exist_ok=True)
    html_file = Path(folder, f"{ft}_{tt}.html")
    msg = f"Writing reports to {html_file}"
    logger.info(msg)
    with open(html_file, "w") as file:
        file.write(main_report)


def sizing_calc_report_header(test_details: Optional[TestDetails], time_range: Optional[TimeRange]) -> str:
    """Report header with namespace and time range."""
    # time_range present always
    duration = (time_range.to_time - time_range.from_time).total_seconds() if time_range else 0
    samples = int(duration / settings.step_sec) + 1
    description = test_details.description if test_details else ""
    from_time: str = time_range.from_time.isoformat() if time_range else ""
    to_time: str = time_range.to_time.isoformat() if time_range else ""
    data: Dict[str, List[str]] = {
        "description": [description],
        "duration [hours]": [duration / 3600],
        "from": [from_time],
        "to": [to_time],
        "max samples": [str(samples)],
    }
    df: pd.DataFrame = pd.DataFrame(data=data)
    return df.to_html()


def sizing_calc_report(
    time_range: Optional[TimeRange],
    test_details: Optional[TestDetails],
    data: pd.DataFrame,
    folder: Path,
    file_name: str,
    test_summary: Optional[TestSummary] = None,
):
    """Create and save full report to file."""
    file_name = f"{file_name}_{str(time_range)}.html"
    report_header = (
        sizing_calc_report_header(test_details, time_range)
        if test_summary is None
        else sizing_calc_summary_header(test_summary) + "<br/>" + sizing_calc_report_header(test_details, time_range)
    )
    path = Path(folder, file_name)
    msg = f"Saving report to {path.resolve()}"
    logger.info(msg)
    with open(path, "w") as f:
        f.write(report_header + ("<br/>" + data.to_html() + "<hr>"))


def sizing_calc_summary_header(test_summary: TestSummary) -> str:
    """Test summary header."""
    data: Dict[str, List[str]] = {
        "name": [test_summary.name],
        "namespace": [test_summary.namespace],
        "catalog items": [str(test_summary.catalogItems)],
    }
    df: pd.DataFrame = pd.DataFrame(data=data)
    return df.to_html()
