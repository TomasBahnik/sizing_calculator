import os
from pathlib import Path
from typing import Dict, List

import pandas as pd
import typer

from metrics.collector import TimeRange
from prometheus.sla_model import SlaTable
from reports import PROMETHEUS_REPORT_FOLDER


def report_header(sla_table: SlaTable, time_range: TimeRange) -> str:
    data: Dict[str, List[str]] = {'table_name': [sla_table.tableName],
                                  'time_range': [f'{time_range.from_time}-{time_range.to_time}']}
    df: pd.DataFrame = pd.DataFrame(data=data)
    return df.T.to_html()


def save_rules_report(main_report: str, sla_table: SlaTable, time_range: TimeRange):
    from shared.utils import DATE_TIME_FORMAT_FOLDER
    ft = time_range.from_time.strftime(DATE_TIME_FORMAT_FOLDER)
    tt = time_range.to_time.strftime(DATE_TIME_FORMAT_FOLDER)
    folder = Path(PROMETHEUS_REPORT_FOLDER, sla_table.dbSchema, sla_table.tableName)
    os.makedirs(folder, exist_ok=True)
    html_file = Path(folder, f'{ft}_{tt}.html')
    msg = f"Writing reports to {html_file}"
    typer.echo(msg)
    with open(html_file, "w") as file:
        file.write(main_report)
