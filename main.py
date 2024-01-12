from pathlib import Path
from typing import List

import pandas as pd
import typer

import metrics
from metrics import PROMETHEUS_URL, NAMESPACE_COLUMN, POD_BASIC_RESOURCES_TABLE
from metrics.collector import TimeRange, PrometheusCollector
from metrics.model.tables import PortalPrometheus
from prometheus.commands import last_timestamp, DEFAULT_LABELS, sf_series, common_columns, prom_save
from prometheus.prompt_model import PortalTable
from sizing.calculator import TestTimeRange, TestDetails, TestSummary, sizing_calculator, NEW_SIZING_REPORT_FOLDER, \
    save_new_sizing, logger
from sizing.rules import DEFAULT_TIME_DELTA_HOURS, PrometheusRules, RatioRule, save_rules_report

DEFAULT_PROM_EXPRESSIONS = './expressions/basic'

app = typer.Typer()


@app.command()
def sizing_reports(start_time: str = typer.Option(None, "--start", "-s",
                                                  help="Start time in UTC without tz. "
                                                       "format: '2023-07-21T04:43:00' or '2023-09-13 16:35:00`"),
                   end_time: str = typer.Option(None, "--end", "-e", help="End time in UTC without tz"),
                   delta_hours: float = typer.Option(DEFAULT_TIME_DELTA_HOURS, "--delta", "-d",
                                                     help="hours in the past i.e start time = end_time - delta_hours"),
                   namespace: str = typer.Option(None, "--namespace", "-n", help="Only selected namespace"),
                   metrics_folder: Path = typer.Option(DEFAULT_PROM_EXPRESSIONS, "--folder", "-f",
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
                metrics_folder: Path = typer.Option(DEFAULT_PROM_EXPRESSIONS, "--folder", "-f",
                                                    dir_okay=True,
                                                    help="Folder with json files specifying PromQueries to run")):
    """List last timestamps per table and namespace"""
    portal_prometheus: PortalPrometheus = PortalPrometheus(folder=metrics_folder)
    portal_tables: List[PortalTable] = portal_prometheus.load_portal_tables()
    table_names = [f'{t.dbSchema}.{t.tableName}' for t in portal_tables]
    last_timestamp(table_names, namespace)


@app.command()
def load_metrics(
        start_time: str = typer.Option(None, "--start", "-s",
                                       help="Start time of period in datetime format wo timezone "
                                            "e.g. '2023-07-20T04:43:00' UTC is added. "
                                            "If None, start_time = end_time - delta"),
        end_time: str = typer.Option(None, "--end", "-e",
                                     help="End of period in datetime format wo timezone (UTC is added) "
                                          "e.g. '2023-07-21T00:43:00'. If None, end_time = now in UTC"),
        delta_hours: float = typer.Option(metrics.DEFAULT_TIME_DELTA_HOURS, "--delta", "-d",
                                          help="hours in the past i.e start time = end_time - delta_hours"),
        namespaces: str = typer.Option(..., "-n", "--namespace",
                                       help=f"list of namespaces separated by | enclosed in \" "
                                            f"or using .+ e.g. for all '{metrics.PORTAL_ONE_NS}'"),
        metrics_folder: Path = typer.Option(DEFAULT_PROM_EXPRESSIONS, "--folder", "-f",
                                            dir_okay=True,
                                            help="Folder with json files specifying PromQueries to run")):
    """
    Loads prom queries from `metrics_folder`, runs them and stores in Snowflake.

    Explicitly specified namespaces are preferred. Regex based ones can be huge.
    Note that double slash is needed in PromQL e.g. for digit regex `\\d+`

    There is no option for just update. It is difficult to resolve last timestamp for each namespace.
    Dedup Snowflake table instead
    https://stackoverflow.com/questions/58259580/how-to-delete-duplicate-records-in-snowflake-database-table/65743216#65743216
    """
    portal_prometheus: PortalPrometheus = PortalPrometheus(folder=metrics_folder)
    portal_tables: List[PortalTable] = portal_prometheus.load_portal_tables()
    time_range = TimeRange(start_time=start_time, end_time=end_time, delta_hours=delta_hours)
    prom_collector: PrometheusCollector = PrometheusCollector(PROMETHEUS_URL, time_range=time_range)
    for portal_table in portal_tables:
        typer.echo(f'Table: {portal_table.dbSchema}.{portal_table.tableName}, '
                   f'period: {time_range.from_time} - {time_range.to_time}')
        # new table for each Portal table
        all_series: List[pd.Series] = []
        all_columns: List[str] = []
        # grp keys ONLY on table level NOT query level - can't be mixed !!
        grp_keys: List[str] = portal_table.prepare_group_keys()
        replaced_pt: PortalTable = portal_prometheus.replace_portal_labels(portal_table=portal_table,
                                                                           labels=DEFAULT_LABELS,
                                                                           namespaces=namespaces)
        #  default = DEFAULT_STEP_SEC
        step_sec: float = portal_table.stepSec
        for prom_query in replaced_pt.queries:
            typer.echo(f'{prom_query.columnName}')
            typer.echo(f'\tquery: {prom_query.query}')
            df: pd.DataFrame = prom_collector.range_query(p_query=prom_query.query, step_sec=step_sec)
            if df.empty:
                typer.echo(f'Query returns empty data. Continue')
                continue
            sf_ser = sf_series(metric_df=df, grp_keys=grp_keys)
            all_series.append(sf_ser)
            all_columns.append(prom_query.columnName)
        # after concat, index stays the same, so we can extract common columns
        if not all_series:
            typer.echo(f'No data after all queries. Continue')
            continue
        all_data_df: pd.DataFrame = pd.concat(all_series, axis=1)
        all_data_df.columns = all_columns
        # extract common columns TIMESTAMP, NAMESPACE, POD
        common_columns_df = common_columns(stacked_df=all_data_df, grp_keys=grp_keys)
        full_df: pd.DataFrame = pd.concat([common_columns_df, all_data_df], axis=1)
        prom_save(dfs=[full_df], portal_table=portal_table)
        unique_ns = set(full_df[NAMESPACE_COLUMN])
        typer.echo(f'shape: {full_df.shape}\n'
                   f'{len(unique_ns)} unique namespaces: {unique_ns}')


@app.command()
def eval_slas(start_time: str = typer.Option(None, "--start", "-s",
                                             help="Start time in UTC without tz. "
                                                  "format: '2023-07-21T04:43:00' or '2023-09-13 16:35:00`"),
              end_time: str = typer.Option(None, "--end", "-e", help="End time in UTC without tz"),
              delta_hours: float = typer.Option(DEFAULT_TIME_DELTA_HOURS, "--delta", "-d",
                                                help="hours in the past i.e start time = end_time - delta_hours"),
              metrics_folder: Path = typer.Option(DEFAULT_PROM_EXPRESSIONS, "--folder", "-f",
                                                  dir_okay=True,
                                                  help="Folder with json files specifying PromQueries to run"),
              limit_pct: float = typer.Option(None, "-l", "--limit-pct",
                                              help="Resource above percentage of limits. Overrides value in json"),
              namespace: str = typer.Option(None, "--namespace", "-n", help="Only selected namespace")):
    """Evaluate SLAs for all tables in metrics_folder"""
    time_range = TimeRange(start_time=start_time, end_time=end_time, delta_hours=delta_hours)
    # typer.echo(f'{prom_rules}')
    portal_prometheus: PortalPrometheus = PortalPrometheus(folder=metrics_folder)
    portal_tables: List[PortalTable] = portal_prometheus.load_portal_tables()
    for portal_table in portal_tables:
        if len(portal_table.rules) == 0:
            typer.echo(f'No rules in {portal_table.name}. Continue ..')
            continue
        prom_rules: PrometheusRules = PrometheusRules(time_range=time_range, portal_table=portal_table)
        empty_report_header = prom_rules.report_header()
        main_report: str = empty_report_header
        prom_rules.load_df()
        namespaces = prom_rules.namespaces(namespace=namespace)
        for rule in portal_table.rules:
            # rule.limit_pct has default value == None
            if limit_pct:  # limit_pct is set
                # change the limit for all rules where limit_pct is already set
                # to the same value but keep those rule which do not need limit_pct None
                # number can be confusing in report
                rule.limit_pct = limit_pct if rule.limit_pct else None
            for ns in namespaces:
                typer.echo(f'namespace: {ns}, rule: {rule.resource}, limit_pct: {rule.limit_pct}, '
                           f'limit_value: {rule.resource_limit_value}, compare: {rule.compare.name}')
                ns_container_df = prom_rules.ns_container_df(namespace=ns)
                # when verify_integrity of indexes portal table specific keys are needed
                rr = RatioRule(ns_df=ns_container_df, basic_rule=rule, keys=portal_table.tableKeys)
                if portal_table.tableName == POD_BASIC_RESOURCES_TABLE:
                    # add resource request and limits only for POD_BASIC_RESOURCES table
                    main_report = rr.add_report(main_report, portal_table)
                else:
                    main_report = rr.add_report(main_report)
        if main_report != empty_report_header:
            #  do not save empty reports
            save_rules_report(main_report, portal_table, prom_rules)


if __name__ == "__main__":
    app()
