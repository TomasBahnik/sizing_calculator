from pathlib import Path
from typing import List

import pandas as pd
import typer

from metrics import DEFAULT_TIME_DELTA_HOURS
from metrics.collector import TimeRange
from metrics.model.tables import PortalPrometheus
from prometheus.commands import last_timestamp
from prometheus.prompt_model import PortalTable
from sizing.calculator import TestTimeRange, TestDetails, TestSummary, sizing_calculator, NEW_SIZING_REPORT_FOLDER, \
    save_new_sizing, logger

EXPRESSIONS_BASIC = './expressions/basic'

app = typer.Typer()


@app.command()
def sizing_reports(start_time: str = typer.Option(None, "--start", "-s",
                                                  help="Start time in UTC without tz. "
                                                       "format: '2023-07-21T04:43:00' or '2023-09-13 16:35:00`"),
                   end_time: str = typer.Option(None, "--end", "-e", help="End time in UTC without tz"),
                   delta_hours: float = typer.Option(DEFAULT_TIME_DELTA_HOURS, "--delta", "-d",
                                                     help="hours in the past i.e start time = end_time - delta_hours"),
                   namespace: str = typer.Option(None, "--namespace", "-n", help="Only selected namespace"),
                   metrics_folder: Path = typer.Option(EXPRESSIONS_BASIC, "--folder", "-f",
                                                       dir_okay=True,
                                                       help="Folder with json files specifying PromQueries to run"),
                   test_summary_file: Path = typer.Option(None, "--test-summary", "-t",
                                                          help="Test summary file with test start and end time",
                                                          file_okay=True)):
    """
    Create sizing reports for namespace and time range either from test_summary file or from command line args
    When test_summary file is provided then start_time, end_time and delta_hours are ignored
    """
    all_test_sizing: List[pd.DataFrame] = []
    if start_time is not None and end_time is not None:
        time_range = TimeRange(start_time=start_time, end_time=end_time, delta_hours=delta_hours)
        test_name = f'{namespace if namespace is not None else "all"}_{str(time_range)}'
        test_time_range = TestTimeRange(start=time_range.from_time, end=time_range.to_time)
        test_details = TestDetails(timeRange=test_time_range, description=test_name)
        test_summary = TestSummary(name=test_name, namespace=namespace, catalogItems=1, tests=[test_details])
        s_c = sizing_calculator(start_time=test_time_range.start.isoformat(),
                                end_time=test_time_range.end.isoformat(),
                                delta_hours=delta_hours,
                                metrics_folder=metrics_folder, namespace=namespace, test_details=test_details)
        common_folder = Path(NEW_SIZING_REPORT_FOLDER, test_summary.name.replace(' ', '_'))
        folder = Path(common_folder, test_details.description.replace(' ', '_'))
        s_c.all_reports(folder=folder, test_summary=test_summary)
        all_test_sizing.append(s_c.new_sizing())
        save_new_sizing(all_test_sizing, common_folder, test_summary)

    elif test_summary_file is not None:
        test_summary: TestSummary = TestSummary.parse_file(test_summary_file)
        logger.info(f'Loaded test summary from {test_summary_file}')
        common_folder = Path(NEW_SIZING_REPORT_FOLDER, test_summary.name.replace(' ', '_'))
        for test_details in test_summary.tests:
            logger.info(f'Processing {test_details.description}')
            start_time = test_details.timeRange.start
            end_time = test_details.timeRange.end
            delta_hours = (end_time - start_time).total_seconds() / 3600
            namespace = test_summary.namespace
            s_c = sizing_calculator(start_time=start_time.isoformat(), end_time=end_time.isoformat(),
                                    delta_hours=delta_hours,
                                    metrics_folder=metrics_folder, namespace=namespace, test_details=test_details)
            folder = Path(common_folder, test_details.description.replace(' ', '_'))
            s_c.all_reports(folder=folder, test_summary=test_summary)
            all_test_sizing.append(s_c.new_sizing())
        save_new_sizing(all_test_sizing, common_folder, test_summary)
    else:
        raise ValueError('Either start_time and end_time or test_summary_file must be provided')


@app.command()
def last_update(namespace: str = typer.Option(..., '-n', '--namespace', help='Last update of given namespace'),
                metrics_folder: Path = typer.Option(EXPRESSIONS_BASIC, "--folder", "-f",
                                                    dir_okay=True,
                                                    help="Folder with json files specifying PromQueries to run")):
    """List last timestamps per table and namespace"""
    portal_prometheus: PortalPrometheus = PortalPrometheus(folder=metrics_folder)
    portal_tables: List[PortalTable] = portal_prometheus.load_portal_tables()
    table_names = [f'{t.dbSchema}.{t.tableName}' for t in portal_tables]
    last_timestamp(table_names, namespace)


if __name__ == "__main__":
    app()
