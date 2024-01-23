import unittest

import pandas as pd
import pytest

from sizing.calculator import CPU_RESOURCE, MEMORY_RESOURCE
from sizing.calculator import LimitsRequests


@pytest.mark.unit
class TestLimitRequest:
    def test_max_limit_request(self):
        from sizing.data import DataLoader
        from metrics import POD_BASIC_RESOURCES_TABLE
        from metrics.model.tables import PortalPrometheus
        data_loader: DataLoader = DataLoader(delta_hours=None, start_time='2024-01-06T20', end_time='2024-01-06T20:05')
        sla_table = PortalPrometheus().get_sla_table(table_name=POD_BASIC_RESOURCES_TABLE)
        df: pd.DataFrame = data_loader.load_df(sla_table=sla_table)
        cpu = LimitsRequests(sla_table=sla_table, resource=CPU_RESOURCE, ns_df=df)
        max_cpu_request = cpu.request_value.max()
        assert max_cpu_request == 1
        max_cpu_limit = cpu.limit_value.max()
        assert max_cpu_limit == 1.5
        memory = LimitsRequests(sla_table=sla_table, resource=MEMORY_RESOURCE, ns_df=df)
        from metrics import MIBS
        max_request_memory_mib = memory.request_value.max() / MIBS
        assert max_request_memory_mib == 4200
        max_limit_memory_mib = memory.limit_value.max() / MIBS
        assert max_limit_memory_mib == max_request_memory_mib


if __name__ == '__main__':
    unittest.main()
