import logging
import sys
from pathlib import Path

import typer

app = typer.Typer()
logger = logging.getLogger(__name__)


@app.command()
def load(metrics_folder: Path = typer.Option('./kubernetes/expressions', "--folder", "-f", dir_okay=True,
                                             help="Folder with saved PromQueries")):
    from prometheus.commands import DEFAULT_LABELS
    from metrics.model.tables import PortalPrometheus
    pp: PortalPrometheus = PortalPrometheus(folder=metrics_folder)
    portal_tables = pp.load_portal_tables()
    typer.echo(f'{metrics_folder}: {len(portal_tables)} loaded portal_tables')
    for portal_table in portal_tables:
        from metrics import PORTAL_ONE_NS
        pp.replace_portal_labels(portal_table=portal_table, labels=DEFAULT_LABELS,
                                 debug=True, namespaces=PORTAL_ONE_NS)


if __name__ == "__main__":
    app()
    sys.exit()
