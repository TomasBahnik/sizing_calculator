from __future__ import annotations

from pathlib import Path
from typing import Optional

from loguru import logger

from prometheus.sla_model import SlaTable
from settings import settings
from shared.utils import list_files


class SlaTablesHelper:
    def __init__(self, folder: Path = settings.sla_tables):
        self.folder: Path = folder
        self.slaFiles: list[Path] = list_files(folder=self.folder, ends_with="json")
        self.slaTables: list[SlaTable] = [
            SlaTable.model_validate_json(json_data=sla_file.read_text()) for sla_file in self.slaFiles
        ]
        self.tableNames: list[str] = [f"{t.dbSchema}.\"{t.tableName}\"" for t in self.slaTables]

    def get_sla_table(self, table_name: str) -> SlaTable:
        for sla_table in self.slaTables:
            if sla_table.tableName == table_name:
                return sla_table
        raise ValueError(f"no table with name {table_name}")

    def load_sla_tables(self, table_name: Optional[str] = None) -> list[SlaTable]:
        logger.info(f"Loading prom queries from {self.folder}")
        # by convention table name is uppercase of the file name without extension
        file_name_contains = table_name.lower() if table_name else None
        metrics_files: list[Path] = list_files(folder=self.folder, ends_with="json", contains=file_name_contains)
        if not metrics_files:
            raise FileNotFoundError(f"No json files in {self.folder} with name containing {file_name_contains}")
        ret: list[SlaTable] = [
            SlaTable.model_validate_json(json_data=metric_file.read_text()) for metric_file in metrics_files
        ]
        if table_name:
            ret = [sla_table for sla_table in ret if sla_table.tableName == table_name]
            if len(ret) == 0:
                raise ValueError(f"no table with name {table_name}")
        return ret
