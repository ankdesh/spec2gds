"""Strict schemas for Spec Component Library catalogue assets, evidence, and inventory."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal

import pydantic

from spec2gds.spec.spec_format.models import EntityRef, StrictModel

CATALOGUE_SCHEMA_VERSION = 1
EVIDENCE_SCHEMA_VERSION = 1
INVENTORY_SCHEMA_VERSION = 1

ID_REGEX = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
VERSION_REGEX = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")

SUPPORTED_CATEGORIES: tuple[str, ...] = (
    "arithmetic_dsp",
    "buses",
    "cdc_reset",
    "integrity_control",
    "ip_helpers",
    "logic",
    "peripherals",
    "state",
    "storage",
    "streams",
)


def compute_identity_key(vendor: str, library: str, name: str) -> str:
    """Stable lower-case SHA-256 hex of UTF-8 root VLNV without its version field."""
    canonical_vlnv_base = f"{vendor}:{library}:{name}"
    return hashlib.sha256(canonical_vlnv_base.encode("utf-8")).hexdigest().lower()


def compute_sha256(data: bytes) -> str:
    """Compute sha256:<64 lowercase hex> digest for arbitrary bytes."""
    return f"sha256:{hashlib.sha256(data).hexdigest().lower()}"


def serialize_canonical_evidence_bytes(data: dict[str, Any]) -> bytes:
    """Encode evidence as UTF-8 JSON with sorted keys, no whitespace separators, and no trailing newline."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def get_package_asset(pkg: Any, asset_id: str) -> bytes | None:
    """Find and return raw asset bytes by asset_id from a SpecPackage."""
    for asset in getattr(pkg.manifest, "assets", []):
        if asset.asset_id == asset_id:
            return pkg.files.get(asset.path)
    return None


class TimingInfo(StrictModel):
    """Timing characteristics described as explicit strings without expression evaluation."""

    latency: str
    throughput: str
    reset: str


class DependencyInfo(StrictModel):
    """External dependency recorded in a composite or child component."""

    vlnv: str
    package_sha256: str
    parameters: dict[str, str]
    local_ref: EntityRef


class CatalogueAssetV1(StrictModel):
    """Metadata asset stored inside a Component package at library_catalogue_v1."""

    schema_version: Literal[1]
    root: EntityRef
    id: str
    category: str
    version: str
    summary: str
    tags: list[str]
    licence: str
    implementation: Literal["body_sv", "composite"]
    contracts: str
    presets: dict[str, dict[str, str]]
    timing: TimingInfo
    limitations: list[str]
    dependencies: list[DependencyInfo]

    @pydantic.field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not ID_REGEX.match(value):
            raise ValueError(f"Invalid Component ID: {value!r}. Must match {ID_REGEX.pattern}")
        return value

    @pydantic.field_validator("category")
    @classmethod
    def _validate_category(cls, value: str) -> str:
        if value not in SUPPORTED_CATEGORIES:
            raise ValueError(f"Unknown category: {value!r}. Must be one of {SUPPORTED_CATEGORIES}")
        return value

    @pydantic.field_validator("version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        if not VERSION_REGEX.match(value):
            raise ValueError(f"Invalid semantic version: {value!r}. Must match MAJOR.MINOR.PATCH with no leading zeros.")
        return value

    @pydantic.field_validator("tags")
    @classmethod
    def _validate_tags(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("Tags must be a sorted list of unique strings.")
        return value

    @pydantic.field_validator("presets")
    @classmethod
    def _validate_presets(cls, value: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
        if "default" not in value:
            raise ValueError("Presets must contain a 'default' configuration.")
        for name, preset_map in value.items():
            for p_name, p_val in preset_map.items():
                if not isinstance(p_val, str) or not re.fullmatch(r"^-?\d+$", p_val):
                    raise ValueError(f"Preset {name} parameter {p_name} value {p_val!r} must be canonical base-10 integer string.")
        return value


class CheckRecord(StrictModel):
    """One atomic check execution outcome."""

    kind: Literal[
        "package",
        "implementation",
        "determinism",
        "lint",
        "simulation",
        "parameter_validation",
        "stress",
        "structure",
        "formal",
        "synthesis",
        "physical",
    ]
    preset: str | None = None
    status: Literal["pass", "fail", "not_run", "not_applicable"]
    seed: int | None = None
    summary: str
    artifact_sha256: str | None = None


class EvidenceRecordV1(StrictModel):
    """Evidence file for a Component release recorded in evidence.json."""

    schema_version: Literal[1]
    package_sha256: str
    source_revision_hash: str
    root: EntityRef
    runner_commit: str
    tools: dict[str, str]
    presets: dict[str, dict[str, str]]
    checks: list[CheckRecord]
    limitations: list[str]
    created_at: str

    @pydantic.field_validator("package_sha256")
    @classmethod
    def _validate_package_sha256(cls, value: str) -> str:
        if not re.fullmatch(r"^sha256:[a-f0-9]{64}$", value):
            raise ValueError("package_sha256 must be formatted as sha256:<64 lowercase hex>.")
        return value

    @pydantic.field_validator("created_at")
    @classmethod
    def _validate_created_at(cls, value: str) -> str:
        if not value.endswith("Z"):
            raise ValueError("created_at must be an ISO8601 UTC timestamp ending in 'Z'.")
        return value


class ReleaseRecord(StrictModel):
    """One immutable release record inside an inventory entry."""

    version: str
    path: str
    package_sha256: str
    evidence_path: str
    evidence_sha256: str


class InventoryEntry(StrictModel):
    """One Component inventory entry."""

    id: str
    phase: int
    category: str
    version: str
    path: str
    contract: str
    dependencies: list[str]
    status: Literal["planned", "delivered"]
    releases: list[ReleaseRecord]


class InventoryV1(StrictModel):
    """Catalogue inventory containing all planned and delivered Components."""

    schema_version: Literal[1]
    entries: list[InventoryEntry]
