import logging
import os
from pathlib import Path

from cpt.constants import CPT_HOME

PYCPT_LOG = "pycpt.log"


# module level logging : logger = logging.getLogger(__name__)
# class level logging : self.logger = logging.getLogger(cpt.logging.fullname(self))

def setup_logging(folder: str = f"{CPT_HOME}/log",
                  filename: str = PYCPT_LOG, level: int = logging.INFO):
    if folder:
        os.makedirs(folder, exist_ok=True)
        filename = Path(folder, filename).resolve()
    logging_format = '[%(asctime)s] %(name)s:%(funcName)s:%(lineno)d %(levelname)s - %(message)s'
    logging.basicConfig(filename=filename, level=level, format=logging_format)


def fullname(o):
    """ fully qualified class name"""
    klass = o.__class__
    module = klass.__module__
    if module == 'builtins':
        return klass.__qualname__  # avoid outputs like 'builtins.str'
    return module + '.' + klass.__qualname__


# the only place where logging is configured
setup_logging()
