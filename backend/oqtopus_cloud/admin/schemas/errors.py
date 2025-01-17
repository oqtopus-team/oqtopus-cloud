# This file contains the error wrapper classes for the API

from __future__ import (
    annotations,
)

from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorResponse(JSONResponse):
    pass


class Detail(BaseModel):
    """A simple message response.

    Args:
        BaseModel: The base class for Pydantic models.

    Attributes:
        message (str): The message to return.

    """

    message: str


class InternalServerErrorResponse(ErrorResponse):
    """
    Represents an internal server error response.

    Args:
        message (str): The error message or details of the internal server error.

    Attributes:
        status_code (int): The HTTP status code for the internal server error response.
        content (dict): The content of the internal server error response, containing the error detail.

    """

    def __init__(
        self,
        message: str,
    ):
        super().__init__(
            status_code=500,
            content={"message": message},
        )


class NotFoundErrorResponse(ErrorResponse):
    """
    Represents an error response for a resource not found.

    Args:
        message (str): The detailed error message.

    Attributes:
        status_code (int): The HTTP status code of the error response.
        content (dict): The content of the error response.

    """

    def __init__(
        self,
        message: str,
    ):
        super().__init__(
            status_code=404,
            content={"message": message},
        )


class BadRequestErrorResponse(ErrorResponse):
    """
    Represents an error response for a bad request.

    Args:
        message (str): The detailed error message.

    Attributes:
        status_code (int): The HTTP status code of the error response.
        content (dict): The content of the error response.

    """

    def __init__(
        self,
        message: str,
    ):
        super().__init__(
            status_code=400,
            content={"message": message},
        )
