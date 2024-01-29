from __future__ import annotations

from typing import Optional

from storage.snowflake import EVENT_MMM_BUILD_VERSION_KEY, FROM_TIME_ALIAS, TEST_ENV_KEY, TO_TIME_ALIAS, UUID_COLUMN


def q_env_build(test_env: str, mmm_build: str, result: Optional[str] = None, table_name: Optional[str] = None) -> str:
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
    """Query specified time range."""
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
    Time range, UUID test env and build info grouped by UUID.

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
