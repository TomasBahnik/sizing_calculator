"""Coverts result of Prometheus query to columns in RDS."""

from __future__ import annotations

import pandas as pd

from prometheus.sla_model import SlaTable


class PrometheusRDSColumn:
    """Coverts result of Prometheus query to columns in RDS."""

    def __init__(self, df: pd.DataFrame, sla_table: SlaTable):
        self.df = df
        # duplicated from SlaTable.prepare_group_keys
        # in case of typos and duplicates in json file - set comprehension, sorted returns list
        self.groupBy: list[str] = sorted({key.strip() for key in sla_table.groupBy})

    def col_dict(self, column_name: str) -> dict:
        """Convert columns names returned by range query with groupBy keys to dict.
        {groupBy[0]: "value0", ...}
        We need only values
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
        return eval(column_name)

    def col_tuple(self, column_name: str) -> tuple[str, ...]:
        """Returns values of dict groupBy keys as tuple."""
        d: dict = self.col_dict(column_name)
        return tuple([v for v in d.values()])

    def columns_to_tuples(self) -> list[tuple[str, ...]]:
        """covert string column names to tuples of self.groupBy values.

        [{namespace: "one", pod: "two"} -> ("one", "two"), ...]
        """
        column_values: list[tuple[str, ...]] = [self.col_tuple(str(c)) for c in self.df.columns]
        return column_values

    def stack_timestamps(self) -> pd.Series:
        """
        Stack the prescribed level(s) from columns to index
        transpose df has single level column - timestamp
        if the columns have a single level, the output is a Series
        dropna = True by default
        When reading from json file columns are strings and needs to be converted to tuples
        :return: DataFrame to store in snowflake
        """
        from storage.snowflake.dataframe import add_tz

        localized_ts = add_tz(pd.Series(self.df.index))
        self.df.index = localized_ts
        tuple_columns: list[tuple[str, ...]] = self.columns_to_tuples()
        multi_idx = pd.MultiIndex.from_tuples(tuple_columns)
        self.df.columns = multi_idx
        stacked: pd.Series = self.df.T.stack(dropna=False)
        return stacked

    def sf_series(self) -> pd.Series:
        """Add tuple columns and move timestamps to index."""
        self.columns_to_tuples()
        return self.stack_timestamps()
