import datetime

# job storage objects
JOB_INFO_INPUT_PARAM = "input"
JOB_INFO_COMBINED_PROGRAM_PARAM = "combined_program"
JOB_INFO_TRANSPILE_RESULT_PARAM = "transpile_result"
JOB_INFO_RESULT_PARAM = "result"
JOB_INFO_SSE_LOG_PARAM = "sse_log"

# device storage objects
DEVICE_INFO_FILE = "device_info.json"
DEVICE_INFO_ARCHIVE = "device_info.zip"
DEVICE_INFO_UPLOADS_DIR = "uploads"
DEVICE_INFO_HISTORY_DIR = "history"


def _format_utc_timestamp(value: datetime.datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.timezone.utc)
    value = value.astimezone(datetime.timezone.utc)
    return value.strftime("%Y%m%dT%H%M%S%fZ")


def get_device_info_key(device_id: str) -> str:
    return f"devices/{device_id}/{DEVICE_INFO_ARCHIVE}"


def get_device_info_upload_key(device_id: str, upload_id: str) -> str:
    return f"devices/{device_id}/{DEVICE_INFO_UPLOADS_DIR}/{upload_id}/{DEVICE_INFO_ARCHIVE}"


def get_device_info_history_key(
    device_id: str, calibrated_at: datetime.datetime
) -> str:
    return (
        f"devices/{device_id}/{DEVICE_INFO_HISTORY_DIR}/"
        f"{_format_utc_timestamp(calibrated_at)}/{DEVICE_INFO_ARCHIVE}"
    )
