import pandas as pd
import pytz
import typer
from pandas import DataFrame, Series
from snowflake.connector import SnowflakeConnection

from prometheus.common import TIMESTAMP_KEY
from constants import GMT_TZ, TEST_ENV_KEY, END_ISO_TIME, UUID_COLUMN
from storage.snowflake import FROM_TIME_ALIAS, TO_TIME_ALIAS, API_TESTS_CU_RUN_INFO_TABLE_NAME, \
    API_TESTS_CU_RAW_DATA_TABLE_NAME, API_TESTS_CU_LIST_TABLE_NAME
from storage.snowflake.queries import q_uuid


def get_df(query: str, con: SnowflakeConnection, dedup: bool = True) -> pd.DataFrame:
    """
    dedup by default - no other way how to get rid of occasionally duplicated save
    no primary keys for not-normalized tables
    """
    df: pd.DataFrame = con.cursor().execute(query).fetch_pandas_all()
    if dedup:
        df = df.drop_duplicates()
    return df


def add_tz(series: pd.Series, tz: str = GMT_TZ) -> pd.Series:
    return series.apply(lambda x: pd.Timestamp(x, tz=tz))


def localize_series_timezone(series: pd.Series, tz: pytz.tzinfo = pytz.UTC) -> pd.Series:
    return series.apply(lambda x: x.tz_localize(tz=tz))


def get_jobs_df(query: str, con: SnowflakeConnection) -> pd.DataFrame:
    """Explicitly add timezone to timestamp
    (maybe changed behaviour of pandas connector in v 3.0.1)
    """
    job_df = get_df(query=query, con=con)
    time_stamp_ser = localize_series_timezone(job_df[TIMESTAMP_KEY])
    job_df[TIMESTAMP_KEY] = time_stamp_ser
    return job_df


def dedup_df(query: str, con: SnowflakeConnection) -> DataFrame:
    #  potentially changed behavior because of default drop duplicates
    df: DataFrame = get_df(con=con, query=query)
    if df.empty:
        typer.echo(f"Empty dataframe for query: {query}")
        exit(3)
    df_dedup = df.drop_duplicates(subset=[TEST_ENV_KEY, END_ISO_TIME])
    return df_dedup


def localize_to_gmt(df: DataFrame) -> DataFrame:
    """
    Timestamp is stored in Snowflake as TIMESTAMPNTZ as UTC time
    SQL query returns this UTC value but WITHOUT TZ.
    To DISPLAY it correctly localize it back to UTC
    """
    df[FROM_TIME_ALIAS] = localize_series_timezone(df[FROM_TIME_ALIAS])
    df[TO_TIME_ALIAS] = localize_series_timezone(df[TO_TIME_ALIAS])
    return df


def round_from_to_times(df: DataFrame) -> DataFrame:
    df[FROM_TIME_ALIAS] = df[FROM_TIME_ALIAS].apply(lambda x: x.floor('S'))
    df[TO_TIME_ALIAS] = df[TO_TIME_ALIAS].apply(lambda x: x.ceil('S'))
    return df


def round_localize_gmt(df: DataFrame) -> DataFrame:
    df = round_from_to_times(df=df)
    return localize_to_gmt(df=df)


def check_unique_uuid(new_uuid: str, table: str, connection: SnowflakeConnection):
    q = q_uuid(uuid=new_uuid, table_name=table)
    df: DataFrame = get_df(query=q, con=connection)
    uuids: Series = df[UUID_COLUMN]
    if new_uuid in uuids.values:
        raise ValueError(f"Duplicated UUID: {new_uuid}")


def lr_raw_data_df(uuid: str, connection: SnowflakeConnection) -> DataFrame:
    q = q_uuid(uuid=uuid, table_name=API_TESTS_CU_RAW_DATA_TABLE_NAME)
    return get_df(con=connection, query=q)


def lr_run_info_df(uuid: str, connection: SnowflakeConnection) -> DataFrame:
    q = q_uuid(uuid=uuid, table_name=API_TESTS_CU_RUN_INFO_TABLE_NAME)
    return get_df(con=connection, query=q)


def lr_list_df(uuid: str, connection: SnowflakeConnection) -> DataFrame:
    q = q_uuid(uuid=uuid, table_name=API_TESTS_CU_LIST_TABLE_NAME)
    return get_df(con=connection, query=q)
