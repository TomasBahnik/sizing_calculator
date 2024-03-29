from __future__ import annotations


DEFAULT_PREFIX = """You are looking for Prometheus Query Language expressions. Given the title of that expression  
give me comma separated list of expressions best fitting that title. Ignore labels. Use prepared examples"""
DEFAULT_PROM_EXPR_TITLE = "Average pod CPU"
DEFAULT_MAX_TOKENS: int = 256

"""
mean = df.mean()
high = df.columns[df.apply(lambda x: x > 2 * mean[x.name]).sum() > 0]

mean = df.mean()
cols = [col for col in df.columns if (df[col] > 2 * mean[col]).any()]
"""

PROMETHEUS_POD_CPU_PROMPT = """Here is data about pod CPU usage. We are looking for columns with values higher
than twice a mean value. If there are such columns give me a list of those columns.
In case no such columns are found inform me with "no columns with values above 2 x mean" message
"""

PROMETHEUS_POD_CPU_PROMPT_COUNTS = """Here is data about pod CPU usage. We are looking for columns with values higher
than twice a mean value. If there are such columns give me count of those columns.
In case no such columns are found inform me with "0 columns with values above 2 x mean" message
"""

COMPARE_PROMPT = """Dataframe contains columns 'test_0' and 'test_1'. Data in those two columns are durations measured
in two subsequent measurements.
Question: Decide if these two measurements are statistically equivalent
If you cannot decide for whatever reason answer "Can't decide"
"""

TRIVIAL_COMPARE_PROMPT = """Dataframe contains 2 columns 'test_0' and 'test_1'. Data in those two columns
are durations measured in two subsequent measurements.
Question: Decide if the means of those two measurements are equal within one standard deviation. 
Take as standard deviation the smaller one of those two measurements.
If you cannot decide for whatever reason answer "Can't decide"
"""
"""
std = np.min(df.std())
mean_0 = df['test_0'].mean()
mean_1 = df['test_1'].mean()

if abs(mean_0 - mean_1) <= std:
    print('Means are equal within one standard deviation')
else:
    print("Can't decide")

import pandas as pd
import numpy as np
from scipy.stats import ttest_ind

df = pd.read_csv("data.csv")
test_0 = df["test_0"]
test_1 = df["test_1"]
t, p = ttest_ind(test_0, test_1, equal_var=True)
if p < 0.05:
    print("Not equivalent")
else:
    print("Equivalent")
"""
