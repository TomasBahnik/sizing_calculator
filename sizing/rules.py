from __future__ import annotations

from typing import Dict, List, Optional, Set

import pandas as pd

from loguru import logger
from pandas import DataFrame

from metrics import CONTAINER_COLUMN, NAMESPACE_COLUMN, POD_COLUMN, TIMESTAMP_COLUMN
from metrics.collector import TimeRange
from prometheus.sla_model import BasicSla, Compare, SlaTable
from storage.snowflake import dataframe
from storage.snowflake.engine import SnowflakeEngine


CONTAINER_POD_COLUMNS = [CONTAINER_COLUMN, POD_COLUMN]
OVER_LIMIT_PCT_COLUMN = "OVER_LIMIT_PCT"
RATIO_COLUMN = "RATIO"
OVER_LIMIT_COUNT_COLUMN = "OVER_LIMIT_COUNT"
MAX_OVER_LIMIT_TIME_SEC_COLUMN = "MAX_OVER_LIMIT_TIME_SEC"
POD_CONTAINER_TYPE = "POD"

CPU_REQUEST_CORE = "CPU_REQUEST_CORE"
CPU_LIMIT_CORE = "CPU_LIMIT_CORE"
MEMORY_BYTE = "MEMORY_BYTE"
CPU_CORE = "CPU_CORE"
MEMORY_REQUEST_BYTE = "MEMORY_REQUEST_BYTE"
MEMORY_LIMIT_BYTE = "MEMORY_LIMIT_BYTE"
DEFAULT_TIME_DELTA_HOURS = 1


class RatioRule:

    def __init__(self, basic_rule: BasicSla, ns_df: pd.DataFrame, keys: List[str]):
        self.basic_rule: BasicSla = basic_rule
        self.keys: List[str] = keys
        self.allKeys: List[str] = [TIMESTAMP_COLUMN] + self.keys
        # NAMESPACE is already filtered, no need for unique index
        # df.set_index, verify_integrity – Check the new index for duplicate
        self.indexFromKeys: List[str] = [k for k in self.allKeys if k != NAMESPACE_COLUMN]
        # only delta and max consecutive period rules need timestamp
        self.groupByKeys: List[str] = [k for k in self.indexFromKeys if k != TIMESTAMP_COLUMN]
        # 0 has bool = False
        self.limit_value: bool = bool(self.basic_rule.resource_limit_value)
        self.limit_column: bool = bool(self.basic_rule.resource_limit_column)
        self.validate_limits()
        self.ns_df: pd.DataFrame = ns_df
        # use timestamp, pod, container as index
        self.ns_df_indexed: pd.DataFrame = self.set_index_ns_df()
        self.ns_df_ts_col: pd.DataFrame = self.index_to_frame()
        self.report_df: pd.DataFrame = pd.DataFrame()
        self.over_pct_dynamic: pd.Series = pd.Series(dtype=float)
        self.over_pct_counts: pd.Series = pd.Series(dtype=int)
        self.over_pct_static = pd.Series(data=float)
        self.containerPodIndexes: Dict[tuple, pd.MultiIndex] = self.container_pod_indexes()

    def get_namespace(self) -> str:
        namespaces: Set[str] = set(self.ns_df[NAMESPACE_COLUMN])
        assert len(namespaces) == 1
        return namespaces.pop()

    def pod_container_columns(self, columns: List[str]) -> pd.DataFrame:
        return self.ns_df[[POD_COLUMN, CONTAINER_COLUMN] + columns]

    def validate_limits(self):
        """Either limit value or limit column not both"""
        if self.limit_value and self.limit_column:
            raise ValueError(
                f"{self.basic_rule.resource}: " f"Either resource_limit_value or resource_limit_column not both"
            )
        if not self.limit_value and not self.limit_column:
            raise ValueError(
                f"{self.basic_rule.resource}:" f" Either resource_limit_column or resource_limit_value must be set "
            )

    def is_limit_static(self) -> bool:
        """Either limit value or limit column is already checked"""
        return self.limit_value and not self.limit_column

    @staticmethod
    def rows_nan(df: pd.DataFrame, check_nan: bool):
        """
        all nan/null why axis=1 (column) see
        # https://stackoverflow.com/questions/38884538/python-pandas-find-all-rows-where-all-values-are-nan
        :param df:
        :param check_nan:
        :return:
        """
        if check_nan:
            return df.index[df.isnull().all(axis=1)]
        else:
            return df.index[~df.isnull().all(axis=1)]

    def limits_wo_nan(self) -> pd.DataFrame:
        """Assumes valid limit > 0, missing limit = -1."""
        if self.is_limit_static():
            return pd.DataFrame({"limit value": [self.basic_rule.resource_limit_value]})
        limits_df = self.ns_df_indexed[[self.basic_rule.resource_limit_column]]
        return limits_df.fillna(value=-1, axis=1)

    def missing_limits_idx(self) -> pd.Index:
        if self.is_limit_static():
            return pd.Index([])
        limits_df = self.ns_df_indexed[[self.basic_rule.resource_limit_column]]
        limits_pod_container = limits_df.unstack(level=0)
        # at least one value
        limits_with_value = limits_pod_container.dropna(thresh=1)
        # all nan/null
        missing_limits_df = limits_pod_container[limits_pod_container.isnull().all(axis=1)]
        check_sets = set(limits_with_value.index).intersection(set(missing_limits_df.index))
        assert len(check_sets) == 0
        return missing_limits_df.index

    def set_index_ns_df(self):
        """Create index from keys columns"""
        #  verify_integrity – Check the new index for duplicate
        return self.ns_df.set_index(keys=self.indexFromKeys, verify_integrity=True, drop=True)

    def index_to_frame(self) -> pd.DataFrame:
        idx: pd.MultiIndex = self.ns_df_indexed.index
        return idx.to_frame()

    def container_pod_indexes(self):
        """Unique sorted dictionary.

        key = (container, pod)
        value = indexes in (namespace) DataFrame with metrics
        """
        cp_idx = {}
        try:
            c_p_df = self.ns_df_ts_col[CONTAINER_POD_COLUMNS]
            cp_tuples = sorted({tuple(cp) for cp in c_p_df.values})
            for t in cp_tuples:
                cp_idx[t] = c_p_df[(c_p_df[CONTAINER_COLUMN] == t[0]) & (c_p_df[POD_COLUMN] == t[1])].index
        except KeyError as key:
            logger.info(f"\t No {key}: in {self.basic_rule.resource}. Return empty dict")
        return cp_idx

    def resource_values(self) -> pd.Series:
        return self.ns_df_indexed[self.basic_rule.resource]

    def ns_resource_ratios(self) -> pd.Series:
        """Calculate resource/resource_limit_column ratio."""
        # index = pod/container, values = limits or -1 in case of missing limit
        resource_limits: pd.DataFrame = self.limits_wo_nan()
        resource_limits_ser: pd.Series = resource_limits[self.basic_rule.resource_limit_column]
        resource_values_ser: pd.Series = self.resource_values()
        ratio_values_ser: pd.Series = resource_values_ser.divide(resource_limits_ser, axis=0)
        return ratio_values_ser

    def missing_idx_values(self) -> pd.DataFrame:
        """Collected resource values for (pod,container) with missing resource limit.

        Only in these cases makes sense to look for suitable resource limit that can be used
        for ratio

        For static limit self.missing_limits_idx() return empty Index
        """
        resource_values_ts = self.resource_values()
        # rows with missing limits, all columns
        missing_values: pd.DataFrame = resource_values_ts.loc[
            resource_values_ts.index.isin(self.missing_limits_idx()), :
        ]
        # Keep only the rows with at least 1 non-NA values.
        missing_values = missing_values.dropna(thresh=1)
        return missing_values

    def over_pct_df(self) -> pd.DataFrame:
        ratios = self.calc_over_pct_dynamic()
        # group by pod/container counts timestamps
        all_ratio_counts = ratios.groupby(by=self.groupByKeys).count()
        non_nan_samples = all_ratio_counts[all_ratio_counts.index.isin(self.over_pct_counts.index)]
        report_df = self.pct_above_limit(not_nan_samples=non_nan_samples)
        return report_df

    def calc_over_pct_dynamic(self) -> pd.Series:
        ratios = self.ns_resource_ratios()
        compare: Compare = self.basic_rule.compare
        if compare == Compare.GREATER:
            self.over_pct_dynamic = ratios[ratios > self.basic_rule.limit_pct]
        elif compare == Compare.LESS:
            self.over_pct_dynamic = ratios[ratios < self.basic_rule.limit_pct]
        elif compare == Compare.EQUAL:
            self.over_pct_dynamic = ratios[ratios == self.basic_rule.limit_pct]
        self.over_pct_counts = self.over_pct_dynamic.groupby(by=self.groupByKeys).count()
        self.over_pct_counts.name = OVER_LIMIT_COUNT_COLUMN
        return ratios

    def over_pct_static_limit(self) -> pd.DataFrame:
        """Compare resource to fixed limit specified in the rule definition as rule.resource_limit_value."""
        resource_values = self.resource_values()
        compare: Compare = self.basic_rule.compare
        over_pct_static: pd.Series | pd.DataFrame
        if compare == Compare.GREATER:
            over_pct_static = resource_values[resource_values > self.basic_rule.resource_limit_value]
        elif compare == Compare.LESS:
            over_pct_static = resource_values[resource_values < self.basic_rule.resource_limit_value]
        elif compare == Compare.EQUAL:
            over_pct_static = resource_values[resource_values == self.basic_rule.resource_limit_value]
        elif compare == Compare.DELTA:
            # delta is supported only for default keys wo namespace i.e. container / pod
            # see cpt/prometheus/const.py DEFAULT_PORTAL_GRP_KEYS
            deltas = []
            for idx in self.containerPodIndexes.values():
                c_p_res = resource_values[resource_values.index.isin(idx)]
                deltas.append(c_p_res.max() - c_p_res.min())
            data = {self.basic_rule.resource: deltas}
            m_idx: pd.MultiIndex = pd.MultiIndex.from_tuples(
                list(self.containerPodIndexes.keys()), names=CONTAINER_POD_COLUMNS
            )
            over_pct: pd.DataFrame = pd.DataFrame(data=data, index=m_idx)
            over_pct_static = over_pct[over_pct[self.basic_rule.resource] > self.basic_rule.resource_limit_value]
            return over_pct_static
        else:
            raise ValueError(f"Unknown compare operator: {compare}")
        # aggregates over pod/container
        self.over_pct_static = over_pct_static
        self.over_pct_counts = over_pct_static.groupby(by=self.groupByKeys).count()
        self.over_pct_counts.name = OVER_LIMIT_COUNT_COLUMN
        all_not_nan_samples = resource_values.groupby(by=self.groupByKeys).count()
        not_nan_samples = all_not_nan_samples[all_not_nan_samples.index.isin(self.over_pct_counts.index)]
        return self.pct_above_limit(not_nan_samples=not_nan_samples)

    def pct_above_limit(self, not_nan_samples) -> pd.DataFrame:
        """Not NaN sample with index in over pct counts."""
        pct_above: pd.Series = 100 * self.over_pct_counts / not_nan_samples
        pct_above.name = OVER_LIMIT_PCT_COLUMN
        basic_concat_list = [self.over_pct_counts, pct_above.round(1)]
        max_period_over_sec: pd.Series = self.max_consecutive_overtime(threshold_count=1)
        concat_list = basic_concat_list if max_period_over_sec.empty else basic_concat_list + [max_period_over_sec]
        report_df = pd.concat(concat_list, axis=1)
        return report_df

    def report_header(self) -> str:
        """rule limit_pct has default value (None) - can't be used in calculation"""
        limit_pct: str = f"{self.basic_rule.limit_pct * 100}%" if self.basic_rule.limit_pct else str(None)
        data: Dict[str, List[str]] = {
            "namespace": [self.get_namespace()],
            "resource": [self.basic_rule.resource],
            "limit column": [self.basic_rule.resource_limit_column],
            "limit value": [str(self.basic_rule.resource_limit_value)],
            "limit pct": [limit_pct],
            "compare": [self.basic_rule.compare.name],
        }
        df: pd.DataFrame = pd.DataFrame(data=data)
        return df.to_html()

    def eval_rule(self) -> None:
        """Calculates specified ratios and provides DataFrame for report."""
        report_df: pd.DataFrame
        if self.is_limit_static():
            report_df = self.over_pct_static_limit()
        else:
            report_df = self.over_pct_df()
        self.report_df = report_df

    def report_data(self, ratios_only: bool = True) -> str:
        """
        All relevant data for report. empty df results in empty str
        :param ratios_only: only rule eval data - no all limits
        """
        ratios_html: str = self.report_df.to_html() if not self.report_df.empty else ""
        if ratios_only:
            return ratios_html
        missing_values_html: str = ""
        if not self.missing_idx_values().empty:
            missing_values_count: pd.Series = self.missing_idx_values().count(axis=1)
            missing_values_count.name = "COUNT"
            missing_values_mean: pd.Series = self.missing_idx_values().mean(axis=1)
            missing_values_mean.name = "MEAN"
            missing_values_df = pd.concat([missing_values_mean, missing_values_count], axis=1)
            title = f"<h4>{self.basic_rule.resource}: values available for missing limits</h4>"
            missing_values_html = title + missing_values_df.to_html()
        report_html = ratios_html + missing_values_html
        title_unique_limits = f"<h4>{self.basic_rule.resource}: unique limits</h4>"
        report_html += title_unique_limits
        unique_limits_html = f"{self.limits_wo_nan().to_html()}"
        report_html += unique_limits_html
        return report_html

    def requests_limits(self, resource_table: SlaTable) -> pd.DataFrame:
        from sizing.calculator import CPU_RESOURCE, MEMORY_RESOURCE, LimitsRequests, SizingCalculator

        cpu: LimitsRequests = LimitsRequests(ns_df=self.ns_df, sla_table=resource_table, resource=CPU_RESOURCE)
        memory: LimitsRequests = LimitsRequests(ns_df=self.ns_df, sla_table=resource_table, resource=MEMORY_RESOURCE)
        sizing_calc = SizingCalculator(cpu=cpu, memory=memory)
        return sizing_calc.request_limits()

    def add_report(self, main_header: str, resource_table: Optional[SlaTable] = None) -> str:
        self.eval_rule()
        requests_limits_df = self.requests_limits(resource_table=resource_table) if resource_table else None
        self.report_df = (
            pd.concat([self.report_df, requests_limits_df], axis=1, join="inner")
            if requests_limits_df is not None
            else self.report_df
        )
        if self.report_data():
            main_header += "<br/>" + self.report_header()
            main_header += "<br/>" + self.report_data() + "<hr>"
        return main_header

    def max_consecutive_overtime(self, threshold_count: int):
        """Max consecutive time period spent over limit"""
        empty_periods_sec_default: int = 0
        # NaN is True, non NaN is False : cumulative sum is constant in False block
        full_ts: pd.Series = pd.Series(index=self.resource_values().index, dtype=bool)
        if self.is_limit_static():
            # we need the full timeseries with nans at index NOT in self.over_pct_static
            # and not nan value at index with value over
            full_ts[full_ts.index.isin(self.over_pct_static.index)] = False
        else:
            # same for dynamic rule but with dynamic over_pct
            full_ts[full_ts.index.isin(self.over_pct_dynamic.index)] = False
        data = full_ts
        unstac_ts_data = data.unstack(level=0)
        # nan = True i.e. NOT over limit
        filled = unstac_ts_data.fillna(value=True)
        filled_false = filled[~filled.all(axis="columns")]
        index_names = filled_false.index.names
        consecutive_counts = filled_false.cumsum(axis=1)
        summary_dict = {}
        # iterate only over time values
        for idx in consecutive_counts.index:
            column_ser = consecutive_counts.loc[idx]
            # index after calling groupby = cumsum, values = counts
            grouped: pd.Series = column_ser.groupby(column_ser).count()
            # -1 because of first value is for the last True
            counts_over: pd.Series = grouped[grouped >= threshold_count] - 1
            periods_over_sec = []
            for c_o in counts_over.index:
                # go back to timestamps
                ts_over = column_ser[column_ser == c_o].index
                # first value is for the last True so subtract 2nd value
                # at least 3 1st = True, 2nd = False 3rd False
                # with len == 2 period_over == 0 because ts_over[-1] == ts_over[1]
                if len(ts_over) > 2:
                    period_over: pd.Timedelta = ts_over[-1] - ts_over[1]
                    periods_over_sec.append(period_over.total_seconds())
            # ValueError: max() arg is an empty sequence
            summary_dict[idx] = max(periods_over_sec) if len(periods_over_sec) > 0 else empty_periods_sec_default
        summary_ser: pd.Series = pd.Series(data=summary_dict.values(), index=summary_dict.keys(), dtype=float)
        summary_ser_not_empty = summary_ser[summary_ser != empty_periods_sec_default]
        if not summary_ser_not_empty.empty:
            summary_ser_not_empty.index.names = index_names
            summary_ser_not_empty.name = MAX_OVER_LIMIT_TIME_SEC_COLUMN
        return summary_ser_not_empty.round(0)


class PrometheusRules:

    def __init__(self, sla_table: SlaTable, time_range: TimeRange):
        self.timeRange: TimeRange = time_range
        self.sla_table: SlaTable = sla_table
        # load_df() must be called to set this to non-empty
        self.df: pd.DataFrame = pd.DataFrame()

    def __format__(self, format_spec=""):
        return f"period: {self.timeRange.from_time.isoformat()} - {self.timeRange.to_time.isoformat()}"

    def time_range_query(self, table_name: str, timestamp_field: str = TIMESTAMP_COLUMN):
        lower_bound = f""""{timestamp_field}" >= '{self.timeRange.from_time}'"""
        upper_bound = f""""{timestamp_field}" <= '{self.timeRange.to_time}'"""
        q = f"SELECT * FROM {table_name} WHERE {lower_bound} AND {upper_bound}"
        return q

    def load_range_table(self) -> pd.DataFrame:
        sf = SnowflakeEngine(schema=self.sla_table.dbSchema)
        try:
            table_name = self.sla_table.tableName
            table_keys = [TIMESTAMP_COLUMN] + self.sla_table.tableKeys if self.sla_table.tableKeys else []
            q = self.time_range_query(table_name=table_name)
            logger.info(
                f"Snowflake table: {sf.schema}.{table_name}, "
                f"range: {self.timeRange.from_time} - {self.timeRange.to_time}"
            )
            df: DataFrame = dataframe.get_df(query=q, con=sf.connection)
            dedup_df = df.drop_duplicates(subset=table_keys)
            removed = len(df) - len(dedup_df)
            if removed > 0:
                logger.info(f"Removed {removed} duplicates by {table_keys}")
            return dedup_df
        finally:
            sf.sf_engine.dispose()

    def load_df(self):
        """Load data from Snowflake sla table and set self.df."""
        self.df = self.load_range_table()

    def namespaces(self, namespace: str) -> List[str]:
        """All unique namespaces or filtered one."""
        all_ns = sorted(set(self.df[NAMESPACE_COLUMN]))
        if namespace in all_ns:
            return [namespace]
        else:
            logger.info(f"{namespace} not found in {all_ns}. Return all")
        return all_ns

    def ns_df(self, namespace: str):
        """Filter df by namespace."""
        return self.df[self.df[NAMESPACE_COLUMN] == namespace]
