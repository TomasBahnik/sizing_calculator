import logging
from pathlib import Path
from typing import List

import pandas as pd
import typer

import metrics
from metrics import PROMETHEUS_URL, NAMESPACE_COLUMN, POD_BASIC_RESOURCES_TABLE
from metrics.collector import TimeRange, PrometheusCollector
from metrics.model.tables import SlaTables
from prometheus.commands import last_timestamp, DEFAULT_LABELS, sf_series, common_columns, prom_save
from prometheus.sla_model import SlaTable
from reports import html
from reports.html import sla_report
from shared import SLA_TABLES_FOLDER
from sizing.calculator import NEW_SIZING_REPORT_FOLDER, \
    save_new_sizing, SizingCalculator, LimitsRequests, CPU_RESOURCE, MEMORY_RESOURCE
from sizing.data import DataLoader
from sizing.rules import DEFAULT_TIME_DELTA_HOURS, RatioRule
from test_summary.model import TestSummary

DEFAULT_PROM_EXPRESSIONS = './expressions/basic'
logger: logging.Logger = logging.getLogger(__name__)
app = typer.Typer()


@app.command()
def sizing_reports(start_time: str = typer.Option(None, "--start", "-s",
                                                  help="Start time in UTC without tz. "
                                                       "format: '2023-07-21T04:43:00' or '2023-09-13 16:35:00`"),
                   end_time: str = typer.Option(None, "--end", "-e", help="End time in UTC without tz"),
                   delta_hours: float = typer.Option(DEFAULT_TIME_DELTA_HOURS, "--delta", "-d",
                                                     help="hours in the past i.e start time = end_time - delta_hours"),
                   namespace: str = typer.Option(None, "--namespace", "-n", help="Only selected namespace"),
                   folder: Path = typer.Option(SLA_TABLES_FOLDER, "--folder", "-f",
                                               dir_okay=True,
                                               help="Folder with json files specifying PromQueries to run"),
                   test_summary_json: Path = typer.Option(None, "--test-summary", "-t",
                                                          help="Test summary file with test start and end time",
                                                          file_okay=True)):
    """
    Create sizing reports for namespace and time range either from test_summary file or from command line args
    When test_summary file is provided then start_time, end_time and delta_hours are ignored
    """
    all_test_sizing: List[pd.DataFrame] = []
    sla_tables: SlaTables = SlaTables(folder=folder)
    sla_table: SlaTable = sla_tables.get_sla_table(table_name=POD_BASIC_RESOURCES_TABLE)
    if start_time is not None and end_time is not None:
        data_loader: DataLoader = DataLoader(delta_hours=delta_hours, start_time=start_time, end_time=end_time)
        ns_df, namespaces = data_loader.ns_df(sla_table=sla_table, namespace=namespace)
        # unique namespaces in df
        assert len(namespaces) == 1
        assert namespaces[0] == namespace
        cpu = LimitsRequests(ns_df=ns_df, resource=CPU_RESOURCE, sla_table=sla_table)
        memory = LimitsRequests(ns_df=ns_df, resource=MEMORY_RESOURCE, sla_table=sla_table)
        time_range = TimeRange(start_time=start_time, end_time=end_time, delta_hours=delta_hours)
        s_c = SizingCalculator(cpu=cpu, memory=memory, time_range=time_range)
        typer.echo(f'Creating sizing reports for {namespace} and {time_range}')
        common_folder = Path(NEW_SIZING_REPORT_FOLDER)
        report_folder = Path(common_folder)
        s_c.sizing_calc_all_reports(folder=report_folder, test_summary=None)
        all_test_sizing.append(s_c.new_sizing())
        save_new_sizing(all_test_sizing, common_folder, test_summary=None)

    elif test_summary_json is not None:
        test_summary: TestSummary = TestSummary.model_validate_json(json_data=test_summary_json.read_text())
        logger.info(f'Loaded test summary from {test_summary_json}')
        common_folder = Path(NEW_SIZING_REPORT_FOLDER, test_summary.name.replace(' ', '_'))
        for test_details in test_summary.tests:
            logger.info(f'Processing {test_details.description}')
            namespace = test_summary.namespace
            data_loader: DataLoader = DataLoader(time_range=test_details.testTimeRange.to_time_range(),
                                                 delta_hours=None, start_time=None, end_time=None)
            ns_df, namespaces = data_loader.ns_df(sla_table=sla_table, namespace=namespace)
            # unique namespaces in df
            assert len(namespaces) == 1
            assert namespaces[0] == namespace
            cpu = LimitsRequests(ns_df=ns_df, resource=CPU_RESOURCE, sla_table=sla_table)
            memory = LimitsRequests(ns_df=ns_df, resource=MEMORY_RESOURCE, sla_table=sla_table)
            s_c = SizingCalculator.from_test_details(cpu=cpu, memory=memory, test_details=test_details)
            folder = Path(common_folder, test_details.description.replace(' ', '_'))
            s_c.sizing_calc_all_reports(folder=folder, test_summary=test_summary)
            all_test_sizing.append(s_c.new_sizing())
        save_new_sizing(all_test_sizing, common_folder, test_summary)
    else:
        raise ValueError('Either start_time and end_time or test_summary_file must be provided')


@app.command()
def last_update(namespace: str = typer.Option(..., '-n', '--namespace', help='Last update of given namespace'),
                folder: Path = typer.Option(SLA_TABLES_FOLDER, "--folder", "-f",
                                            dir_okay=True,
                                            help="Folder with json files specifying SLA tables")):
    """List last timestamps per table and namespace"""
    sla_tables: SlaTables = SlaTables(folder=folder)
    all_sla_tables: List[SlaTable] = sla_tables.load_sla_tables()
    table_names = [f'{t.dbSchema}.{t.tableName}' for t in all_sla_tables]
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
        folder: Path = typer.Option(SLA_TABLES_FOLDER, "--folder", "-f",
                                    dir_okay=True,
                                    help="Folder with json files specifying SLA tables")):
    """
    Loads prom queries from `metrics_folder`, runs them and stores in Snowflake.

    Explicitly specified namespaces are preferred. Regex based ones can be huge.
    Note that double slash is needed in PromQL e.g. for digit regex `\\d+`

    There is no option for just update. It is difficult to resolve last timestamp for each namespace.
    Dedup Snowflake table instead
    https://stackoverflow.com/questions/58259580/how-to-delete-duplicate-records-in-snowflake-database-table/65743216#65743216
    """
    portal_prometheus: SlaTables = SlaTables(folder=folder)
    portal_tables: List[SlaTable] = portal_prometheus.load_sla_tables()
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
        replaced_pt: SlaTable = portal_prometheus.replace_portal_labels(portal_table=portal_table,
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
              folder: Path = typer.Option(SLA_TABLES_FOLDER, "--folder", "-f",
                                          dir_okay=True,
                                          help="Folder with json files specifying SLA tables"),
              limit_pct: float = typer.Option(None, "-l", "--limit-pct",
                                              help="Resource above percentage of limits. Overrides value in json"),
              namespace: str = typer.Option(None, "--namespace", "-n", help="Only selected namespace")):
    """Evaluate SLAs for all tables in metrics_folder"""
    data_loader: DataLoader = DataLoader(delta_hours=delta_hours, start_time=start_time, end_time=end_time)
    time_range = TimeRange(start_time=start_time, end_time=end_time, delta_hours=delta_hours)
    sla_tables: SlaTables = SlaTables(folder=folder)
    for sla_table in sla_tables.load_sla_tables():
        if len(sla_table.rules) == 0:
            typer.echo(f'No rules in {sla_table.name}. Continue ..')
            continue
        all_ns_df, namespaces = data_loader.ns_df(sla_table=sla_table, namespace=namespace)
        main_report: str = html.sla_report_header(sla_table=sla_table, time_range=time_range)
        for rule in sla_table.rules:
            # rule.limit_pct has default value == None
            if limit_pct:  # limit_pct is set
                # change the limit for all rules where limit_pct is already set
                # to the same value but keep those rule which do not need limit_pct None
                # number can be confusing in report
                rule.limit_pct = limit_pct if rule.limit_pct else None
            for ns in namespaces:
                typer.echo(f'namespace: {ns}, rule: {rule.resource}, limit_pct: {rule.limit_pct}, '
                           f'limit_value: {rule.resource_limit_value}, compare: {rule.compare.name}')
                ns_df = all_ns_df[all_ns_df[NAMESPACE_COLUMN] == ns]
                # when verify_integrity of indexes portal table specific keys are needed
                rr = RatioRule(ns_df=ns_df, basic_rule=rule, keys=sla_table.tableKeys)
                if sla_table.tableName == POD_BASIC_RESOURCES_TABLE:
                    # add resource request and limits only for POD_BASIC_RESOURCES table
                    main_report = rr.add_report(main_report, sla_table)
                else:
                    main_report = rr.add_report(main_report)
        if main_report != html.sla_report_header(sla_table=sla_table, time_range=time_range):
            #  do not save empty reports
            sla_report(main_report=main_report, sla_table=sla_table, time_range=time_range)


@app.command()
def load_save_df(start_time: str = typer.Option(None, "--start", "-s",
                                                help="Start time in UTC without tz. "
                                                     "format: '2023-07-21T04:43:00' or '2023-09-13 16:35:00`"),
                 end_time: str = typer.Option(None, "--end", "-e", help="End time in UTC without tz"),
                 delta_hours: float = typer.Option(DEFAULT_TIME_DELTA_HOURS, "--delta", "-d",
                                                   help="hours in the past i.e start time = end_time - delta_hours"),
                 namespace: str = typer.Option(None, "--namespace", "-n", help="Only selected namespace")):
    """Load df from DB and save it to json"""
    from sizing.data import DataLoader
    data_loader: DataLoader = DataLoader(delta_hours=delta_hours, start_time=start_time, end_time=end_time)
    sla_table = SlaTables().get_sla_table(table_name=POD_BASIC_RESOURCES_TABLE)
    data_loader.save_df(sla_table=sla_table, namespace=namespace)
    df = data_loader.load_df(sla_table=sla_table)
    typer.echo(f'Loaded {df.shape} from {data_loader.timeRange}')


if __name__ == "__main__":
    app()
