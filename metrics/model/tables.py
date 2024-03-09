from __future__ import annotations

from pathlib import Path
from typing import Optional

from loguru import logger

from prometheus.sla_model import SlaTable
from settings import settings
from shared.utils import list_files


class SlaTables:
    def __init__(self, folder: Path = settings.sla_tables):
        self.folder: Path = folder
        self.slaFiles: list[Path] = list_files(folder=self.folder, ends_with="json")
        self.slaTables: list[SlaTable] = [
            SlaTable.model_validate_json(json_data=sla_file.read_text()) for sla_file in self.slaFiles
        ]

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

    @classmethod
    def replace_portal_labels(
        cls,
        sla_table: SlaTable,
        namespaces: Optional[str],
        debug: bool = False,
    ) -> SlaTable:
        """
        Replace `groupBy`, `rateInterval` and `labels` placeholders
        groupBy is taken from PortalTable
        rateInterval is part of the query definition in json file
        labels are passed as argument or from PromQuery
        """
        for prom_query in sla_table.queries:
            grp_by_list: list[str] = sla_table.prepare_group_keys()
            use_group_by: str = f'{",".join(grp_by_list)}'
            prom_query.query = prom_query.query.replace("groupBy", use_group_by)
            # set for queries with rate, increase - presence indicates usage
            if prom_query.rateInterval:
                prom_query.query = prom_query.query.replace("rateInterval", prom_query.rateInterval)
            ns_label = f'namespace=~"{namespaces}"' if namespaces else None
            use_labels_list = prom_query.labels if prom_query.labels else sla_table.defaultLabels
            all_labels_list = [ns_label] + use_labels_list if ns_label is not None else use_labels_list
            use_labels = ",".join(all_labels_list)
            # staticLabels is by default empty list no need to check for None
            static_labels = ",".join(prom_query.staticLabels)
            if static_labels:
                use_labels = use_labels + "," + static_labels if use_labels else static_labels
            prom_query.query = prom_query.query.replace("labels", use_labels)
            if debug:
                logger.info(f"{prom_query.columnName}")
                logger.info(f"query          : {prom_query.query}")
        return sla_table
