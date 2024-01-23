import unittest

import pandas as pd
import pytest

from sizing.calculator import CPU_RESOURCE, MEMORY_RESOURCE
from sizing.calculator import LimitsRequests


@pytest.mark.unit
class TestLimitRequest:
    def test_something(self):
        from sizing.data import DataLoader
        from metrics import POD_BASIC_RESOURCES_TABLE
        from metrics.model.tables import PortalPrometheus
        data_loader: DataLoader = DataLoader(delta_hours=None, start_time='2024-01-06T20', end_time='2024-01-06T20:05')
        sla_table = PortalPrometheus().get_sla_table(table_name=POD_BASIC_RESOURCES_TABLE)
        df: pd.DataFrame = data_loader.load_df(sla_table=sla_table)
        cpu = LimitsRequests(sla_table=sla_table, resource=CPU_RESOURCE, ns_df=df)
        assert cpu.request_value.max() == 1
        memory = LimitsRequests(sla_table=sla_table, resource=MEMORY_RESOURCE, ns_df=df)
        from metrics import MIBS
        max_memory_mib = memory.request_value.max() / MIBS
        # 4200 Mi
        assert max_memory_mib == 4200


if __name__ == '__main__':
    unittest.main()
