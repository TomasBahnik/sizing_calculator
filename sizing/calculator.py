from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Dict, Optional

import pandas as pd
import typer
from pydantic import BaseModel

from metrics import DEFAULT_STEP_SEC, CONTAINER_COLUMN, MIBS, TIMESTAMP_COLUMN, NAMESPACE_COLUMN, \
    POD_BASIC_RESOURCES_TABLE
from metrics.collector import TimeRange
from metrics.model.tables import PortalPrometheus
from prometheus.sla_model import SlaTable
from shared import PYCPT_HOME
from sizing import REQUEST_PERCENTILE, CPU_REQUEST_NAME, LIMIT_PERCENTILE, CPU_LIMIT_NAME, MEMORY_REQUEST_NAME, \
    MEMORY_LIMIT_NAME, CPU_LIMIT_MILLIS_COLUMNS, MEMORY_LIMIT_MIBS_COLUMNS, PERCENTILES
from sizing.rules import PrometheusRules

NEW_SIZING_REPORT_FOLDER = Path(PYCPT_HOME, '../cpt_artefacts', 'new_sizing')

logger: logging.Logger = logging.getLogger(__name__)


class Resource:
    def __init__(self, name: str, unit: str, limit: str, measured: str, request: Optional[str] = None):
        self.name = name
        self.unit = unit
        self.limit = limit
        self.measured = measured
        self.request = request

    def __str__(self):
        return f'{self.name} : {self.measured}[{self.unit}]'


MEMORY_RESOURCE = Resource(name='memory', unit='Mi',
                           limit='MEMORY_LIMIT_BYTE', measured='MEMORY_BYTE', request='MEMORY_REQUEST_BYTE')

CPU_RESOURCE = Resource(name='cpu', unit='m',
                        limit='CPU_LIMIT_CORE', measured='CPU_CORE', request='CPU_REQUEST_CORE')

JVM_PROCESS_HEAP_RESOURCE = Resource(name='jvm_process_heap', unit='Mi',
                                     limit='JVM_PROCESS_HEAP_MAX', measured='JVM_PROCESS_HEAP_USED')

JVM_PROCESS_NON_HEAP_RESOURCE = Resource(name='jvm_process_non_heap', unit='Mi',
                                         limit='JVM_PROCESS_NON_HEAP_MAX', measured='JVM_PROCESS_NON_HEAP_USED')


class LimitsRequests:
    def __init__(self, ns_df: pd.DataFrame, sla_table: SlaTable, resource: Resource):
        self.ns_df: pd.DataFrame = ns_df
        self.sla_table: SlaTable = sla_table
        self.keys: List[str] = self.sla_table.tableKeys
        self.allKeys: List[str] = [TIMESTAMP_COLUMN] + self.keys
        self.indexFromKeys: List[str] = [k for k in self.allKeys if k != NAMESPACE_COLUMN]
        self.ns_df_indexed: pd.DataFrame = self.set_index_ns_df(self.indexFromKeys)
        # unstack TIMESTAMP_COLUMN
        self.ns_df_unstacked = self.ns_df_indexed.unstack(level=0)
        self.limit_field = self.ns_df_unstacked[resource.limit]
        self.request_field = self.ns_df_unstacked[resource.request]
        self.measured_field = self.ns_df_unstacked[resource.measured]
        self.verify_limits_requests()
        self.limit_value = self.limit_field.max(axis=1)
        self.request_value = self.request_field.max(axis=1)
        self.limit_value.name = resource.limit
        self.request_value.name = resource.request

    @classmethod
    def dummy(cls, sla_table: SlaTable, resource: Resource, df: pd.DataFrame) -> LimitsRequests:
        """Create LimitsRequests with simple data"""
        return cls(ns_df=df, sla_table=sla_table, resource=resource)

    def set_index_ns_df(self, keys: List[str]):
        """Create index from keys columns"""
        #  verify_integrity – Check the new index for duplicate
        return self.ns_df.set_index(keys=keys, verify_integrity=True, drop=True)

    def verify_limits_requests(self):
        """Positive numbers with min == max, do not mix different sizings"""
        assert self.limit_field.min(axis=1).equals(self.limit_field.max(axis=1))
        assert self.request_field.min(axis=1).equals(self.request_field.max(axis=1))

    def request_limit_df(self, columns: List[str]) -> pd.DataFrame:
        """Return requests and limits values"""
        df = pd.concat([self.request_value, self.limit_value], axis=1)
        df.columns = columns
        df.dropna(how='all', inplace=True)
        return df

    def measured_df_percentiles(self) -> pd.DataFrame:
        """Return measured values percentiles"""
        described_df = self.measured_field.dropna(how='all').T.describe(percentiles=PERCENTILES)
        return described_df.T


count_column = 'count'
scaled_columns = ['min'] + [f'{int(p * 100)}%' for p in PERCENTILES if p != count_column] + ['max']
cpu_lower_limit_millis = 1
memory_lower_limit_mib = 1


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


class SizingCalculator:
    def __init__(self, cpu: LimitsRequests, memory: LimitsRequests, time_range: Optional[TimeRange] = None,
                 namespace: Optional[str] = None, test_details: Optional[TestDetails] = None):
        self.cpu: LimitsRequests = cpu
        self.memory: LimitsRequests = memory
        self.time_range: TimeRange = time_range
        self.namespace: str = namespace
        self.test_details: TestDetails = test_details

    @classmethod
    def from_test_details(cls, cpu: LimitsRequests, memory: LimitsRequests, namespace,
                          test_details: TestDetails) -> SizingCalculator:
        return cls(cpu=cpu, memory=memory, time_range=test_details.testTimeRange.to_time_range(),
                   namespace=namespace, test_details=test_details)

    def memory_mibs(self) -> pd.DataFrame:
        memory_request_limits = self.memory.request_limit_df(columns=MEMORY_LIMIT_MIBS_COLUMNS)
        return (memory_request_limits / MIBS).astype(int)

    def cpu_millis(self) -> pd.DataFrame:
        """Convert cpu limits and requests from cores to milli cores"""
        cpu_request_limits = self.cpu.request_limit_df(columns=CPU_LIMIT_MILLIS_COLUMNS)
        return (cpu_request_limits * 1000).astype(int)

    def request_limits(self) -> pd.DataFrame:
        """Return CPU and memory requests and limits values in milli cores and Mi"""
        cpu_request_limits_millis = self.cpu_millis()
        memory_request_limits_mib = self.memory_mibs()
        return pd.concat([cpu_request_limits_millis, memory_request_limits_mib], axis=1)

    def mem_percentiles(self) -> pd.DataFrame:
        """Return memory percentiles joined with memory requests and limits in Mi"""
        counts_ser: pd.Series = self.memory.measured_df_percentiles()[count_column].astype(int)
        percentiles_df = (self.memory.measured_df_percentiles()[scaled_columns] / MIBS).astype(int)
        percentiles_df[count_column] = counts_ser
        return pd.concat([percentiles_df, self.memory_mibs()], axis=1, join='inner')

    def cpu_percentiles(self) -> pd.DataFrame:
        """Return cpu percentiles joined with cpu requests and limits in milli cores"""
        counts_ser: pd.Series = self.cpu.measured_df_percentiles()[count_column].astype(int)
        percentiles_df = (self.cpu.measured_df_percentiles()[scaled_columns] * 1000).round(1)
        percentiles_df[count_column] = counts_ser
        return pd.concat([percentiles_df, self.cpu_millis()], axis=1, join='inner')

    def report_header(self) -> str:
        """report header with namespace and time range"""
        duration = (self.test_details.testTimeRange.end - self.test_details.testTimeRange.start).total_seconds()
        samples = int(duration / DEFAULT_STEP_SEC) + 1
        data: Dict[str, List[str]] = {'description': [self.test_details.description],
                                      'duration [hours]': [duration / 3600],
                                      'from': [self.time_range.from_time.isoformat()],
                                      'to': [self.time_range.to_time.isoformat()],
                                      'max samples': [samples],
                                      }
        df: pd.DataFrame = pd.DataFrame(data=data)
        return df.to_html()

    def report(self, data: pd.DataFrame, folder: Path, file_name: str, test_summary: Optional[TestSummary] = None):
        """Create and save full report to file"""
        file_name = f'{file_name}_{str(self.time_range)}.html'
        report_header = self.report_header() if test_summary is None \
            else test_summary_header(test_summary) + "<br/>" + self.report_header()
        path = Path(folder, file_name)
        msg = f'Saving report to {path.resolve()}'
        typer.echo(msg)
        logger.info(msg)
        with open(path, 'w') as f:
            f.write(report_header + ("<br/>" + data.to_html() + "<hr>"))

    def all_reports(self, folder: Path, test_summary: Optional[TestSummary] = None):
        """Create and save all reports to folder"""
        os.makedirs(folder, exist_ok=True)
        self.report(data=self.request_limits(), folder=folder, file_name='requests_limits',
                    test_summary=test_summary)
        self.report(data=self.mem_percentiles(), folder=folder, file_name='memory_percentiles',
                    test_summary=test_summary)
        self.report(data=self.cpu_percentiles(), folder=folder, file_name='cpu_percentiles',
                    test_summary=test_summary)

    def new_sizing(self) -> pd.DataFrame:
        cpu_request: pd.Series = self.cpu_percentiles()[REQUEST_PERCENTILE]
        cpu_request.name = CPU_REQUEST_NAME
        cpu_limit: pd.Series = self.cpu_percentiles()[LIMIT_PERCENTILE]
        cpu_limit.name = CPU_LIMIT_NAME
        cpu_sizing = pd.concat([cpu_request, cpu_limit], axis=1)
        # select max cpu sizing for each container
        cpu_sizing_container = cpu_sizing.groupby(CONTAINER_COLUMN).max()
        # remove rows with small cpu (in milli)
        cpu_sizing_container = (
            cpu_sizing_container[cpu_sizing_container > cpu_lower_limit_millis].dropna(how='any').astype(int))
        # for memory we use limit = request but
        # DataFrame columns must be unique for orient='index'.
        mem_request: pd.Series = self.mem_percentiles()[REQUEST_PERCENTILE]
        mem_request.name = MEMORY_REQUEST_NAME
        mem_limit: pd.Series = self.mem_percentiles()[LIMIT_PERCENTILE]
        mem_limit.name = MEMORY_LIMIT_NAME
        mem_sizing = pd.concat([mem_request, mem_limit], axis=1)
        mem_sizing_container = mem_sizing.groupby(CONTAINER_COLUMN).max()
        # remove rows with 0
        mem_sizing_container = (
            mem_sizing_container[mem_sizing_container > memory_lower_limit_mib].dropna(how='any').astype(int))
        r_l = self.request_limits().groupby(CONTAINER_COLUMN).max()
        # inner join of cpu and memory sizings removes containers with 0 cpu from memory sizing_container
        joined_sizings = pd.concat([cpu_sizing_container, mem_sizing_container, r_l], axis=1, join='inner')
        return joined_sizings

    def sizing_json(self, folder: Path):
        """Save new sizing to folder as json"""
        os.makedirs(folder, exist_ok=True)
        file_name = f'new_sizing_{str(self.time_range)}.json'
        path = Path(folder, file_name)
        typer.echo(f'Saving new sizing to {path}')
        n_s = self.new_sizing()
        n_s.to_json(path, orient='index', indent=2)


def sizing_calculator(start_time: str, end_time: str, delta_hours: float, metrics_folder: Path,
                      namespace: str, test_details: Optional[TestDetails] = None) -> SizingCalculator:
    time_range = TimeRange(start_time=start_time, end_time=end_time, delta_hours=delta_hours)
    portal_prometheus: PortalPrometheus = PortalPrometheus(folder=metrics_folder)
    # value error if no table with name
    resource_table: SlaTable = portal_prometheus.load_sla_tables(table_name=POD_BASIC_RESOURCES_TABLE)[0]
    prom_rules: PrometheusRules = PrometheusRules(time_range=time_range, portal_table=resource_table)
    prom_rules.load_df()
    ns_df = prom_rules.ns_df(namespace=namespace)
    cpu: LimitsRequests = LimitsRequests(ns_df=ns_df, sla_table=resource_table, resource=CPU_RESOURCE)
    memory: LimitsRequests = LimitsRequests(ns_df=ns_df, sla_table=resource_table, resource=MEMORY_RESOURCE)
    return SizingCalculator(cpu=cpu, memory=memory, time_range=time_range, namespace=namespace,
                            test_details=test_details)


def test_summary_header(test_summary: TestSummary) -> str:
    """test summary header"""
    data: Dict[str, List[str]] = {'name': [test_summary.name],
                                  'namespace': [test_summary.namespace],
                                  'catalog items': [test_summary.catalogItems],
                                  }
    df: pd.DataFrame = pd.DataFrame(data=data)
    return df.to_html()


def save_new_sizing(all_test_sizing, common_folder, test_summary):
    if len(all_test_sizing) > 0:
        new_sizings = pd.concat(all_test_sizing).groupby(CONTAINER_COLUMN).max()
        folder = common_folder
        os.makedirs(folder, exist_ok=True)
        typer.echo(f'Saving new sizings to {folder}')
        new_sizings_report = test_summary_header(test_summary) + "<br/>" + new_sizings.to_html()
        with open(Path(folder, 'new_sizings.html'), 'w') as f:
            f.write(new_sizings_report)
        # new_sizings.to_json(Path(folder, 'new_sizings.json'), orient='index', indent=2)
        sizing_ini(new_sizings, folder)
    if len(all_test_sizing) == 0:
        typer.echo(f'No df appended to `all_test_sizing`')


def sizing_ini(new_sizings: pd.DataFrame, folder: Path):
    """Save new sizing to folder as ini"""
    os.makedirs(folder, exist_ok=True)
    file_name = 'new_sizing.ini'
    path = Path(folder, file_name)
    typer.echo(f'Saving new sizing to {path}')
    import configparser
    config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
    # case-sensitive keys
    config.optionxform = str
    new_sizings = new_sizings[new_sizings[CPU_REQUEST_NAME] >= 10]
    for container, row in new_sizings.iterrows():
        section = f'{container}'
        config.add_section(section=section)
        config.set(section=section, option='requests.cpu', value=str(row[CPU_REQUEST_NAME]) + 'm')
        config.set(section=section, option='limits.cpu', value=str(row[CPU_LIMIT_NAME]) + 'm')
        config.set(section=section, option='requests.memory', value=str(row[MEMORY_LIMIT_NAME]) + 'Mi')
        config.set(section=section, option='limits.memory', value=str(row[MEMORY_LIMIT_NAME]) + 'Mi')
    with open(path, 'w') as f:
        config.write(f)
