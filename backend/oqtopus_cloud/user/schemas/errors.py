# This file contains the error wrapper classes for the API

from __future__ import (
    annotations,
)

from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorResponse(JSONResponse):
    pass


class Message(BaseModel):
    """A simple message response.

    Args:
        BaseModel: The base class for Pydantic models.

    Attributes:
        message (str): The message to return.

    """

    message: str


class BadRequestResponse(ErrorResponse):
    """
    Represents a response for a bad request.

    Args:
        message (str): The detailed error message.

    Attributes:
        status_code (int): The HTTP status code for the response.
        content (dict): The content of the response.

    """

    def __init__(
        self,
        message: str,
    ):
        super().__init__(
            status_code=400,
            content={"message": message},
        )


class InternalServerErrorResponse(ErrorResponse):
    """
    Represents an internal server error response.

    Args:
        message (str): The error message or details of the internal server error.

    Attributes:
        status_code (int): The HTTP status code for the internal server error response.
        content (dict): The content of the internal server error response, containing the error message.

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


class ConflictErrorResponse(ErrorResponse):
    """
    Represents an error response for a conflict (HTTP status code 409).

    Args:
        message (str): The detailed error message.

    Attributes:
        status_code (int): The HTTP status code for the error response (409).
        content (dict): The content of the error response, containing the detail message.

    """

    def __init__(
        self,
        message: str,
    ):
        super().__init__(
            status_code=409,
            content={"message": message},
        )


class ForbiddenErrorResponse(ErrorResponse):
    """
    Represents an error response for a forbidden request.

    Args:
        detail (str): The detailed error message.

    Attributes:
        status_code (int): The HTTP status code of the error response.
        content (dict): The content of the error response.
    """

    def __init__(
        self,
        message: str,
    ):
        super().__init__(
            status_code=403,
            content={"message": message},
        )
