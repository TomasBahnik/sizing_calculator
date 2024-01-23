import os
from pathlib import Path

if not os.getenv('PYCPT_HOME'):
    raise Exception('PYCPT_HOME env var not set')

PYCPT_HOME = Path(os.getenv('PYCPT_HOME')).resolve()
if not PYCPT_HOME.exists():
    raise Exception(f'PYCPT_HOME {PYCPT_HOME} does not exist')

PYCPT_ARTEFACTS: Path = Path(PYCPT_HOME, '../cpt_artefacts').resolve()
SLA_TABLES_FOLDER: Path = Path(PYCPT_HOME, 'sla_tables')
