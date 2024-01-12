import json
import logging
import os
import re
from pathlib import Path
from typing import List, Optional, TypeVar, Dict, Tuple

import pandas as pd
import typer
from langchain import PromptTemplate, FewShotPromptTemplate
from langchain.prompts.example_selector import LengthBasedExampleSelector
from pandas import DataFrame
from pydantic import BaseModel, parse_file_as

from prometheus.common import check_file, list_files
from reports import PROMETHEUS_REPORT_FOLDER
from prometheus.const import QUERIES, TITLE, LABEL, STATIC_LABEL, FILE
from prometheus.prom_ql import strip_replace, extract_labels
from prometheus.prompt_model import Target, PromQuery, Title, PromptExample

JSON_SUFFIX = ".json"

PROMPT_FIELDS = [TITLE, QUERIES, FILE, LABEL]
DF_COLUMNS = [TITLE, QUERIES, FILE, STATIC_LABEL]
TEMPLATE_FIELDS = [TITLE, QUERIES, FILE, STATIC_LABEL]

PROMPT_INPUT_VARIABLE = 'input'
NO_TITLE = "no_title"
app = typer.Typer()
logger = logging.getLogger(__name__)


class SubPanel(BaseModel):
    title: str = NO_TITLE
    targets: List[Target] = []


class Panel(BaseModel):
    # panels[26].panels[4].title
    title: str = NO_TITLE
    # panels[26].panels[4].targets[3].expr
    targets: List[Target] = []
    panels: List[SubPanel] = []


class Row(BaseModel):
    title: str = NO_TITLE
    panels: List[SubPanel] = []


class GrafanaDashboard(BaseModel):
    """ Either rows with panels or directly panels"""
    title: str = NO_TITLE
    rows: List[Row] = []
    panels: List[Panel] = []


TGrafanaDashboard = TypeVar("TGrafanaDashboard", bound=GrafanaDashboard)


def load_dashboards_from_files(folder: Path, filename: Optional[str] = None,
                               contains: Optional[str] = None, ends_with: str = ("%s" % JSON_SUFFIX)) \
        -> List[Tuple[PromptExample, GrafanaDashboard]]:
    """ Load dashboards from list of files"""
    dashboards: List[Path] = list_files(folder=folder, ends_with=ends_with, contains=contains)
    if filename is not None:
        dashboard_file = Path(folder, filename)
        check_file(dashboard_file)
        dashboards: List[Path] = [dashboard_file]
    # fileName usually encodes info about module for private dashboards
    msg = f"Folder '{folder}', file '{filename}' : {len(dashboards)} files containing '{contains}' with suffix '{ends_with}'"
    logger.info(msg=msg)
    typer.echo(message=msg)
    ret = list(zip([PromptExample(fileName=x) for x in dashboards],
                   [parse_file_as(type_=GrafanaDashboard, path=dashboard_file) for dashboard_file in dashboards]))
    return ret


def shot_examples(fse: List[Dict], num_examples: int, prefix: str) -> FewShotPromptTemplate:
    # Next, we specify the template to format the examples we have provided.
    # We use the `PromptTemplate` class for this.
    example_formatter_template = f"""{TEMPLATE_FIELDS[0]}: {{{TITLE}}}
    {TEMPLATE_FIELDS[1]}: {{{QUERIES}}}
    {TEMPLATE_FIELDS[2]}: {{{FILE}}}""".replace(' ', '')
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
        max_length=num_examples
        # This is the function used to get the length of a string, which is used
        # to determine which examples to include. It is commented out because
        # it is provided as a default value if none is specified.
        # get_text_length: Callable[[str], int] = lambda x: len(re.split("\n| ", x))
    )
    suffix = f"""{TEMPLATE_FIELDS[0]}:{{{PROMPT_INPUT_VARIABLE}}}""".replace(" ", '')
    few_shot_prompt = FewShotPromptTemplate(example_selector=example_selector,
                                            example_prompt=example_prompt,
                                            prefix=prefix,
                                            suffix=suffix,
                                            input_variables=[f'{PROMPT_INPUT_VARIABLE}'],
                                            example_separator="\n\n")
    return few_shot_prompt


def flatten_list(l_of_l):
    return [item for sublist in l_of_l for item in sublist]


def extract_targets(dashboard: GrafanaDashboard) -> Dict[str, List[Target]]:
    """ title: targets dictionary with filters"""
    panels: List[Panel] = flatten_list([r.panels for r in dashboard.rows])
    panels: List[Panel] = panels + dashboard.panels
    sub_panels = [panel for panel in panels if type(panel) != SubPanel and panel.panels]
    sub_panels_list: List[SubPanel] = flatten_list([sp.panels for sp in sub_panels])
    title_targets: Dict[str, List[Target]] = {p.title.strip(): p.targets for p in panels if p.targets}
    sub_targets: Dict[str, List[Target]] = {p.title.strip(): p.targets for p in sub_panels_list if p.targets}
    title_targets.update(sub_targets)
    ret = {title: targets for title, targets in title_targets.items()
           if title != NO_TITLE and len(targets) > 0 and targets[0].expr}
    return ret


def expr_query(expr: str) -> PromQuery:
    # initial value of prom_query.query = expr with labels
    expr = strip_replace(expr)
    return extract_labels(PromQuery(expr=expr, query=expr))


def prom_queries(title_targets: Dict[str, List[Target]]) -> Dict[str, List[PromQuery]]:
    """ title: List[PromQuery] dictionary"""
    ret = {title: [expr_query(target.expr) for target in targets if target.expr] for title, targets in
           title_targets.items()}
    return ret


def prompt_lists(p_e_s: List[PromptExample]):
    """ Prepare and return lists for prompt examples and html report """
    titles_oo: List[Title] = flatten_list([[title for title in p_e.titles] for p_e in p_e_s])
    queries_oo: List[List[PromQuery]] = [t.queries for t in titles_oo]
    titles = [t.name for t in titles_oo]
    queries = [[pq.query for pq in pqs] for pqs in queries_oo]
    file_names: List[str] = flatten_list([p_e.file_names() for p_e in p_e_s])
    static_labels = [[pq.staticLabels for pq in pqs] for pqs in queries_oo]
    return file_names, queries, static_labels, titles


def prompt_examples(dashboards: List[Tuple[PromptExample, GrafanaDashboard]]) -> List[PromptExample]:
    for p_e, d in dashboards:
        title_targets: Dict[str, List[Target]] = extract_targets(d)
        title_queries: Dict[str, List[PromQuery]] = prom_queries(title_targets=title_targets)
        if title_queries.keys() != title_targets.keys():
            raise ValueError("Different titles for targets and queries")
        titles = list(title_queries.keys())
        titles_oo: List[Title] = [Title(name=title, queries=title_queries[title]) for title in titles]
        p_e.titles = titles_oo
    examples: List[PromptExample] = [pg[0] for pg in dashboards]
    return examples


def all_examples(folder: Path, filename: Optional[str] = None, contains: Optional[str] = None,
                 ends_with: str = JSON_SUFFIX) -> List[PromptExample]:
    prompt_example_dashboard: List[Tuple[PromptExample, GrafanaDashboard]] = \
        load_dashboards_from_files(folder=folder,
                                   filename=filename,
                                   contains=contains,
                                   ends_with=ends_with)
    examples: List[PromptExample] = prompt_examples(prompt_example_dashboard)
    return examples


@app.command()
def report(dashboards_folder: Path = typer.Option(..., "--folder", dir_okay=True,
                                                  help="Folder with grafana dashboards"),
           dashboard_file: str = typer.Option(None, "--file",
                                              help=f"Name of dashboard file. If None all files with "
                                                   f"--suffix value from the folder are loaded"),
           file_name_contains: str = typer.Option(None, "--contains", "-c",
                                                  help="Filter filenames that contain this string"),
           file_name_ends_with: str = typer.Option(JSON_SUFFIX, "--suffix", "-s",
                                                   help="Filter filenames that ends with this string")):
    """HTML report with prometheus metrics to stdout"""
    examples: List[PromptExample] = all_examples(folder=dashboards_folder, filename=dashboard_file,
                                                 contains=file_name_contains, ends_with=file_name_ends_with)
    file_names, queries, static_labels, titles = prompt_lists(examples)
    tmp_dict = {FILE: file_names, TITLE: titles, QUERIES: queries, STATIC_LABEL: static_labels}
    tmp_df = DataFrame(data=tmp_dict)
    tmp_df.sort_values(by=[FILE, TITLE], inplace=True, ignore_index=True)
    base_path = Path(PROMETHEUS_REPORT_FOLDER, report.__name__)
    os.makedirs(name=base_path, exist_ok=True)
    html_file = Path(base_path, f"{dashboards_folder.parts[-1]}_{file_name_contains}_{file_name_ends_with[1:]}.html")
    if dashboard_file:
        html_file = Path(f"{dashboards_folder.parts[-1]}_{dashboard_file}_{file_name_ends_with[1:]}.html")
    typer.echo(f'Saving to {html_file.resolve()}')
    tmp_df.to_html(html_file, index=True)


@app.command()
def expressions(dashboards_folder: Path = typer.Option(..., "--folder", dir_okay=True,
                                                       help="Folder with grafana dashboards"),
                dashboard_file: str = typer.Option(None, "--file",
                                                   help=f"Name of dashboard file. If None all files with "
                                                        f"--suffix value from the folder are loaded"),
                file_name_contains: str = typer.Option(None, "--contains", "-c",
                                                       help="Filter filenames that contain this string"),
                file_name_ends_with: str = typer.Option(JSON_SUFFIX, "--suffix", "-s",
                                                        help="Filter filenames that ends with this string")):
    """
    Store Prometheus expression as dumped cpt.prometheus.prompt_model.Title so it can be loaded back to objects

    :param dashboards_folder:
    :param dashboard_file:
    :param file_name_contains:
    :param file_name_ends_with:
    :return:
    """
    examples: List[PromptExample] = all_examples(folder=dashboards_folder, filename=dashboard_file,
                                                 contains=file_name_contains, ends_with=file_name_ends_with)
    for e in examples:
        typer.echo(f'{e.fileName}')
        bare_file_name = e.fileName.parts[-1].split('.')[0]
        #  instance of cpt.prometheus.prompt_model.Title
        for title in e.titles:
            # typer.echo(f'\title{title.name}: {len(title.queries)} queries')
            base_file_name = title.name.replace(' ', '_').replace('/', ' ')
            base_path = Path(PROMETHEUS_REPORT_FOLDER,
                             expressions.__name__, dashboards_folder.parts[-1], bare_file_name)
            os.makedirs(base_path, exist_ok=True)
            f_n = Path(base_path, f"{base_file_name}.json").resolve()
            typer.echo(f'Saving {f_n}')
            with open(f_n, "w") as json_file:
                json.dump(title.dict(), json_file, indent=4)


@app.command()
def match_metrics(dashboards_folder: Path = typer.Option(..., "--folder", dir_okay=True,
                                                         help="Folder with grafana dashboards"),
                  dashboard_file: str = typer.Option(None, "--file",
                                                     help=f"Name of dashboard file. If None all files with "
                                                          f"--suffix value from the folder are loaded"),
                  file_name_contains: str = typer.Option(None, "--contains", "-c",
                                                         help="Filter filenames that contain this string"),
                  file_name_ends_with: str = typer.Option(JSON_SUFFIX, "--suffix", "-s",
                                                          help="Filter filenames that ends with this string")):
    pattern = r'\((.*?)\(label'
    examples: List[PromptExample] = all_examples(folder=dashboards_folder, filename=dashboard_file,
                                                 contains=file_name_contains, ends_with=file_name_ends_with)
    # cpt.prometheus.commands.metrics with contains=None creates metrics_all.json
    metrics_file: Path = Path(PROMETHEUS_REPORT_FOLDER, 'metrics', 'metrics_all.json')
    if metrics_file.is_file():
        metrics_df: pd.DataFrame = pd.read_json(metrics_file)
        file_names, queries, static_labels, titles = prompt_lists(examples)
        available_metrics = metrics_df['metrics']
        for am in available_metrics:
            am_used: bool = False
            for q in flatten_list(queries):
                # remove white spaces
                q = "".join(q.split())
                matches = re.findall(pattern, q)
                if matches:
                    typer.echo(f'match groups : {matches}')
                #  add opening (
                if f'({am}' in q:
                    am_used = True
            typer.echo(f'{am} used {am_used}')


if __name__ == "__main__":
    app()