import pandas as pd

from metrics import TIMESTAMP_COLUMN, CONTAINER_COLUMN, POD_COLUMN, MIBS
from sizing.calculator import CPU_RESOURCE, MEMORY_RESOURCE

time_delta = pd.Timedelta(seconds=1)
cpu_data = {TIMESTAMP_COLUMN: [pd.Timestamp.now() - time_delta, pd.Timestamp.now()],
            CONTAINER_COLUMN: ['container1', 'container2'],
            POD_COLUMN: ['pod1', 'pod2'],
            CPU_RESOURCE.limit: [1, 0.9],
            CPU_RESOURCE.request: [0.5, 0.4],
            CPU_RESOURCE.measured: [0.6, 0.7]}
CPU_DF = pd.DataFrame(cpu_data)

mem_data = {TIMESTAMP_COLUMN: [pd.Timestamp.now() - time_delta, pd.Timestamp.now()],
            CONTAINER_COLUMN: ['container1', 'container2'],
            POD_COLUMN: ['pod1', 'pod2'],
            MEMORY_RESOURCE.limit: [10 * MIBS, 9 * MIBS],
            MEMORY_RESOURCE.request: [5 * MIBS, 4 * MIBS],
            MEMORY_RESOURCE.measured: [6 * MIBS, 7 * MIBS]}
MEM_DF = pd.DataFrame(mem_data)
