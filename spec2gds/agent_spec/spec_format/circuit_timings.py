"""Versioned source-semantic Circuit Designer timing annotations."""

from __future__ import annotations

import json
import math
import typing

import pydantic
from lxml import etree

from spec2gds.agent_spec.spec_format.models import AnnotationSchemaEntry, EntityRef, StrictModel

TIMING_NAMESPACE = "spec2gds.circuit-timing"
TIMING_ROOT = "annotations/circuit-timing"
TIMING_MAX_BYTES = 2 * 1024 * 1024


class DesignClockSignalV1(StrictModel):
    kind: typing.Literal["boundary", "net"]
    id: str


class DesignClockDomainV1(StrictModel):
    id: str
    label: str
    color: str | None = None
    signal: DesignClockSignalV1 | None = None


class DesignCycleEdgeV1(StrictModel):
    id: str
    x: float
    label: str | None = None
    next_stage_label: str | None = None
    locked: bool = False


class DesignCircuitTimingV1(StrictModel):
    """Timing stages keyed by semantic instance and boundary names."""

    schema_version: typing.Literal[1] = 1
    design: EntityRef
    clock_domains: tuple[DesignClockDomainV1, ...] = (DesignClockDomainV1(id="default", label="clk"),)
    cycle_edges: tuple[DesignCycleEdgeV1, ...] = ()
    subject_domain_overrides: dict[str, str] = pydantic.Field(default_factory=dict)
    leading_stage_label: str | None = None

    @pydantic.model_validator(mode="after")
    def validate_payload(self) -> "DesignCircuitTimingV1":
        if self.design.entity_kind != "design":
            raise ValueError("Circuit timing must be owned by a design entity.")
        domain_ids = [item.id for item in self.clock_domains]
        if not self.clock_domains or "default" not in domain_ids or len(domain_ids) != len(set(domain_ids)):
            raise ValueError("Circuit timing needs unique clock domains including default.")
        edge_ids = [item.id for item in self.cycle_edges]
        edge_positions = [item.x for item in self.cycle_edges]
        if len(edge_ids) != len(set(edge_ids)) or len(edge_positions) != len(set(edge_positions)):
            raise ValueError("Circuit timing cycle edges need unique IDs and positions.")
        if not all(math.isfinite(item.x) for item in self.cycle_edges):
            raise ValueError("Circuit timing cycle-edge positions must be finite.")
        if set(self.subject_domain_overrides.values()) - set(domain_ids):
            raise ValueError("Circuit timing subject references an unknown clock domain.")
        for key in self.subject_domain_overrides:
            if not ((key.startswith("instance:") or key.startswith("boundary:")) and key.split(":", 1)[1]):
                raise ValueError(f"Invalid circuit timing subject key: {key}")
        encoded = json.dumps(self.model_dump(mode="json"), separators=(",", ":")).encode()
        if len(encoded) > TIMING_MAX_BYTES:
            raise ValueError("Circuit timing exceeds the 2 MiB limit.")
        return self


def timing_path(design_id: str) -> str:
    return f"{TIMING_ROOT}/{design_id}.json"


def load_design_timing(revision: typing.Any, design: EntityRef) -> DesignCircuitTimingV1 | None:
    path = timing_path(design.entity_id)
    annotation = next((item for item in revision.annotations if item.path == path), None)
    if annotation is None:
        return None
    value = DesignCircuitTimingV1.model_validate_json(annotation.data)
    if value.design != design:
        raise ValueError(f"Circuit timing {path} does not match its owning design.")
    return value


def upsert_design_timing(package: typing.Any, timing: DesignCircuitTimingV1) -> None:
    path = timing_path(timing.design.entity_id)
    data = (json.dumps(timing.model_dump(mode="json", exclude_none=True), indent=2, sort_keys=True) + "\n").encode()
    if len(data) > TIMING_MAX_BYTES:
        raise ValueError("Circuit timing exceeds the 2 MiB limit.")
    package.files[path] = data
    schemas = [item for item in package.manifest.annotation_schemas if item.namespace != TIMING_NAMESPACE]
    schemas.append(AnnotationSchemaEntry(namespace=TIMING_NAMESPACE, version=1, path_prefix=TIMING_ROOT))
    package.manifest = package.manifest.model_copy(update={"annotation_schemas": schemas})


def validate_timing_annotations(manifest: typing.Any, files: typing.Mapping[str, bytes]) -> None:
    """Validate registered timing files against actual design, net and clock references.

    Annotations are semantic package data rather than arbitrary canvas coordinates.
    Registration, canonical path and document identity must agree before saving.
    """
    registered = any(item.namespace == TIMING_NAMESPACE for item in manifest.annotation_schemas)
    paths = sorted(path for path in files if path.startswith(f"{TIMING_ROOT}/"))
    if paths and not registered:
        raise ValueError("Circuit timing files require the spec2gds.circuit-timing registration.")
    if registered and not paths:
        raise ValueError("Circuit timing registration has no timing files.")
    known_designs = {item.entity_id: item for item in manifest.documents if item.kind == "design"}
    component_ports: dict[str, set[str]] = {}
    for entry in (item for item in manifest.documents if item.kind == "component"):
        root = etree.fromstring(files[entry.path])
        component_ports[entry.vlnv] = {
            str(node.text or "").strip()
            for node in root.xpath("./*[local-name()='model']/*[local-name()='ports']/*[local-name()='port']/*[local-name()='name']")
        }
    owner_vlnv_by_design: dict[str, str] = {}
    for mapping in manifest.component_compositions:
        owner = next((item for item in manifest.documents if item.kind == "component" and item.entity_id == mapping.component.entity_id), None)
        if owner is not None:
            owner_vlnv_by_design[mapping.internal_design.entity_id] = owner.vlnv
    for path in paths:
        value = DesignCircuitTimingV1.model_validate_json(files[path])
        if value.design.document_id != manifest.document_id or value.design.entity_id not in known_designs:
            raise ValueError(f"Circuit timing {path} references an unknown design.")
        if path != timing_path(value.design.entity_id):
            raise ValueError(f"Circuit timing {path} is not stored at its canonical path.")
        design_root = etree.fromstring(files[known_designs[value.design.entity_id].path])
        instances = {
            str(node.xpath("string(./*[local-name()='instanceName'])")).strip()
            for node in design_root.xpath("./*[local-name()='componentInstances']/*[local-name()='componentInstance']")
        }
        nets = {
            str(node.xpath("string(./*[local-name()='name'])")).strip()
            for node in design_root.xpath("./*[local-name()='adHocConnections']/*[local-name()='adHocConnection']")
        }
        boundaries = component_ports.get(owner_vlnv_by_design.get(value.design.entity_id, ""), set())
        known_subjects = {
            *(f"instance:{name}" for name in instances),
            *(f"boundary:{name}" for name in boundaries),
        }
        unknown_subjects = set(value.subject_domain_overrides) - known_subjects
        unknown_net_signals = {
            domain.signal.id for domain in value.clock_domains
            if domain.signal is not None and domain.signal.kind == "net" and domain.signal.id not in nets
        }
        unknown_boundary_signals = {
            domain.signal.id for domain in value.clock_domains
            if domain.signal is not None and domain.signal.kind == "boundary" and domain.signal.id not in boundaries
        }
        unknown = unknown_subjects | unknown_net_signals | unknown_boundary_signals
        if unknown:
            raise ValueError(f"Circuit timing {path} contains unknown semantic references: {', '.join(sorted(unknown))}")
