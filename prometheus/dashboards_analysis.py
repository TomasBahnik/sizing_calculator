from __future__ import annotations

import re

from pathlib import Path
from typing import Optional, TypeVar

import pandas as pd
import typer

from langchain.prompts import FewShotPromptTemplate, PromptTemplate
from langchain.prompts.example_selector import LengthBasedExampleSelector
from loguru import logger
from pydantic import BaseModel

from prometheus import FILE, LABEL, QUERIES, STATIC_LABEL, TITLE
from prometheus.prom_ql import extract_labels, strip_replace
from prometheus.prompt_model import PromExpression, PromptExample, Target, Title
from shared.utils import check_file, list_files


JSON_SUFFIX = ".json"

PROMPT_FIELDS = [TITLE, QUERIES, FILE, LABEL]
DF_COLUMNS = [TITLE, QUERIES, FILE, STATIC_LABEL]
TEMPLATE_FIELDS = [TITLE, QUERIES, FILE, STATIC_LABEL]

PROMPT_INPUT_VARIABLE = "input"
NO_TITLE = "no_title"
app = typer.Typer()


class SubPanel(BaseModel):
    title: str = NO_TITLE
    targets: list[Target] = []


class Panel(BaseModel):
    # panels[26].panels[4].title
    title: str = NO_TITLE
    # panels[26].panels[4].targets[3].expr
    targets: list[Target] = []
    panels: list[SubPanel] = []


class Row(BaseModel):
    title: str = NO_TITLE
    panels: list[SubPanel] = []


class GrafanaDashboard(BaseModel):
    """Either rows with panels or directly panels"""

    title: str = NO_TITLE
    rows: list[Row] = []
    panels: list[Panel] = []


TGrafanaDashboard = TypeVar("TGrafanaDashboard", bound=GrafanaDashboard)


def load_dashboards_from_files(
    folder: Path,
    filename: Optional[str] = None,
    contains: Optional[str] = None,
    ends_with: str = ("%s" % JSON_SUFFIX),
) -> list[tuple[PromptExample, GrafanaDashboard]]:
    """Load dashboards from list of files"""
    dashboards: list[Path] = list_files(folder=folder, ends_with=ends_with, contains=contains)
    if filename is not None:
        dashboard_file = Path(folder, filename)
        check_file(dashboard_file)
        dashboards = [dashboard_file]
    # fileName usually encodes info about module for private dashboards
    msg = f"Folder '{folder}', file '{filename}' : {len(dashboards)} files containing '{contains}' with suffix '{ends_with}'"
    logger.info(msg)
    ret = list(
        zip(
            [PromptExample(fileName=x) for x in dashboards],
            [
                GrafanaDashboard.model_validate_json(json_data=dashboard_file.read_text())
                for dashboard_file in dashboards
            ],
        )
    )
    return ret


def shot_examples(fse: list[dict], num_examples: int, prefix: str) -> FewShotPromptTemplate:
    # Next, we specify the template to format the examples we have provided.
    # We use the `PromptTemplate` class for this.
    example_formatter_template = f"""{TEMPLATE_FIELDS[0]}: {{{TITLE}}}
    {TEMPLATE_FIELDS[1]}: {{{QUERIES}}}
    {TEMPLATE_FIELDS[2]}: {{{FILE}}}""".replace(
        " ", ""
    )
    # {TEMPLATE_FIELDS[3]}: {{{STATIC_LABEL}}}""".replace(' ', '')
    example_prompt = PromptTemplate(
        input_variables=[TEMPLATE_FIELDS[0], TEMPLATE_FIELDS[1], TEMPLATE_FIELDS[2]],
        template=example_formatter_template,
    )

    example_selector = LengthBasedExampleSelector(
        examples=fse,
        example_prompt=example_prompt,
        # This is the maximum length that the formatted examples should be.
        # Length is measured by the get_text_length function below.
        max_length=num_examples,
        # This is the function used to get the length of a string, which is used
        # to determine which examples to include. It is commented out because
        # it is provided as a default value if none is specified.
        # get_text_length: Callable[[str], int] = lambda x: len(re.split("\n| ", x))
    )
    suffix = f"""{TEMPLATE_FIELDS[0]}:{{{PROMPT_INPUT_VARIABLE}}}""".replace(" ", "")
    few_shot_prompt = FewShotPromptTemplate(
        example_selector=example_selector,
        example_prompt=example_prompt,
        prefix=prefix,
        suffix=suffix,
        input_variables=[f"{PROMPT_INPUT_VARIABLE}"],
        example_separator="\n\n",
    )
    return few_shot_prompt


def flatten_list(l_of_l):
    return [item for sublist in l_of_l for item in sublist]


def extract_targets(dashboard: GrafanaDashboard) -> dict[str, list[Target]]:
    """title: targets dictionary with filters"""
    panels: list[Panel] = flatten_list([r.panels for r in dashboard.rows])
    panels = panels + dashboard.panels
    sub_panels = [panel for panel in panels if type(panel) != SubPanel and panel.panels]
    sub_panels_list: list[SubPanel] = flatten_list([sp.panels for sp in sub_panels])
    title_targets: dict[str, list[Target]] = {p.title.strip(): p.targets for p in panels if p.targets}
    sub_targets: dict[str, list[Target]] = {p.title.strip(): p.targets for p in sub_panels_list if p.targets}
    title_targets.update(sub_targets)
    ret = {
        title: targets
        for title, targets in title_targets.items()
        if title != NO_TITLE and len(targets) > 0 and targets[0].expr
    }
    return ret


def expr_query(expr: str) -> PromExpression:
    # initial value of prom_query.query = expr with labels
    expr = strip_replace(expr)
    return extract_labels(PromExpression(expr=expr, query=expr))


def prom_queries(title_targets: dict[str, list[Target]]) -> dict[str, list[PromExpression]]:
    """title: list[PromQuery] dictionary"""
    ret = {
        title: [expr_query(target.expr) for target in targets if target.expr]
        for title, targets in title_targets.items()
    }
    return ret


def prompt_lists(p_e_s: list[PromptExample]):
    """Prepare and return lists for prompt examples and html report"""
    titles_oo: list[Title] = flatten_list([[title for title in p_e.titles] for p_e in p_e_s])
    queries_oo: list[list[PromExpression]] = [t.queries for t in titles_oo]
    titles = [t.name for t in titles_oo]
    queries = [[pq.query for pq in pqs] for pqs in queries_oo]
    file_names: list[str] = flatten_list([p_e.file_names() for p_e in p_e_s])
    static_labels = [[pq.staticLabels for pq in pqs] for pqs in queries_oo]
    return file_names, queries, static_labels, titles


def prompt_examples(dashboards: list[tuple[PromptExample, GrafanaDashboard]]) -> list[PromptExample]:
    for p_e, d in dashboards:
        title_targets: dict[str, list[Target]] = extract_targets(d)
        title_queries: dict[str, list[PromExpression]] = prom_queries(title_targets=title_targets)
        if title_queries.keys() != title_targets.keys():
            raise ValueError("Different titles for targets and queries")
        titles = list(title_queries.keys())
        titles_oo: list[Title] = [Title(name=title, queries=title_queries[title]) for title in titles]
        p_e.titles = titles_oo
    examples: list[PromptExample] = [pg[0] for pg in dashboards]
    return examples


def all_examples(
    folder: Path,
    filename: Optional[str] = None,
    contains: Optional[str] = None,
    ends_with: str = JSON_SUFFIX,
) -> list[PromptExample]:
    prompt_example_dashboard: list[tuple[PromptExample, GrafanaDashboard]] = load_dashboards_from_files(
        folder=folder, filename=filename, contains=contains, ends_with=ends_with
    )
    examples: list[PromptExample] = prompt_examples(prompt_example_dashboard)
    return examples


@app.command()
def match_metrics(
    dashboards_folder: Path = typer.Option(..., "--folder", dir_okay=True, help="Folder with grafana dashboards"),
    dashboard_file: str = typer.Option(
        None,
        "--file",
        help=f"Name of dashboard file. If None all files with " f"--suffix value from the folder are loaded",
    ),
    file_name_contains: str = typer.Option(None, "--contains", "-c", help="Filter filenames that contain this string"),
    file_name_ends_with: str = typer.Option(
        JSON_SUFFIX,
        "--suffix",
        "-s",
        help="Filter filenames that ends with this string",
    ),
):
    pattern = r"\((.*?)\(label"
    examples: list[PromptExample] = all_examples(
        folder=dashboards_folder,
        filename=dashboard_file,
        contains=file_name_contains,
        ends_with=file_name_ends_with,
    )
    # cpt.prometheus.commands.metrics with contains=None creates metrics_all.json
    from settings import settings

    metrics_file: Path = Path(settings.prometheus_report_folder, "metrics", "metrics_all.json")
    if metrics_file.is_file():
        metrics_df: pd.DataFrame = pd.read_json(metrics_file)
        file_names, queries, static_labels, titles = prompt_lists(examples)
        available_metrics = metrics_df["metrics"]
        for am in available_metrics:
            am_used: bool = False
            for q in flatten_list(queries):
                # remove white spaces
                q = "".join(q.split())
                matches = re.findall(pattern, q)
                if matches:
                    logger.info(f"match groups : {matches}")
                #  add opening (
                if f"({am}" in q:
                    am_used = True
            logger.info(f"{am} used {am_used}")


if __name__ == "__main__":
    app()
