#! /usr/bin/env python
"""Few Shot Prompt for suggesting Prometheus Expressions."""

from __future__ import annotations

import os

from pathlib import Path

import openai
import typer

from langchain.chains import LLMChain
from langchain.prompts import FewShotPromptTemplate
from langchain_openai import AzureChatOpenAI, AzureOpenAI
from loguru import logger

from prometheus import DEFAULT_TEMPERATURE, DEPLOYMENT_HELP, FILE, QUERIES, TITLE, deployment_name_4, deployment_name_35
from prometheus.dashboards_analysis import all_examples, prompt_lists, shot_examples
from prometheus.prompt_model import PromptExample
from prometheus.prompts import DEFAULT_MAX_TOKENS, DEFAULT_PREFIX, DEFAULT_PROM_EXPR_TITLE


app = typer.Typer()

base_dev = os.getenv("LLM_API_URL")
key_dev = os.getenv("LLM_API_KEY")


def init(key, base):
    """Initialize OpenAI API with given key and API base."""
    # None can't be assigned to env var as os.environ["OPENAI_API_KEY"] = key
    # whenever from cpt.prometheus import … is used this function is called
    # and TypeError: str expected, not NoneTyp
    key = key if key is not None else "unknown"
    openai.api_type = "azure"
    openai.api_version = "2023-05-15"
    openai.api_key = key
    openai.api_base = base

    os.environ["OPENAI_API_TYPE"] = "azure"
    os.environ["OPENAI_API_VERSION"] = "2023-05-15"
    os.environ["OPENAI_API_KEY"] = key
    os.environ["AZURE_OPENAI_ENDPOINT"] = base


init(key=key_dev, base=base_dev)


def few_shot_prompt(
    dashboards_folder: Path,
    dashboard_file: str,
    max_length: int,
    debug: bool,
    prefix: str,
    query_title: str,
) -> FewShotPromptTemplate:
    """Prepare prompt for model"""
    examples: list[PromptExample] = all_examples(folder=dashboards_folder, filename=dashboard_file)
    file_names, queries, static_labels, titles = prompt_lists(examples)
    fse: list[dict] = [{TITLE: t[0], QUERIES: t[1], FILE: t[2]} for t in zip(titles, queries, file_names)]
    prompt_template: FewShotPromptTemplate = shot_examples(fse=fse, num_examples=max_length, prefix=prefix)
    if debug:
        logger.info(f'{"=" * 10} Few Shot Prompt Start {"=" * 10}')
        logger.info(f"{prompt_template.format(input=query_title)}")
        logger.info(f'{"=" * 10} Few Shot Prompt End {"=" * 10}\n')
    return prompt_template


def get_model(deployment, max_tokens, temperature):
    match deployment:
        case "gpt-4":
            llm = AzureChatOpenAI(
                temperature=temperature,
                deployment_name=deployment_name_4,
                max_tokens=max_tokens,
            )
        case "gpt-35-turbo":
            llm = AzureOpenAI(
                temperature=temperature,
                deployment_name=deployment_name_35,
                max_tokens=max_tokens,
            )
        case "gpt-35-turbo-chat":
            llm = AzureChatOpenAI(
                temperature=temperature,
                deployment_name=deployment_name_35,
                max_tokens=max_tokens,
            )
        case _:
            llm = None
    return llm


@app.command()
def title_queries(
    dashboards_folder: Path = typer.Option(..., "--folder", dir_okay=True, help="Folder with grafana dashboards"),
    dashboard_file: str = typer.Option(
        None,
        "--file",
        help=f"Dashboard file. If None all files with .json suffix " f"from the folder are loaded",
    ),
    max_length: int = typer.Option(100, "--length", "-l", help="Maximum length of prompt examples"),
    max_tokens: int = typer.Option(DEFAULT_MAX_TOKENS, "--tokens", help="Maximum tokens in response"),
    temperature: float = typer.Option(DEFAULT_TEMPERATURE, help="Model temperature"),
    prefix: str = typer.Option(DEFAULT_PREFIX, "--prefix", "-p", help="Prefix for examples"),
    query_title: str = typer.Option(DEFAULT_PROM_EXPR_TITLE, "--title", help="Query title"),
    deployment: str = typer.Option(deployment_name_35, "--model", "-m", help=DEPLOYMENT_HELP),
    show_prompt: bool = typer.Option(False, help="Show few shot prompt"),
):
    """Prepares Few Shot Prompt from given grafana dashboards and asks model for Prometheus
    expressions with given title."""
    prompt: FewShotPromptTemplate = few_shot_prompt(
        dashboards_folder=dashboards_folder,
        dashboard_file=dashboard_file,
        max_length=max_length,
        prefix=prefix,
        debug=show_prompt,
        query_title=query_title,
    )
    logger.info(f"{deployment}: {query_title}")
    llm = get_model(deployment=deployment, max_tokens=max_tokens, temperature=temperature)
    if llm:
        chain = LLMChain(llm=llm, prompt=prompt)
        response: dict[str, str] = chain.invoke({"input": query_title})
        logger.info(f'{"=" * 10} Response Start {"=" * 10}')
        logger.info(response["text"])
        logger.info(f'{"=" * 10} Response End {"=" * 10}')
    else:
        logger.info(f"Unknown model {deployment}")


if __name__ == "__main__":
    app()
