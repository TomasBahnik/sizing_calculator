"""Coverts result of Prometheus query to columns in RDS."""

from __future__ import annotations

import pandas as pd

import metrics
from storage.snowflake.dataframe import add_tz


class PrometheusRDSColumn:
    """Coverts result of Prometheus query to columns in RDS."""

    def __init__(self, df: pd.DataFrame, group_by: list[str], column_name: str):
        self.df = df
        self.originalColumns = df.columns
        # duplicated from SlaTable.prepare_group_keys
        # in case of typos and duplicates in json file - set comprehension, sorted returns list
        self.groupBy: list[str] = sorted({key.strip() for key in group_by})
        self.columnName: str = column_name
        self.localized_ts = add_tz(pd.Series(self.df.index))
        self.tableColumns = [g.upper() for g in self.groupBy]
        self.multiIndex = self.multi_index()

    def col_dict(self, column_name: str) -> dict:
        """Convert columns names returned by range query with groupBy keys to dict.
        {groupBy[0]: "value0", ...}
        We need only values because keys are checked against groupBy and ValueError is raised if not consistent
        """
        column_name = column_name.replace("=", ":")
        for key in self.groupBy:
            column_name = column_name.replace(key, f'"{key}"')
        parts = column_name.split(",")
        filtered_parts = [p for p in parts if any([gk in p for gk in self.groupBy])]
        column_name = ",".join(filtered_parts)
        # add ending } in case when there is more grp keys
        column_name = column_name if column_name.endswith("}") else "{" + column_name + "}"
        ret = eval(column_name)
        assert isinstance(ret, dict)
        # check consistency of SLA groupBy and column names returned by Prometheus
        if self.groupBy != sorted(ret.keys()):
            raise ValueError(f"SLA groupBy {self.groupBy} and column names {ret.keys()} are not consistent")
        return ret

    def col_values(self, column_name: str) -> tuple[str, ...]:
        """Returns values of groupBy keys as tuple."""
        d: dict = self.col_dict(column_name)
        return tuple([v for v in d.values()])

    def columns_to_tuples(self) -> list[tuple[str, ...]]:
        """covert string column names to tuples of self.groupBy values.

        [{namespace: "one", pod: "two"} -> ("one", "two"), ...]
        """
        column_values: list[tuple[str, ...]] = [self.col_values(str(c)) for c in self.originalColumns]
        return column_values

    def multi_index(self) -> pd.MultiIndex:
        """MultiIndex from columns."""
        tuple_columns: list[tuple[str, ...]] = self.columns_to_tuples()
        return pd.MultiIndex.from_tuples(tuple_columns)

    def column_df(self) -> pd.DataFrame:
        """Single column DataFrame with multi index = self.groupBy and timestamp.
        Add tuple columns and move timestamps to index.

        Stack the prescribed level(s) from columns to index
        transpose df has single level column - timestamp
        if the columns have a single level, the output is a Series
        dropna = True by default
        When reading from json file columns are strings and needs to be converted to tuples
        :return: Single columns DataFrame to store in RDS
        """
        # first set timestamp with timezone
        self.df.index = self.localized_ts
        # columns as multi index
        self.df.columns = self.multiIndex
        # transpose so localized timestamp are columns and self.multi_index() indexes rows
        # after stack localized timestamp becomes last level of index
        stacked: pd.Series = self.df.T.stack(dropna=False)
        df: pd.DataFrame = pd.DataFrame(stacked, columns=[self.columnName])
        return df

    def common_columns(self):
        """Extract columns used in MultiIndex."""
        column_values = self.columns_to_tuples()
        column_keys = self.groupBy
        ts_data: dict = {metrics.TIMESTAMP_COLUMN: self.localized_ts}
        col_data: dict = {column_keys[i]: [t[i] for t in column_values] for i in range(len(column_keys))}
        # ts_data.update(col_data)
        # df: pd.DataFrame = pd.DataFrame(ts_data, index=self.df.index)
        # return sf_df
