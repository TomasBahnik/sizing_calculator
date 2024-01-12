import re

from metrics import MIBS, GIBS

LINKED_TABLES_PERCENTAGE = '1-n relations between tables (total percentage of linked tables)'
MAX_COLUMNS_PER_TABLE = 'Max columns per table'
HIGH_AVG_COLUMNS_PER_TABLE = 'High average columns per table'
AVG_COLUMNS_PER_TABLE = 'Average columns per table'

common_data_volume = {AVG_COLUMNS_PER_TABLE: 20,
                      HIGH_AVG_COLUMNS_PER_TABLE: 300,
                      MAX_COLUMNS_PER_TABLE: 5000,
                      LINKED_TABLES_PERCENTAGE: 25,
                      'Average # of terms assigned on table level': 4,
                      'Max # of terms assigned on table level': 11,
                      'Average # of terms assigned on column level': 4,
                      'High average # of terms assigned on column level': 9,
                      'Max # of terms assigned on column level': 25,
                      'Average historical versions of entity': 5,
                      'Max historical version of entity': 20}
units_conversion = {"Mi": MIBS, "Gi": GIBS, "G": GIBS, "m": 0.001}
# use for all pd.Timestamps - bad conversion to Snowflake TIMESTAPMPNTZ
GMT_TZ = 'GMT'
EVENT_MMM_BUILD_VERSION_KEY = 'mmmBuildVersion'
MMM_DB_METRICS_KEY = 'mmmDbMetrics'
UUID_KEY = "uuid".upper()
UUID_COLUMN = UUID_KEY
TEST_ENV_KEY = "testEnv"
CATALOG_ITEMS_KEY = 'catalogItems'
END_ISO_TIME = "endIsoTime"
