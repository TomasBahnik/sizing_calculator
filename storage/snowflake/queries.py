from __future__ import annotations

from typing import List

from pandas import DataFrame
from snowflake.connector import SnowflakeConnection

from storage.snowflake import (
    EVENT_MMM_BUILD_VERSION_KEY,
    FROM_TIME_ALIAS,
    PERIOD_UTC_COLUMN,
    TEST_ENV_KEY,
    TO_TIME_ALIAS,
    UUID_COLUMN,
)


def q_env_build(
    test_env: str, mmm_build: str, result: str = None, table_name: str = None
) -> str:
    env = f""""{TEST_ENV_KEY}" = '{test_env}'"""
    build = f""""{EVENT_MMM_BUILD_VERSION_KEY}" = '{mmm_build}'"""
    q = (
        f"SELECT * FROM {table_name} WHERE RESULT='{result}' AND {build} AND {env}"
        if result
        else f"SELECT * FROM {table_name} WHERE {build} AND {env}"
    )
    return q


def q_from_to(
    from_time: str,
    to_time: str,
    result: str | None,
    timestamp_field: str,
    table_name: str,
) -> str:
    """Query specified time range. `result` is either pass or fail and RESULT
    is the table field in API_TESTS_SU table
    """
    lower_bound = f""""{timestamp_field}" > '{from_time}'"""
    upper_bound = f""""{timestamp_field}" < '{to_time}'"""
    q = (
        f"SELECT * FROM {table_name} WHERE RESULT='{result}' AND {lower_bound} AND {upper_bound}"
        if result
        else f"SELECT * FROM {table_name} WHERE {lower_bound} AND {upper_bound}"
    )
    return q


def q_uuid(uuid: str, table_name: str) -> str:
    q = f"SELECT * FROM {table_name} WHERE UUID='{uuid}'"
    return q


def q_from_to_by_uuid(timestamp_field: str, table_name: str) -> str:
    """
    Time range, UUID test env and build info grouped by UUID
    :param timestamp_field: rounded down on seconds is used as from time, rounded up on seconds as to time
    :param table_name: API or jobs table
    :return: SQL query
    """
    f_t_q = f'min("{timestamp_field}") as {FROM_TIME_ALIAS}'
    t_t_q = f'max("{timestamp_field}") as {TO_TIME_ALIAS}'
    #  double quotes around camel case
    fields = f'{UUID_COLUMN}, "{TEST_ENV_KEY}", "{EVENT_MMM_BUILD_VERSION_KEY}"'
    q = f"select {f_t_q}, {t_t_q}, {fields} from {table_name} group by {fields} order by {FROM_TIME_ALIAS}"
    return q


# Notin tables synchronized to Snowflake
NOTION_API_TESTS_TABLE = "PERFORMANCE_TESTING_DB_LIST_OF_API_TESTS"
NOTION_JOB_TESTS_TABLE = "PERFORMANCE_TESTING_DB_LIST_OF_DOC_FLOW_TESTS"


def q_notion(
    columns: List[str], table: str, connection: SnowflakeConnection
) -> DataFrame:
    """columns from Notion table with non-empty UUID ordered by period"""
    raw_fields = [
        f"RAW_DATA:properties.{f}.rich_text[0].text.content::varchar as {f}"
        for f in columns
    ]
    query_fields = ",".join(raw_fields)
    select_clause = f"SELECT {query_fields}"
    from_clause = f"FROM DWH_PROD.NOTION.{table}"
    orderby_clause = f"ORDER BY {PERIOD_UTC_COLUMN}"
    query = f"{select_clause} {from_clause} {orderby_clause}"
    df: DataFrame = connection.cursor().execute(query).fetch_pandas_all()
    return df[df[UUID_COLUMN].notnull()]
