__all__ = (
    "uuid7",
    "uuid7str",
    "time_ns",
    "check_timing_precision",
    "uuid_to_datetime",
)

import datetime
import time
import uuid
from typing import Callable, Optional, Union

time_ns = time.time_ns

def uuid7(
    ns: Optional[int] = None,
    as_type: Optional[str] = None,
    time_func: Callable[[], int] = time_ns,
    _last=[0, 0, 0, 0],
    _last_as_of=[0, 0, 0, 0],
) -> Union[uuid.UUID, str, int, bytes]: ...
def uuid7str(ns: Optional[int] = None) -> str: ...
def check_timing_precision(
    timing_func: Optional[Callable[[], int]] = None,
) -> str: ...
def uuid_to_datetime(
    s: Union[str, uuid.UUID, int],
    suppress_error=True,
) -> Optional[datetime.datetime]: ...
