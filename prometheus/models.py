import logging
import os
from pathlib import Path
from typing import List, Tuple

import numpy as np
import openai
import pandas as pd
import typer
from langchain import FewShotPromptTemplate
from langchain.chains import LLMChain
from langchain.chat_models import AzureChatOpenAI
from langchain.llms import AzureOpenAI
from pandasai import PandasAI
from scipy.stats import ttest_ind
from scipy.stats._stats_py import TtestResult

from metrics import DEFAULT_TIME_DELTA_HOURS, PROMETHEUS_URL, PORTAL_ONE_NS, DEFAULT_PORTAL_GRP_KEYS
from prometheus import DEPLOYMENT_HELP, deployment_name_4, deployment_name_35, DEFAULT_TEMPERATURE
from metrics.collector import PrometheusCollector, TimeRange
from prometheus.const import *
from prometheus.dashboards_analysis import shot_examples, all_examples, prompt_lists
from prometheus.prompt_model import PromptExample

TEST_1 = 'test_1'

TEST_0 = 'test_0'

app = typer.Typer()
logger = logging.getLogger(__name__)

base_dev = 'https://ataopenaidev-us-east.openai.azure.com/'
key_dev = os.getenv('LLM_API_KEY')


def init(key, base):
    # None can't be assigned to env var as os.environ["OPENAI_API_KEY"] = key
    # whenever from cpt.prometheus import … is used this function is called
    # and TypeError: str expected, not NoneTyp
    key = key if key is not None else 'unknown'
    openai.api_type = 'azure'
    openai.api_version = '2023-05-15'
    openai.api_key = key
    openai.api_base = base

    os.environ["OPENAI_API_TYPE"] = "azure"
    os.environ["OPENAI_API_VERSION"] = '2023-05-15'
    os.environ["OPENAI_API_KEY"] = key
    os.environ["OPENAI_API_BASE"] = base


init(key=key_dev, base=base_dev)


def few_shot_prompt(dashboards_folder: Path, dashboard_file: str, max_length: int,
                    debug: bool, prefix: str, query_title: str) -> FewShotPromptTemplate:
    """ Prepare prompt for model"""
    examples: List[PromptExample] = all_examples(folder=dashboards_folder, filename=dashboard_file)
    file_names, queries, static_labels, titles = prompt_lists(examples)
    fse: List[dict] = [{TITLE: t[0], QUERIES: t[1], FILE: t[2]} for t in zip(titles, queries, file_names)]
    prompt_template: FewShotPromptTemplate = shot_examples(fse=fse, num_examples=max_length,
                                                           prefix=prefix)
    if debug:
        typer.echo(f'{"=" * 10} Few Shot Prompt Start {"=" * 10}')
        typer.echo(f'{prompt_template.format(input=query_title)}')
        typer.echo(f'{"=" * 10} Few Shot Prompt End {"=" * 10}\n')
    return prompt_template


def get_model(deployment, max_tokens, temperature):
    match deployment:
        case 'gpt-4':
            llm = AzureChatOpenAI(temperature=temperature, deployment_name=deployment_name_4, max_tokens=max_tokens)
        case 'gpt-35-turbo':
            llm = AzureOpenAI(temperature=temperature, deployment_name=deployment_name_35, max_tokens=max_tokens)
        case 'gpt-35-turbo-chat':
            llm = AzureChatOpenAI(temperature=temperature, deployment_name=deployment_name_35, max_tokens=max_tokens)
        case _:
            llm = None
    return llm


@app.command()
def title_queries(dashboards_folder: Path = typer.Option(..., "--folder", dir_okay=True,
                                                         help="Folder with grafana dashboards"),
                  dashboard_file: str = typer.Option(None, "--file",
                                                     help=f"Dashboard file. If None all files with .json suffix "
                                                          f"from the folder are loaded"),
                  max_length: int = typer.Option(100, "--length", "-l", help="Maximum length of prompt examples"),
                  max_tokens: int = typer.Option(DEFAULT_MAX_TOKENS, "--tokens", help="Maximum tokens in response"),
                  temperature: float = typer.Option(DEFAULT_TEMPERATURE, help="Model temperature"),
                  prefix: str = typer.Option(DEFAULT_PREFIX, "--prefix", "-p", help="Prefix for examples"),
                  query_title: str = typer.Option(DEFAULT_PROM_EXPR_TITLE, "--title", help="Query title"),
                  deployment: str = typer.Option(deployment_name_35, "--model", "-m", help=DEPLOYMENT_HELP),
                  show_prompt: bool = typer.Option(False, help="Show few shot prompt")):
    """ Prepares Few Shot Prompt from given grafana dashboards and asks model for Prometheus
    expressions with given title."""
    prompt: FewShotPromptTemplate = few_shot_prompt(dashboards_folder=dashboards_folder,
                                                    dashboard_file=dashboard_file,
                                                    max_length=max_length, prefix=prefix,
                                                    debug=show_prompt, query_title=query_title)
    typer.echo(f"{deployment}: {query_title}")
    llm = get_model(deployment=deployment, max_tokens=max_tokens, temperature=temperature)
    if llm:
        chain = LLMChain(llm=llm, prompt=prompt)
        response: str = chain.run(query_title)
        typer.echo(f'{"=" * 10} Response Start {"=" * 10}')
        typer.echo(response)
        typer.echo(f'{"=" * 10} Response End {"=" * 10}')
    else:
        typer.echo(f"Unknown model {deployment}")


def means_compare(df: pd.DataFrame):
    """
    Check if the mean diff is within smaller std dev
    :param df:
    :return:
    """
    std = np.min(df.std())
    test_0 = df[TEST_0].dropna()
    test_1 = df[TEST_1].dropna()
    mean_0 = test_0.mean()
    mean_1 = test_1.mean()
    mean_diff = abs(mean_0 - mean_1)
    if mean_diff <= std:
        print(f'mean diff {mean_diff} <= {std}')
    else:
        print(f'mean diff {mean_diff} > {std}')


def t_test_compare(df: pd.DataFrame):
    """
    https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind.html
    v. 1.11.1
    :param df:
    :return:
    """
    test_0 = df[TEST_0]
    test_1 = df[TEST_1]
    t_test_result: TtestResult = ttest_ind(list(test_0), list(test_1), equal_var=True, nan_policy='omit')
    if t_test_result.pvalue < 0.05:
        print(f"pvalue: {t_test_result.pvalue} : Not equivalent")
    else:
        print(f"pvalue: {t_test_result.pvalue} : equivalent")


def portal_namespaces(tuple_columns: List[Tuple[str, ...]]) -> List[str]:
    """ Unique and sorted namespaces as first element in df column as tuple"""
    # 1st element as in grp_keys
    namespaces = sorted(list(set([col[0] for col in tuple_columns])))
    return namespaces


@app.command()
def cpu_usage(prompt: str = typer.Option(PROMETHEUS_POD_CPU_PROMPT, "--prompt", "-p", help="Prompt for CPU"),
              start_time: str = typer.Option(None, "--start", "-s", help="Start time of period ISO format "
                                                                         "'2023-07-21T04:43:00-0200'"),
              end_time: str = typer.Option(None, "--end", "-e",
                                           help="End time of period. end_time = now if None, ISO format with tz "),
              delta_hours: int = typer.Option(DEFAULT_TIME_DELTA_HOURS, "--delta", "-d",
                                              help="start time = end_time - delta"),
              clear_cache: bool = typer.Option(False, "--clear-cache", "-c", help="Clear pandas AI cache"),
              namespaces: str = typer.Option(PORTAL_ONE_NS, "--ns", help="list of namespaces separated by |,"
                                                                         "None=all")
              ):
    """ Pandas AI for prometheus CPU usage"""
    time_range = TimeRange(start_time=start_time, end_time=end_time, delta_hours=delta_hours)
    prom: PrometheusCollector = PrometheusCollector(PROMETHEUS_URL, time_range=time_range)
    # grp keys for PromQL = grp keys for namespaces
    cpu_df: pd.DataFrame = prom.portal_cpu_df(grp_keys=DEFAULT_PORTAL_GRP_KEYS, namespace=namespaces)
    tuple_columns = cpu_df.columns
    namespaces = portal_namespaces(tuple_columns=tuple_columns)
    typer.echo(f'Prompt : {prompt}')
    typer.echo(f'{len(namespaces)} namespaces')
    llm = get_model(deployment=deployment_name_35, max_tokens=DEFAULT_MAX_TOKENS, temperature=DEFAULT_TEMPERATURE)
    pandas_ai = PandasAI(llm)
    if clear_cache:
        typer.echo("Clear cache")
        pandas_ai.clear_cache()
    for ns in namespaces:
        # the generated code is cached and reused after 1st namespace
        ns_columns = [col for col in tuple_columns if col[0] == ns]
        df = cpu_df[ns_columns]
        answer = pandas_ai.run(data_frame=df, prompt=prompt)
        typed_answer = eval(answer)
        if isinstance(typed_answer, List):
            # Prompt class: prompt: str, check_answer: assertions
            assert len(ns_columns) >= len(typed_answer)
            typer.echo(f'namespace: {ns}: {len(ns_columns)} columns: answer length: {len(typed_answer)}')
        else:
            typer.echo(f"answer type after eval: {type(typed_answer)}")
            typer.echo(f'namespace: {ns}: {len(ns_columns)} columns:  answer: {answer}')


if __name__ == "__main__":
    app()
