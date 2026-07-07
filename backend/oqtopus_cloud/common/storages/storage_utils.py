# job storage objects
JOB_INFO_INPUT_PARAM = "input"
JOB_INFO_COMBINED_PROGRAM_PARAM = "combined_program"
JOB_INFO_TRANSPILE_RESULT_PARAM = "transpile_result"
JOB_INFO_RESULT_PARAM = "result"
JOB_INFO_SSE_LOG_PARAM = "sse_log"

# device storage objects
DEVICE_INFO_FILE = "device_info.json"
DEVICE_INFO_ARCHIVE = "device_info.zip"


def get_device_info_key(device_id: str) -> str:
    return f"devices/{device_id}/{DEVICE_INFO_ARCHIVE}"
