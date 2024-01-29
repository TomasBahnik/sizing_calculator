from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd
import pytest

from sizing.calculator import CPU_RESOURCE, MEMORY_RESOURCE, LimitsRequests


@pytest.mark.unit
class TestLimitRequest:
    def test_max_limit_request(self):
        """Verify correct values for max limit and request."""
        from metrics import POD_BASIC_RESOURCES_TABLE
        from metrics.model.tables import SlaTables
        from sizing.data import DataLoader

        data_loader: DataLoader = DataLoader(
            delta_hours=None, start_time="2024-01-06T20", end_time="2024-01-06T20:05"
        )
        sla_table = SlaTables().get_sla_table(table_name=POD_BASIC_RESOURCES_TABLE)
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


@pytest.mark.unit
class TestGrafanaDashboards:
    def test_expressions_counts(self):
        """Verify correct number of expressions in selected dashboards."""
        from prometheus.dashboards_analysis import all_examples
        from prometheus.prompt_model import PromptExample
        from settings import settings

        examples: List[PromptExample] = all_examples(
            folder=Path(settings.pycpt_artefacts, "dashboards")
        )
        from prometheus.dashboards_analysis import prompt_lists

        file_names, queries, static_labels, titles = prompt_lists(examples)
        from prometheus import FILE, QUERIES, STATIC_LABEL, TITLE

        tmp_dict = {
            FILE: file_names,
            TITLE: titles,
            QUERIES: queries,
            STATIC_LABEL: static_labels,
        }
        tmp_df = pd.DataFrame(data=tmp_dict)
        assert len(tmp_df) == 930
