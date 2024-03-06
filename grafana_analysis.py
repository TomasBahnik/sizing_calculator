#! /usr/bin/env python
"""Grafana dashboards analysis commands."""

from __future__ import annotations

import json
import os

from pathlib import Path

import typer

from loguru import logger
from pandas import DataFrame

from prometheus import FILE, QUERIES, STATIC_LABEL, TITLE
from prometheus.dashboards_analysis import JSON_SUFFIX, all_examples, prompt_lists
from prometheus.prompt_model import PromptExample
from settings import settings


app = typer.Typer()


@app.command()
def grafana_report(
    dashboards_folder: Path = typer.Option(..., "--folder", dir_okay=True, help="Folder with grafana dashboards"),
    dashboard_file: str = typer.Option(
        None,
        "--file",
        help="Name of dashboard file. If None all files with --suffix value from the folder are loaded",
    ),
    file_name_contains: str = typer.Option(None, "--contains", "-c", help="Filter filenames that contain this string"),
    file_name_ends_with: str = typer.Option(
        JSON_SUFFIX,
        "--suffix",
        "-s",
        help="Filter filenames that ends with this string",
    ),
):
    """HTML report with prometheus metrics to stdout."""
    examples: list[PromptExample] = all_examples(
        folder=dashboards_folder,
        filename=dashboard_file,
        contains=file_name_contains,
        ends_with=file_name_ends_with,
    )
    file_names, queries, static_labels, titles = prompt_lists(examples)
    tmp_dict = {
        FILE: file_names,
        TITLE: titles,
        QUERIES: queries,
        STATIC_LABEL: static_labels,
    }
    tmp_df = DataFrame(data=tmp_dict)
    tmp_df.sort_values(by=[FILE, TITLE], inplace=True, ignore_index=True)
    base_path = Path(settings.prometheus_report_folder, grafana_report.__name__)
    os.makedirs(name=base_path, exist_ok=True)
    html_file = Path(
        base_path,
        f"{dashboards_folder.parts[-1]}_{file_name_contains}_{file_name_ends_with[1:]}.html",
    )
    if dashboard_file:
        html_file = Path(f"{dashboards_folder.parts[-1]}_{dashboard_file}_{file_name_ends_with[1:]}.html")
    logger.info(f"Saving to {html_file.resolve()}")
    tmp_df.to_html(html_file, index=True)


@app.command()
def prom_expressions(
    dashboards_folder: Path = typer.Option(..., "--folder", dir_okay=True, help="Folder with grafana dashboards"),
    dashboard_file: str = typer.Option(
        None,
        "--file",
        help="Name of dashboard file. If None all files with --suffix value from the folder are loaded",
    ),
    file_name_contains: str = typer.Option(None, "--contains", "-c", help="Filter filenames that contain this string"),
    file_name_ends_with: str = typer.Option(
        JSON_SUFFIX,
        "--suffix",
        "-s",
        help="Filter filenames that ends with this string",
    ),
):
    """
    Store Prometheus expression as dumped cpt.prometheus.prompt_model.Title so it can be loaded back to objects.

    :param dashboards_folder:
    :param dashboard_file:
    :param file_name_contains:
    :param file_name_ends_with:
    :return:
    """
    examples: list[PromptExample] = all_examples(
        folder=dashboards_folder,
        filename=dashboard_file,
        contains=file_name_contains,
        ends_with=file_name_ends_with,
    )
    for e in examples:
        logger.info(f"{e.fileName}")
        bare_file_name = e.fileName.parts[-1].split(".")[0]
        #  instance of cpt.prometheus.prompt_model.Title
        for title in e.titles:
            base_file_name = title.name.replace(" ", "_").replace("/", " ")
            base_path = Path(
                settings.prometheus_report_folder,
                prom_expressions.__name__,
                dashboards_folder.parts[-1],
                bare_file_name,
            )
            os.makedirs(base_path, exist_ok=True)
            f_n = Path(base_path, f"{base_file_name}.json").resolve()
            logger.info(f"Saving {f_n}")
            with open(f_n, "w") as json_file:
                json.dump(title.model_dump(), json_file, indent=4)


if __name__ == "__main__":
    app()
