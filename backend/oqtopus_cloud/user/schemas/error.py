# generated by datamodel-codegen:
#   filename:  openapi.yaml
#   timestamp: 2024-10-09T08:20:49+00:00
#   version:   0.25.9

from __future__ import annotations

from pydantic import BaseModel


class UnauthorizedError(BaseModel):
    detail: str


class InternalServerError(BaseModel):
    detail: str


class NotFoundError(BaseModel):
    detail: str


class BadRequest(BaseModel):
    detail: str
