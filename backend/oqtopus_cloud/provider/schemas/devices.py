# generated by datamodel-codegen:
#   filename:  openapi.yaml
#   timestamp: 2024-10-14T08:42:32+00:00
#   version:   0.25.9

from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import AwareDatetime, BaseModel, Field, RootModel


class DeviceStatusUpdate(BaseModel):
    command: Annotated[
        Literal["DeviceStatusUpdate"], Field(examples=["DeviceStatusUpdate"])
    ]
    status: Optional[Literal["available", "unavailable"]] = None
    available_at: Annotated[
        Optional[AwareDatetime], Field(None, examples=["2023-09-10T14:00:00+09:00"])
    ]
    """
    Parameter mandatory and valid for status 'unavailable'
    """


class DevicePendingJobsUpdate(BaseModel):
    command: Annotated[
        Literal["DevicePendingJobsUpdate"], Field(examples=["DevicePendingJobsUpdate"])
    ]
    n_pending_jobs: Optional[int] = None


class DeviceCalibrationUpdate(BaseModel):
    command: Annotated[
        Literal["DeviceCalibrationUpdate"], Field(examples=["DeviceCalibrationUpdate"])
    ]
    device_info: Annotated[
        Optional[str],
        Field(
            None,
            examples=[
                "{'n_nodes': 512, 'calibration_data': {'qubit_connectivity': ['(1,4)', '(4,5)', '(5,8)'], 't1': {'0': 55.51, '1': 37.03, '2': 57.13}}"
            ],
        ),
    ]
    """
    json format calibration_data and n_nodes etc
    """
    calibrated_at: Annotated[
        Optional[AwareDatetime], Field(None, examples=["2023-09-10T14:00:00+09:00"])
    ]
    """
    Parameter mandatory and valid if calibrationData not null
    """


class DeviceDataUpdate(
    RootModel[
        Union[DeviceStatusUpdate, DevicePendingJobsUpdate, DeviceCalibrationUpdate]
    ]
):
    root: Annotated[
        Union[DeviceStatusUpdate, DevicePendingJobsUpdate, DeviceCalibrationUpdate],
        Field(discriminator="command"),
    ]


class DeviceDataUpdateResponse(BaseModel):
    message: Annotated[
        str, Field("Device's data updated", examples=["Device's data updated"])
    ]
