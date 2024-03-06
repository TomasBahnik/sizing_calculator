from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from settings import settings
from sizing.calculator import CPU_RESOURCE, MEMORY_RESOURCE, LimitsRequests, SizingCalculator, save_new_sizing


@pytest.mark.integration
class TestSizingReport:
    def test_files(self) -> None:
        """Verify correct shape new sizing df."""
        from metrics import POD_BASIC_RESOURCES_TABLE
        from metrics.model.tables import SlaTables
        from sizing.data import DataLoader

        data_loader: DataLoader = DataLoader(start_time=None, end_time=None)
        sla_table = SlaTables().get_sla_table(table_name=POD_BASIC_RESOURCES_TABLE)
        df: pd.DataFrame = data_loader.load_df(
            sla_table=sla_table, df_path=Path(settings.test_data, "POD_BASIC_RESOURCES.json")
        )
        from metrics import TIMESTAMP_COLUMN

        start_time = df[TIMESTAMP_COLUMN].min()
        end_time = df[TIMESTAMP_COLUMN].max()
        cpu = LimitsRequests(sla_table=sla_table, resource=CPU_RESOURCE, ns_df=df)
        memory = LimitsRequests(sla_table=sla_table, resource=MEMORY_RESOURCE, ns_df=df)
        from metrics.collector import TimeRange

        time_range = TimeRange(start_time=start_time, end_time=end_time)
        s_c = SizingCalculator(cpu=cpu, memory=memory, time_range=time_range)
        s_c.sizing_calc_all_reports(folder=settings.test_data, test_summary=None)
        new_sizing: pd.DataFrame = s_c.new_sizing()
        assert new_sizing.shape == (20, 8)
        save_new_sizing(all_test_sizing=[s_c.new_sizing()], folder=settings.test_data, test_summary=None)
