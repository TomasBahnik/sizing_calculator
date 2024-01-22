import unittest

import pytest
from sizing.calculator import LimitsRequests
from prometheus.sla_model import SlaTable
from sizing.calculator import CPU_RESOURCE, MEMORY_RESOURCE
from sizing.data import CPU_DF, MEM_DF


@pytest.mark.unit
class TestLimitRequest:
    def test_something(self):
        cpu_dummy = LimitsRequests.dummy(sla_table=SlaTable.dummy(), resource=CPU_RESOURCE, df=CPU_DF)
        memory_dummy = LimitsRequests.dummy(sla_table=SlaTable.dummy(), resource=MEMORY_RESOURCE, df=MEM_DF)
        assert (cpu_dummy.limit_value == CPU_DF[CPU_RESOURCE.limit].max())
        assert (cpu_dummy.request_value == CPU_DF[CPU_RESOURCE.request].max())


if __name__ == '__main__':
    unittest.main()
