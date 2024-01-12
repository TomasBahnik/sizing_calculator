import logging

import numpy as np
import pandas as pd
from scipy.stats import ttest_ind
from scipy.stats._stats_py import TtestResult

from llm import app

# from prometheus.prompts import *

TEST_1 = 'test_1'

TEST_0 = 'test_0'

logger = logging.getLogger(__name__)


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


if __name__ == "__main__":
    app()
