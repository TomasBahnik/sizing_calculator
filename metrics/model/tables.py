from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from loguru import logger

from prometheus.sla_model import SlaTable
from settings import settings
from shared.utils import list_files


class SlaTables:
    def __init__(self, folder: Path = settings.sla_tables):
        self.folder: Path = folder
        self.slaFiles: List[Path] = list_files(folder=self.folder, ends_with="json")
        self.slaTables: List[SlaTable] = [
            SlaTable.model_validate_json(json_data=sla_file.read_text())
            for sla_file in self.slaFiles
        ]

    def get_sla_table(self, table_name: str) -> SlaTable:
        for sla_table in self.slaTables:
            if sla_table.tableName == table_name:
                return sla_table
        raise ValueError(f"no table with name {table_name}")

    def load_sla_tables(self, table_name: Optional[str] = None) -> List[SlaTable]:
        logger.info(f"Loading prom queries from {self.folder}")
        file_name_contains = table_name.lower() if table_name else None
        metrics_files: List[Path] = list_files(
            folder=self.folder, ends_with="json", contains=file_name_contains
        )
        if not metrics_files:
            raise FileNotFoundError(
                f"No json files in {self.folder} with name containing {file_name_contains}"
            )
        ret: List[SlaTable] = [
            SlaTable.model_validate_json(json_data=metric_file.read_text())
            for metric_file in metrics_files
        ]
        if table_name:
            ret = [
                portal_table
                for portal_table in ret
                if portal_table.tableName == table_name
            ]
            if len(ret) == 0:
                raise ValueError(f"no table with name {table_name}")
        return ret

    @classmethod
    def replace_portal_labels(
        cls,
        portal_table: SlaTable,
        namespaces: Optional[str],
        labels: Optional[List[str]] = None,
        debug: bool = False,
    ) -> SlaTable:
        """
        Replace `groupBy`, `rateInterval` and `labels` placeholders
        groupBy is taken from PortalTable
        rateInterval is part of the query definition in json file
        labels are passed as argument or from PromQuery
        """
        for prom_query in portal_table.queries:
            grp_by_list: List[str] = portal_table.prepare_group_keys()
            use_group_by: str = f'{",".join(grp_by_list)}'
            prom_query.query = prom_query.query.replace("groupBy", use_group_by)
            # set for queries with rate, increase - presence indicates usage
            if prom_query.rateInterval:
                prom_query.query = prom_query.query.replace(
                    "rateInterval", prom_query.rateInterval
                )
            ns_label = f'namespace=~"{namespaces}"'
            use_labels_list = prom_query.labels if prom_query.labels else labels
            all_labels_list = [ns_label] + use_labels_list
            use_labels = ",".join(all_labels_list)
            # staticLabels is by default empty list no need to check for None
            static_labels = ",".join(prom_query.staticLabels)
            if static_labels:
                use_labels = use_labels + "," + static_labels
            prom_query.query = prom_query.query.replace("labels", use_labels)
            if debug:
                logger.info(f"{prom_query.columnName}")
                logger.info(f"query          : {prom_query.query}")
        return portal_table
