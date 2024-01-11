import logging
import sys
from pathlib import Path
from typing import List, Optional

import typer
from pydantic import parse_file_as

from common import list_files
from const import PORTAL_ONE_NS
from prompt_model import PortalTable

app = typer.Typer()
logger = logging.getLogger(__name__)


class PortalPrometheus:
    def __init__(self, folder: Path):
        self.folder: Path = folder

    def load_portal_tables(self, table_name: Optional[str] = None) -> List[PortalTable]:
        logger.info(f'Loading prom queries from {self.folder}')
        file_name_contains = table_name.lower() if table_name else None
        metrics_files: List[Path] = list_files(folder=self.folder, ends_with="json",
                                               contains=file_name_contains)
        if not metrics_files:
            raise FileNotFoundError(f'No json files in {self.folder} with name containing {file_name_contains}')
        ret: List[PortalTable] = [parse_file_as(type_=PortalTable, path=metric_file) for metric_file in metrics_files]
        if table_name:
            ret = [portal_table for portal_table in ret if portal_table.tableName == table_name]
            if len(ret) == 0:
                raise ValueError(f'no table with name {table_name}')
        return ret

    @classmethod
    def replace_portal_labels(cls, portal_table: PortalTable, namespaces: Optional[str],
                              labels: Optional[List[str]] = None, debug: bool = False) -> PortalTable:
        """
        Replace `groupBy`, `rateInterval` and `labels` placeholders
        groupBy is taken from PortalTable
        rateInterval is part of the query definition in json file
        labels are passed as argument or from PromQuery
        """
        for prom_query in portal_table.queries:
            grp_by_list: List[str] = portal_table.prepare_group_keys()
            use_group_by: str = f'{",".join(grp_by_list)}'
            prom_query.query = prom_query.query.replace('groupBy', use_group_by)
            # set for queries with rate, increase - presence indicates usage
            if prom_query.rateInterval:
                prom_query.query = prom_query.query.replace('rateInterval', prom_query.rateInterval)
            ns_label = f'namespace=~\"{namespaces}\"'
            use_labels_list = prom_query.labels if prom_query.labels else labels
            all_labels_list = [ns_label] + use_labels_list
            use_labels = ','.join(all_labels_list)
            # staticLabels is by default empty list no need to check for None
            static_labels = ','.join(prom_query.staticLabels)
            if static_labels:
                use_labels = use_labels + ',' + static_labels
            prom_query.query = prom_query.query.replace('labels', use_labels)
            if debug:
                typer.echo(f'{prom_query.columnName}')
                typer.echo(f'query          : {prom_query.query}')
        return portal_table


@app.command()
def load(metrics_folder: Path = typer.Option('./kubernetes/expressions', "--folder", "-f", dir_okay=True,
                                             help="Folder with saved PromQueries")):
    from prometheus.commands import DEFAULT_LABELS
    pp: PortalPrometheus = PortalPrometheus(folder=metrics_folder)
    portal_tables = pp.load_portal_tables()
    typer.echo(f'{metrics_folder}: {len(portal_tables)} loaded portal_tables')
    for portal_table in portal_tables:
        pp.replace_portal_labels(portal_table=portal_table, labels=DEFAULT_LABELS,
                                 debug=True, namespaces=PORTAL_ONE_NS)


if __name__ == "__main__":
    app()
    sys.exit()
