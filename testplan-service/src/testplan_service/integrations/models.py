"""Normalized projection models for decoded spec2gds Activity Snapshots."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class EntitySummary(BaseModel):
    """Summary of a component or design entity in the snapshot."""

    model_config = ConfigDict(extra="forbid")

    entity_ref: dict[str, str]
    name: str
    kind: str
    vlnv: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    ports: list[dict[str, Any]] = Field(default_factory=list)


class OccurrenceSummary(BaseModel):
    """Hierarchical component or design occurrence representing a verification scope."""

    model_config = ConfigDict(extra="forbid")

    occurrence_id: str
    name: str
    kind: str  # "design" or "component"
    component_ref: dict[str, str] | None = None
    component_name: str = ""
    path: str
    instance_chain: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    ports: list[dict[str, Any]] = Field(default_factory=list)


class SourceSectionSummary(BaseModel):
    """Auditable narrative or structured fact section from the snapshot."""

    model_config = ConfigDict(extra="forbid")

    section_id: str
    title: str
    entity_ref: dict[str, str]
    locator: dict[str, Any]
    text: str
    content_digest: str


class SourceSnapshotView(BaseModel):
    """Normalized, validated read-only projection of an Activity Snapshot."""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    source_document_id: str
    source_revision_hash: str
    root_ref: dict[str, str] | None = None
    entities: list[EntitySummary] = Field(default_factory=list)
    occurrences: list[OccurrenceSummary] = Field(default_factory=list)
    source_sections: list[SourceSectionSummary] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)
