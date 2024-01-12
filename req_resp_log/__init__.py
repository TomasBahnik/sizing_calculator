import re

# ended with a "Pass" status (Duration: 0.8570 Wasted Time: 0.3640)
# (Duration: 14.7360 Think Time: 0.0010 Wasted Time: 3.5380)
# t=00006915ms
# Virtual User Script started at : 2020-10-05 11:27:34
# {"operationName":"GetApplicationMode","variables":{}
# operationName -> OPERATION_NAME const can't escape '\' in f strings use """?
# OPERATION_NAME_START = r"{\"operationName\":\"(\w+)\",\"variables\":(\{.*\})"

# load steps and actions from output.txt
# used as LOG_TIMESTAMP_RE = re.compile(r"t=(\d+)ms")
# t=00029357ms: Step 21: Click on Browse button started    [MsgId: MMSG-205180]	[MsgId: MMSG-205180]

START_ITER_REGEXP = r"Starting\siteration\s(\d+)"
START_ITER = re.compile(START_ITER_REGEXP)
NOTIFY_TRANSACTION = 'Notify: Transaction'
START_TRX = re.compile(NOTIFY_TRANSACTION + r"\s\"(.*)\"\sstarted")
TRX_COMMON = r"\s\"(.*)\"\sended\swith\sa\s\"(.*)\"\sstatus"
END_TRX = re.compile(NOTIFY_TRANSACTION + TRX_COMMON)
END_TRX_PASSED_DURATION = re.compile(r".*\(Duration:\s(\d+\.\d+)\)")
END_TRX_PASSED_DURATION_WASTED = re.compile(r".*\(Duration:\s(\d+\.\d+)\sWasted\sTime:\s(\d+\.\d+)\)")
END_TRX_PASSED_DURATION_THINK = re.compile(r".*\(Duration:\s(\d+\.\d+)\sThink\sTime:\s(\d+\.\d+)\)")
END_TRX_PASSED_ALL_TIMES = \
    re.compile(r".*\(Duration:\s(\d+\.\d+)\sThink\sTime:\s(\d+\.\d+)\sWasted\sTime:\s(\d+\.\d+)\)")
LOG_TIMESTAMP_RE = re.compile(r"t=(\d+)ms")
SCRIPT_STARTED_RE = re.compile(r"Virtual User Script.+(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})")
OPERATION_NAME_START = r"{\"operationName\":\"(\w+)\","
OPERATION_NAME_START_RE = re.compile(OPERATION_NAME_START)
RUNTIME_SETTINGS_FILE_RE = re.compile(r"Run-Time Settings file.+: \"(.+)\\default.cfg")
FE_APP_URL_RE = re.compile(r"t=\d+ms: Request headers for \"(.+\.\w+/)\" \(")
SCRIPT_STEP_OUTPUT_RE = r't=(\d+)ms:\sStep\s([\d\.]+):\s([a-zA-Z\s"]+[\w"])\s{4}'
SCRIPT_STEP_OUTPUT_RE_COMPILED = re.compile(SCRIPT_STEP_OUTPUT_RE)
