"""Typed reference-catalog boundary models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DevStandardReference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    path: str = Field(min_length=1)
    description: str = Field(min_length=1)
    ids: list[str] = Field(min_length=1)


class ReferenceCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: int
    dev_standards: list[DevStandardReference]
