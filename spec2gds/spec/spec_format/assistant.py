"""Revision-guarded assistant context and typed Spec change proposal support.

The LLM-facing contract in this module deliberately contains no XML.  Typed
operations are compiled to the ordinary :mod:`transactions` vocabulary and
therefore pass through the same IP-XACT/profile validation as editor changes.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import typing

import lxml.etree as etree
import pydantic

from spec2gds.spec.activities.reference import register_extensions
from spec2gds.spec.activities.registry import (
    SpecExtensionRegistry,
    render_context,
)
from spec2gds.spec.activities.snapshot import ActivitySnapshot
from spec2gds.spec.spec_format import ipxact
from spec2gds.spec.spec_format.assistant_operation_contract import (
    validate_assistant_operations,
)
from spec2gds.spec.spec_format.document import DocumentSection, build_document_projection
from spec2gds.spec.spec_format.ir import (
    ConnectionIR,
    EndpointSliceIR,
    ExternalPortEndpointIR,
    InstanceIR,
    InterfaceEndpointIR,
    PortEndpointIR,
    SpecRevision,
)
from spec2gds.spec.spec_format.models import EntityRef, NarrativeBlock
from spec2gds.spec.spec_format.naming import reference_name, select_entity
from spec2gds.spec.spec_format.source_edits import (
    set_entity_metadata,
    upsert_component_port,
)
from spec2gds.spec.spec_format.transactions import (
    ClearInternalDesign,
    CreateHardware,
    DeleteConnection,
    DeleteInstance,
    DeleteNarrativeBlock,
    DeleteSection,
    EditOperation,
    InitialComponentPort,
    ReorderConnections,
    ReorderInstances,
    ReorderNarrativeBlocks,
    SetInternalDesign,
    SetNarrativeLinks,
    SpecEditTransaction,
    StructuredPortInput,
    TransactionalPortInput,
    UpsertConnection,
    UpsertDocumentXml,
    UpsertInstance,
    UpsertNarrativeBlock,
    UpsertSection,
    WirePortInput,
    _apply_operation,
)

SUPPORTED_TARGET_KINDS = {
    "component",
    "design",
    "bus_definition",
    "abstraction_definition",
    "narrative_block",
}

SUPPORTED_OPERATION_TYPES = {
    "create_entity",
    "set_entity_metadata",
    "upsert_parameter",
    "delete_parameter",
    "upsert_component_port",
    "delete_component_port",
    "upsert_bus_interface",
    "delete_bus_interface",
    "upsert_channel",
    "delete_channel",
    "upsert_instance",
    "delete_instance",
    "reorder_instances",
    "upsert_connection",
    "delete_connection",
    "reorder_connections",
    "set_internal_design",
    "clear_internal_design",
    "update_bus_definition",
    "set_abstraction_bus_type",
    "upsert_abstraction_port",
    "delete_abstraction_port",
    "upsert_narrative_block",
    "delete_narrative_block",
    "reorder_narrative_blocks",
    "set_narrative_entity_links",
    "upsert_entity_section",
    "delete_entity_section",
}


def normalize_operation_aliases(operation: dict[str, typing.Any]) -> dict[str, typing.Any]:
    """Accept canonical action names and preserve the stable V1 execution vocabulary."""
    normalized = dict(operation)
    kind = normalized.get("type")
    fixed_kind = {"create_component": "component", "create_design": "design"}.get(kind)
    aliases = {"create_component": "create_entity", "create_design": "create_entity",
               "upsert_section": "upsert_entity_section", "delete_section": "delete_entity_section",
               "set_narrative_links": "set_narrative_entity_links"}
    if kind in aliases:
        normalized["type"] = aliases[kind]
    if fixed_kind:
        if "kind" in normalized and normalized["kind"] != fixed_kind:
            raise ValueError("Creation action and hardware kind must match.")
        normalized["kind"] = fixed_kind
    if normalized.get("type") in {"upsert_entity_section", "delete_entity_section"} and "parent" in normalized:
        if "owner" in normalized and normalized["owner"] != normalized["parent"]:
            raise ValueError("Section parent aliases must identify the same Component or Design.")
        normalized["owner"] = normalized.pop("parent")
    return normalized


class SpecChangeProposal(pydantic.BaseModel):
    """Strict envelope accepted by preview and apply endpoints."""

    model_config = pydantic.ConfigDict(extra="forbid")

    schema_version: typing.Literal["1.0"] = "1.0"
    kind: typing.Literal["spec_change_proposal"] = "spec_change_proposal"
    proposal_id: str = pydantic.Field(min_length=1)
    document_id: str
    scope: typing.Literal["document", "entity"] = "entity"
    target: EntityRef | None = None
    base_source_revision_hash: str
    title: str
    summary: str
    rationale: str
    assumptions: list[str] = pydantic.Field(default_factory=list)
    operations: list[dict[str, typing.Any]] = pydantic.Field(min_length=1)

    @pydantic.field_validator("operations", mode="before")
    @classmethod
    def _operation_aliases(cls, values: typing.Any) -> typing.Any:
        if not isinstance(values, list):
            return values
        return [normalize_operation_aliases(value) if isinstance(value, dict) else value for value in values]

    @pydantic.model_validator(mode="after")
    def validate_identity(self) -> "SpecChangeProposal":
        """Require entity targets only for entity-scoped proposal envelopes."""
        if self.scope == "document":
            if self.target is not None:
                raise ValueError("Document-scoped proposals cannot carry an entity target.")
        else:
            if self.target is None:
                raise ValueError("Entity-scoped proposals require a target.")
            if self.target.document_id != self.document_id:
                raise ValueError("Proposal target must belong to proposal document_id.")
            if self.target.entity_kind not in SUPPORTED_TARGET_KINDS:
                raise ValueError(f"Unsupported assistant target: {self.target.entity_kind}")
        return self

    def operations_digest(self) -> str:
        """Hash canonical operations for review and persistence provenance."""
        encoded = json.dumps(
            self.operations,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(encoded).hexdigest()


def build_assistant_context(revision: SpecRevision, target: EntityRef) -> dict[str, typing.Any]:
    """Return complete writable target context plus labeled read-only surroundings."""
    if target.entity_kind not in SUPPORTED_TARGET_KINDS:
        raise ValueError(f"Unsupported assistant target: {target.entity_kind}")
    entity = revision.resolve(target)
    projection = build_document_projection(revision)
    writable_refs = _writable_refs(revision, target)
    writable_keys = {_ref_key(item) for item in writable_refs}
    sections = [
        section.model_dump(mode="json")
        for section in projection.sections
        if section.entity_ref is not None and _ref_key(section.entity_ref) in writable_keys
    ]
    if target.entity_kind == "narrative_block":
        sections = [
            DocumentSection(
                section_id=f"narrative-block-{target.entity_id}",
                title=reference_name(revision, target),
                level=2,
                eyebrow="Narrative",
                entity_ref=target,
                narrative=[_jsonable(entity)],
            ).model_dump(mode="json")
        ]

    closure: tuple[EntityRef, ...] = ()
    owned_internal_design: typing.Any = None
    if target.entity_kind in {"component", "design"}:
        closure = revision.dependency_closure(target)
    if target.entity_kind == "component":
        owned_internal_design = revision.internal_design(target)
    linked = revision.narrative_blocks_for(target) if target.entity_kind != "narrative_block" else (entity,)
    read_only_refs = [item for item in closure if _ref_key(item) not in writable_keys]
    usages = _entity_usages(revision, target)
    return {
        "schema_version": "spec2gds.assistant-context.v1",
        "scope": "entity",
        "document_id": revision.document_id,
        "source_revision_hash": revision.source_revision_hash,
        "target": target.model_dump(mode="json"),
        "writable": {
            "entity": _jsonable(entity),
            "owned_internal_design": _jsonable(owned_internal_design),
            "entity_refs": [item.model_dump(mode="json") for item in writable_refs],
            "sections": sections,
            "linked_narrative": [_jsonable(item) for item in linked if _narrative_is_writable(item, target)],
        },
        "read_only": {
            "dependency_refs": [item.model_dump(mode="json") for item in read_only_refs],
            "usages": usages,
            "shared_narrative": [_jsonable(item) for item in linked if not _narrative_is_writable(item, target)],
        },
        "available_references": {
            "components": [_jsonable(item) for item in revision.components],
            "designs": [_identity(item) for item in revision.designs],
            "bus_definitions": [_identity(item) for item in revision.bus_definitions],
            "abstraction_definitions": [_identity(item) for item in revision.abstraction_definitions],
        },
        "diagnostics": list(revision.diagnostics),
    }


def build_document_assistant_context(revision: SpecRevision) -> dict[str, typing.Any]:
    """Return document-wide writable context for iterative refinement."""
    snapshot = ActivitySnapshot.create(revision)
    registry = SpecExtensionRegistry()
    register_extensions(registry)
    rendered = render_context(registry, "reference.spec_text_context", snapshot)
    return {
        "schema_version": "spec2gds.assistant-context.v1",
        "scope": "document",
        "document_id": revision.document_id,
        "source_revision_hash": revision.source_revision_hash,
        "target": None,
        "rendered_context": rendered.model_dump(mode="json"),
        "writable": {
            "document_operations": sorted(SUPPORTED_OPERATION_TYPES),
            "entity": None,
            "owned_internal_design": None,
            "entity_refs": [item.ref.model_dump(mode="json") for item in (
                *revision.components, *revision.designs, *revision.bus_definitions,
                *revision.abstraction_definitions,
            )],
            "sections": [section.model_dump(mode="json") for section in build_document_projection(revision).sections],
            "linked_narrative": [_jsonable(item) for item in revision.narrative.blocks],
        },
        "read_only": {"existing_entities": False, "assets": True,
                      "composite_boundary_ports": True},
        "available_references": {
            "components": [_jsonable(item) for item in revision.components],
            "designs": [_jsonable(item) for item in revision.designs],
            "bus_definitions": [_jsonable(item) for item in revision.bus_definitions],
            "abstraction_definitions": [
                _jsonable(item) for item in revision.abstraction_definitions
            ],
        },
        "diagnostics": list(revision.diagnostics),
    }


def preview_assistant_proposal(
    revision: SpecRevision,
    proposal: SpecChangeProposal,
) -> dict[str, typing.Any]:
    """Validate and preview a proposal without mutating the active session."""
    if proposal.document_id != revision.document_id:
        raise ValueError("Proposal targets a different document.")
    if proposal.base_source_revision_hash != revision.source_revision_hash:
        return {
            "status": "stale",
            "error_code": "STALE_REVISION",
            "diagnostics": ["Proposal base source revision is stale. Read fresh context and regenerate the operations."],
            "section_validation": [],
            "base_source_revision_hash": proposal.base_source_revision_hash,
            "current_source_revision_hash": revision.source_revision_hash,
            "candidate_source_revision_hash": None,
            "current_sections": _proposal_sections(revision, proposal.target),
            "candidate_sections": [],
            "diff": [],
        }
    try:
        operations = compile_assistant_operations(revision, proposal.target, proposal.operations)
        validate_assistant_operations(
            proposal.scope, proposal.operations,
            proposal.target.entity_kind if proposal.target else None,
            bool(proposal.target and proposal.target.entity_kind == "component"
                 and revision.internal_design(proposal.target)),
        )
    except (KeyError, TypeError, ValueError, pydantic.ValidationError) as exc:
        return _invalid_preview(revision, proposal.target, str(exc))
    result = SpecEditTransaction(revision.source_revision_hash, operations).apply(revision)
    if not result.succeeded or result.revision is None:
        preview = _invalid_preview(revision, proposal.target, *result.diagnostics)
        preview["section_validation"] = [item.as_json() for item in result.section_validation]
        return preview
    current = _proposal_sections(revision, proposal.target)
    candidate = _proposal_sections(result.revision, proposal.target)
    return {
        "status": "valid",
        "diagnostics": [],
        "section_validation": [item.as_json() for item in result.section_validation],
        "base_source_revision_hash": revision.source_revision_hash,
        "candidate_source_revision_hash": result.revision.source_revision_hash,
        "current_sections": current,
        "candidate_sections": candidate,
        "diff": _named_diff(current, candidate),
        "_revision": result.revision,
    }


def compile_assistant_operations(
    revision: SpecRevision,
    target: EntityRef | None,
    raw_operations: list[dict[str, typing.Any]],
) -> tuple[EditOperation, ...]:
    """Resolve proposed definitions privately before compiling dependent edits.

    Creating a definition does not publish an intermediate revision. The caller
    still applies this entire batch through the ordinary atomic transaction.
    """
    creates = [raw for raw in raw_operations if isinstance(raw, dict) and raw.get("type") == "create_entity"]
    if not creates:
        return _compile_assistant_operations(revision, target, raw_operations)
    creates.sort(key=lambda raw: raw.get("kind") == "design")
    package = revision.to_package()
    creation_operations: list[EditOperation] = []
    for raw in creates:
        operations = _compile_assistant_operations(SpecRevision.from_package(package), target, [raw])
        for operation in operations:
            _apply_operation(package, operation)
            creation_operations.append(operation)
    staged = SpecRevision.from_package(package)
    remaining = [raw for raw in raw_operations if not isinstance(raw, dict) or raw.get("type") != "create_entity"]
    return (*creation_operations, *_compile_assistant_operations(staged, target, remaining))


def _compile_assistant_operations(
    revision: SpecRevision,
    target: EntityRef | None,
    raw_operations: list[dict[str, typing.Any]],
) -> tuple[EditOperation, ...]:
    """Validate ownership and compile typed JSON operations to transaction objects."""
    if target is not None:
        revision.resolve(target)
    roots: dict[str, tuple[str, etree._Element]] = {}
    deferred: list[EditOperation] = []
    planned_component_vlnvs = {
        f"spec2gds.local:work:{str(raw.get('name', '')).strip()}:1.0"
        for raw in raw_operations
        if isinstance(raw, dict)
        and raw.get("type") == "create_entity"
        and raw.get("kind") == "component"
    }
    available_component_vlnvs = {
        item.vlnv for item in revision.components
    } | planned_component_vlnvs

    def root_for(reference: EntityRef) -> etree._Element:
        _assert_document_ref(revision, reference)
        if reference.entity_kind == "narrative_block":
            raise ValueError("Narrative blocks are not IP-XACT documents.")
        if reference.entity_id not in roots:
            package = revision.to_package()
            entry = next(
                (
                    item
                    for item in package.manifest.documents
                    if item.entity_id == reference.entity_id and item.kind == reference.entity_kind
                ),
                None,
            )
            if entry is None:
                raise KeyError(f"Unknown {reference.entity_kind}: {reference.entity_id}")
            roots[reference.entity_id] = (entry.kind, ipxact.parse_xml(package.files[entry.path]))
        return roots[reference.entity_id][1]

    for index, raw in enumerate(raw_operations):
        if not isinstance(raw, dict):
            raise ValueError(f"Operation {index} must be an object.")
        operation_type = str(raw.get("type", ""))
        if operation_type not in SUPPORTED_OPERATION_TYPES:
            raise ValueError(f"Unsupported assistant operation: {operation_type}")
        _reject_unknown_keys(raw, _allowed_keys(operation_type), operation_type)
        _assert_operation_owned(revision, target, raw)

        if operation_type == "create_entity":
            entity_kind = str(raw.get("kind", ""))
            if entity_kind not in {"component", "design"}:
                raise ValueError("create_entity kind must be component or design.")
            if "entry_design" in raw and (entity_kind != "design" or not isinstance(raw["entry_design"], bool)):
                raise ValueError("entry_design is a boolean supported only for designs.")
            instances_value = raw.get("instances", [])
            if not isinstance(instances_value, list):
                raise ValueError("instances must be an array.")
            instances = tuple(
                InstanceIR(**{**item, "component_vlnv": select_entity(revision, item["component_vlnv"], ("component",)).vlnv})
                for item in instances_value
            )
            ports_value = raw.get("ports", [])
            if not isinstance(ports_value, list):
                raise ValueError("create_entity ports must be an array.")
            if any(
                item.component_vlnv not in available_component_vlnvs
                for item in instances
            ):
                raise ValueError(
                    "Design instances must use an existing or proposed component VLNV."
                )
            deferred.append(
                CreateHardware(
                    typing.cast(typing.Any, entity_kind),
                    str(raw.get("name", "")),
                    str(raw.get("entity_id", "")),
                    instances,
                    tuple(_initial_component_port(item) for item in ports_value),
                    _optional_string(raw.get("systemverilog")),
                    raw.get("entry_design", True),
                )
            )
        elif operation_type == "set_entity_metadata":
            reference = _ref(raw["entity"])
            _set_metadata(root_for(reference), raw)
        elif operation_type == "upsert_parameter":
            reference = _ref(raw["entity"])
            _upsert_parameter(root_for(reference), _mapping(raw, "parameter"))
        elif operation_type == "delete_parameter":
            reference = _ref(raw["entity"])
            _delete_named(root_for(reference), "parameters", "parameter", "name", str(raw["name"]))
        elif operation_type == "upsert_component_port":
            reference = _ref(raw["component"])
            _assert_component_port_editable(revision, reference)
            _upsert_component_port(root_for(reference), _mapping(raw, "port"))
        elif operation_type == "delete_component_port":
            reference = _ref(raw["component"])
            _assert_component_port_editable(revision, reference)
            _delete_component_port(root_for(reference), str(raw["name"]))
        elif operation_type == "upsert_bus_interface":
            reference = _ref(raw["component"])
            _upsert_bus_interface(revision, root_for(reference), _mapping(raw, "interface"))
        elif operation_type == "delete_bus_interface":
            reference = _ref(raw["component"])
            _delete_named(root_for(reference), "busInterfaces", "busInterface", "name", str(raw["name"]))
        elif operation_type == "upsert_channel":
            reference = _ref(raw["component"])
            _upsert_channel(root_for(reference), _mapping(raw, "channel"))
        elif operation_type == "delete_channel":
            reference = _ref(raw["component"])
            _delete_named(root_for(reference), "channels", "channel", "name", str(raw["name"]))
        elif operation_type == "update_bus_definition":
            reference = _ref(raw["bus_definition"])
            _update_bus_definition(revision, root_for(reference), _mapping(raw, "properties"))
        elif operation_type == "set_abstraction_bus_type":
            reference = _ref(raw["abstraction_definition"])
            _set_abstraction_bus_type(revision, root_for(reference), str(raw["bus_vlnv"]))
        elif operation_type == "upsert_abstraction_port":
            reference = _ref(raw["abstraction_definition"])
            _upsert_abstraction_port(root_for(reference), _mapping(raw, "port"))
        elif operation_type == "delete_abstraction_port":
            reference = _ref(raw["abstraction_definition"])
            _delete_named(root_for(reference), "ports", "port", "logicalName", str(raw["name"]), prune=False)
        elif operation_type == "upsert_instance":
            deferred.append(UpsertInstance(_ref(raw["design"]), InstanceIR(**_mapping(raw, "instance"))))
        elif operation_type == "delete_instance":
            deferred.append(DeleteInstance(_ref(raw["design"]), str(raw["instance_name"])))
        elif operation_type == "reorder_instances":
            deferred.append(ReorderInstances(_ref(raw["design"]), tuple(_strings(raw, "instance_names"))))
        elif operation_type == "upsert_connection":
            value = _mapping(raw, "connection")
            deferred.append(UpsertConnection(_ref(raw["design"]), _connection(value)))
        elif operation_type == "delete_connection":
            deferred.append(DeleteConnection(_ref(raw["design"]), str(raw["connection_name"])))
        elif operation_type == "reorder_connections":
            kind = str(raw["kind"])
            if kind not in {"interface", "ad_hoc"}:
                raise ValueError("Connection reorder kind must be interface or ad_hoc.")
            deferred.append(ReorderConnections(_ref(raw["design"]), typing.cast(typing.Any, kind), tuple(_strings(raw, "connection_names"))))
        elif operation_type == "set_internal_design":
            deferred.append(SetInternalDesign(_ref(raw["component"]), _ref(raw["internal_design"])))
        elif operation_type == "clear_internal_design":
            deferred.append(ClearInternalDesign(_ref(raw["component"])))
        elif operation_type == "upsert_narrative_block":
            deferred.append(UpsertNarrativeBlock(NarrativeBlock.model_validate(raw["block"]), raw.get("parent_block_id"), raw.get("index")))
        elif operation_type == "delete_narrative_block":
            deferred.append(DeleteNarrativeBlock(str(raw["block_id"])))
        elif operation_type == "reorder_narrative_blocks":
            deferred.append(ReorderNarrativeBlocks(tuple(_strings(raw, "block_ids")), typing.cast(str | None, raw.get("parent_block_id"))))
        elif operation_type == "set_narrative_entity_links":
            deferred.append(SetNarrativeLinks(str(raw["block_id"]), tuple(_ref(item) for item in _list(raw, "entity_refs"))))
        elif operation_type == "upsert_entity_section":
            payload = _mapping(raw, "payload")
            deferred.append(UpsertSection(
                parent=_ref(raw.get("parent", raw.get("owner"))),
                section_type=str(raw["section_type"]),
                payload=payload,
                section_id=str(raw["section_id"]) if raw.get("section_id") else None,
                type_version=int(raw.get("type_version", 1)),
            ))
        elif operation_type == "delete_entity_section":
            deferred.append(DeleteSection(
                parent=_ref(raw.get("parent", raw.get("owner"))),
                section_type=str(raw["section_type"]),
                section_id=str(raw["section_id"]) if raw.get("section_id") else None,
            ))

    xml_operations: list[EditOperation] = []
    for entity_id in sorted(roots):
        kind, root = roots[entity_id]
        xml_operations.append(
            UpsertDocumentXml(
                typing.cast(typing.Any, kind),
                etree.tostring(root, encoding="UTF-8", xml_declaration=True, pretty_print=True),
            )
        )
    return tuple([*xml_operations, *deferred])


def _allowed_keys(kind: str) -> set[str]:
    common = {"type", "operation_id"}
    shapes = {
        "create_entity": {"kind", "name", "entity_id", "instances", "ports", "systemverilog", "entry_design"},
        "set_entity_metadata": {"entity", "display_name", "short_description", "description"},
        "upsert_parameter": {"entity", "parameter"},
        "delete_parameter": {"entity", "name"},
        "upsert_component_port": {"component", "port"},
        "delete_component_port": {"component", "name"},
        "upsert_bus_interface": {"component", "interface"},
        "delete_bus_interface": {"component", "name"},
        "upsert_channel": {"component", "channel"},
        "delete_channel": {"component", "name"},
        "upsert_instance": {"design", "instance"},
        "delete_instance": {"design", "instance_name"},
        "reorder_instances": {"design", "instance_names"},
        "upsert_connection": {"design", "connection"},
        "delete_connection": {"design", "connection_name"},
        "reorder_connections": {"design", "kind", "connection_names"},
        "set_internal_design": {"component", "internal_design"},
        "clear_internal_design": {"component"},
        "update_bus_definition": {"bus_definition", "properties"},
        "set_abstraction_bus_type": {"abstraction_definition", "bus_vlnv"},
        "upsert_abstraction_port": {"abstraction_definition", "port"},
        "delete_abstraction_port": {"abstraction_definition", "name"},
        "upsert_narrative_block": {"block", "parent_block_id", "index"},
        "delete_narrative_block": {"block_id"},
        "reorder_narrative_blocks": {"block_ids", "parent_block_id"},
        "set_narrative_entity_links": {"block_id", "entity_refs"},
        "upsert_entity_section": {"owner", "section_type", "section_id", "type_version", "payload"},
        "delete_entity_section": {"owner", "section_type", "section_id"},
    }
    return common | shapes[kind]


def _assert_operation_owned(
    revision: SpecRevision,
    target: EntityRef | None,
    operation: dict[str, typing.Any],
) -> None:
    """Reject references outside the binding before constructing a candidate package.

    Document bindings permit top-level creation; entity bindings stay within their
    owned entity/composition. Nested narrative references need the same check.
    """
    kind = str(operation["type"])
    if kind == "create_entity" and target is not None:
        raise ValueError("Top-level creation requires a document binding.")
    direct_keys = {
        "set_entity_metadata": "entity",
        "upsert_parameter": "entity",
        "delete_parameter": "entity",
        "upsert_component_port": "component",
        "delete_component_port": "component",
        "upsert_bus_interface": "component",
        "delete_bus_interface": "component",
        "upsert_channel": "component",
        "delete_channel": "component",
        "upsert_instance": "design",
        "delete_instance": "design",
        "reorder_instances": "design",
        "upsert_connection": "design",
        "delete_connection": "design",
        "reorder_connections": "design",
        "set_internal_design": "component",
        "clear_internal_design": "component",
        "update_bus_definition": "bus_definition",
        "set_abstraction_bus_type": "abstraction_definition",
        "upsert_abstraction_port": "abstraction_definition",
        "delete_abstraction_port": "abstraction_definition",
        "upsert_entity_section": "owner",
        "delete_entity_section": "owner",
    }
    if kind in direct_keys:
        reference = _ref(operation[direct_keys[kind]])
        _assert_document_ref(revision, reference)
        allowed = {_ref_key(item) for item in _writable_refs(revision, target)} if target else None
        if allowed is not None and _ref_key(reference) not in allowed:
            raise ValueError(f"Operation {kind} crosses the selected entity ownership boundary.")
    if kind == "set_internal_design":
        internal = _ref(operation["internal_design"])
        if internal.entity_kind != "design":
            raise ValueError("Internal design must reference a design.")
        owners = {
            item.internal_design.entity_id: item.component.entity_id
            for item in revision.manifest.component_compositions
        }
        owner = owners.get(internal.entity_id)
        component = _ref(operation["component"])
        _assert_document_ref(revision, internal)
        if owner not in {None, component.entity_id} or internal in revision.manifest.entry_designs:
            raise ValueError("A shared or entry design cannot become component-owned content.")
    if kind in {"upsert_narrative_block", "delete_narrative_block", "reorder_narrative_blocks", "set_narrative_entity_links"}:
        if target is not None:
            _assert_narrative_operation_owned(revision, target, operation)
        else:
            # Document scope can edit shared narrative, but never foreign refs.
            def check_refs(value: typing.Any) -> None:
                if isinstance(value, dict):
                    if {"document_id", "entity_id", "entity_kind"} <= value.keys():
                        _assert_document_ref(revision, _ref(value))
                    else:
                        for child in value.values():
                            check_refs(child)
                elif isinstance(value, list):
                    for child in value:
                        check_refs(child)
            check_refs(operation)


def _assert_component_port_editable(
    revision: SpecRevision,
    component: EntityRef,
) -> None:
    """Apply the same component-boundary rule used by direct editor transactions."""
    if component.entity_kind != "component":
        raise ValueError("Component port operations require a component reference.")
    if any(
        item.component.entity_id == component.entity_id
        for item in revision.manifest.component_compositions
    ):
        raise ValueError(
            "Assistant proposals cannot edit ports on components with internal designs; "
            "use the source-bound Circuit Designer boundary workflow."
        )


def _assert_narrative_operation_owned(revision: SpecRevision, target: EntityRef, operation: dict[str, typing.Any]) -> None:
    allowed = _writable_narrative_ids(revision, target)
    kind = str(operation["type"])
    block_id = str(operation.get("block_id", ""))
    if kind == "upsert_narrative_block":
        block = NarrativeBlock.model_validate(operation["block"])
        existing = _all_narrative_ids(revision)
        if block.block_id in existing and block.block_id not in allowed:
            raise ValueError("Shared narrative is read-only from this chat.")
        parent = operation.get("parent_block_id")
        if parent is not None and str(parent) not in allowed:
            raise ValueError("Narrative insertion parent is outside the selected boundary.")
        if target.entity_kind != "narrative_block" and any(ref != target for ref in block.entity_refs):
            raise ValueError("Entity chats may create narrative linked only to their selected entity.")
        return
    if kind == "reorder_narrative_blocks":
        parent = operation.get("parent_block_id")
        if parent is not None and str(parent) not in allowed:
            raise ValueError("Narrative reorder parent is outside the selected boundary.")
        if any(str(item) not in allowed for item in _list(operation, "block_ids")):
            raise ValueError("Narrative reorder crosses the selected boundary.")
        return
    if block_id not in allowed:
        raise ValueError("Shared narrative is read-only from this chat.")
    if kind == "set_narrative_entity_links" and target.entity_kind != "narrative_block":
        refs = [_ref(item) for item in _list(operation, "entity_refs")]
        if refs != [target]:
            raise ValueError("Entity chats may keep narrative linked only to their selected entity.")


def _writable_refs(revision: SpecRevision, target: EntityRef) -> tuple[EntityRef, ...]:
    refs = [target]
    if target.entity_kind == "component":
        internal = revision.internal_design(target)
        if internal is not None:
            refs.append(internal.ref)
    return tuple(refs)


def _writable_narrative_ids(revision: SpecRevision, target: EntityRef) -> set[str]:
    if target.entity_kind == "narrative_block":
        block = typing.cast(NarrativeBlock, revision.resolve(target))
        return _subtree_ids(block)
    return {
        block.block_id
        for block in revision.narrative_blocks_for(target)
        if _narrative_is_writable(block, target)
    }


def _narrative_is_writable(block: NarrativeBlock, target: EntityRef) -> bool:
    refs = [*block.entity_refs, *(inline.entity_ref for inline in block.inlines if inline.entity_ref)]
    return bool(refs) and all(reference == target for reference in refs)


def _subtree_ids(block: NarrativeBlock) -> set[str]:
    result = {block.block_id}
    for child in block.children:
        result.update(_subtree_ids(child))
    return result


def _all_narrative_ids(revision: SpecRevision) -> set[str]:
    result: set[str] = set()
    for block in revision.narrative.blocks:
        result.update(_subtree_ids(block))
    return result


def _proposal_sections(
    revision: SpecRevision,
    target: EntityRef | None,
) -> list[dict[str, typing.Any]]:
    projection = build_document_projection(revision)
    if target is None:
        return [section.model_dump(mode="json") for section in projection.sections]
    keys = {_ref_key(item) for item in _writable_refs(revision, target)}
    result = [
        section.model_dump(mode="json")
        for section in projection.sections
        if section.entity_ref is not None and _ref_key(section.entity_ref) in keys
    ]
    if target.entity_kind == "narrative_block":
        block = typing.cast(NarrativeBlock, revision.resolve(target))
        result.append(DocumentSection(
            section_id=f"narrative-block-{target.entity_id}",
            title=reference_name(revision, target),
            level=2,
            eyebrow="Narrative",
            entity_ref=target,
            narrative=[block.model_dump(mode="json")],
        ).model_dump(mode="json"))
    return result


def _invalid_preview(
    revision: SpecRevision,
    target: EntityRef | None,
    *diagnostics: str,
) -> dict[str, typing.Any]:
    return {
        "status": "invalid",
        "diagnostics": list(diagnostics),
        "section_validation": [],
        "base_source_revision_hash": revision.source_revision_hash,
        "candidate_source_revision_hash": None,
        "current_sections": _proposal_sections(revision, target),
        "candidate_sections": [],
        "diff": [],
    }


def _named_diff(before: typing.Any, after: typing.Any) -> list[dict[str, typing.Any]]:
    """Add readable target descriptions; retain exact diff paths for tools."""
    labels: dict[str, str] = {}
    def visit(value: typing.Any, path: str, context: tuple[str, ...]) -> None:
        if isinstance(value, dict):
            label = value.get("title") or value.get("label")
            if not label and isinstance(value.get("cells"), dict):
                cell = value["cells"].get("name", {})
                label = (cell.get("display_text") or cell.get("value")) if isinstance(cell, dict) else None
            if isinstance(label, str) and label and (not context or label != context[-1]):
                context = (*context, label)
            labels[path] = " › ".join(context) or "Document"
            for key, item in value.items():
                visit(item, f"{path}.{key}", context)
        elif isinstance(value, list):
            keyed = _keyed_list(value)
            if keyed is not None:
                for key, item in keyed.items():
                    visit(item, f"{path}[{key}]", context)
    visit(before, "$", ())
    visit(after, "$", ())
    result = _json_diff(before, after)
    for item in result:
        path = item["path"]
        nearest = max((key for key in labels if path.startswith(key + ".") or path == key), key=len, default="$")
        field = re.sub(r"[^A-Za-z ]", " ", path.rsplit(".", 1)[-1].replace("_", " ")).strip()
        item["label"] = labels.get(nearest, "Document") + (f" › {field.capitalize()}" if field else "")
    return result


def _json_diff(before: typing.Any, after: typing.Any, path: str = "$") -> list[dict[str, typing.Any]]:
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        result: list[dict[str, typing.Any]] = []
        for key in sorted(set(before) | set(after)):
            result.extend(_json_diff(before.get(key), after.get(key), f"{path}.{key}"))
        return result
    if isinstance(before, list) and isinstance(after, list):
        keyed_before = _keyed_list(before)
        keyed_after = _keyed_list(after)
        if keyed_before is not None and keyed_after is not None:
            result = []
            for key in sorted(set(keyed_before) | set(keyed_after)):
                result.extend(_json_diff(keyed_before.get(key), keyed_after.get(key), f"{path}[{key}]"))
            return result
    change = "added" if before is None else "removed" if after is None else "changed"
    return [{"path": path, "change": change, "before": before, "after": after}]


def _keyed_list(values: list[typing.Any]) -> dict[str, typing.Any] | None:
    result: dict[str, typing.Any] = {}
    for index, value in enumerate(values):
        if not isinstance(value, dict):
            return None
        key = next(
            (
                value.get(name)
                for name in ("section_id", "table_id", "row_id", "block_id", "label")
                if value.get(name)
            ),
            None,
        )
        if key is None:
            return None
        result[str(key)] = value
    return result


def _entity_usages(revision: SpecRevision, target: EntityRef) -> list[dict[str, str]]:
    usages: list[dict[str, str]] = []
    entity = revision.resolve(target)
    vlnv = getattr(entity, "vlnv", "")
    if target.entity_kind == "component":
        for design in revision.designs:
            for instance in design.instances:
                if instance.component_vlnv == vlnv:
                    usages.append({"kind": "design_instance", "owner_id": design.ref.entity_id, "name": instance.name})
    elif target.entity_kind in {"bus_definition", "abstraction_definition"}:
        for component in revision.components:
            for interface in component.interfaces:
                used = interface.bus_vlnv if target.entity_kind == "bus_definition" else interface.abstraction_vlnv
                if used == vlnv:
                    usages.append({"kind": "component_interface", "owner_id": component.ref.entity_id, "name": interface.name})
    return usages


def _identity(entity: typing.Any) -> dict[str, typing.Any]:
    from spec2gds.spec.spec_format.naming import entity_name
    return {"ref": entity.ref.model_dump(mode="json"), "vlnv": entity.vlnv, "name": entity_name(entity)}


def _ref_key(reference: EntityRef) -> tuple[str, str]:
    return reference.entity_kind, reference.entity_id


def _assert_document_ref(revision: SpecRevision, reference: EntityRef) -> None:
    if reference.document_id != revision.document_id:
        raise ValueError("Assistant operations cannot cross documents.")
    revision.resolve(reference)


def _ref(value: typing.Any) -> EntityRef:
    return EntityRef.model_validate(value)


def _optional_string(value: typing.Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("systemverilog must be a string or null.")
    return value


def _initial_component_port(value: typing.Any) -> InitialComponentPort:
    """Decode the public component-port union for atomic component creation."""
    if not isinstance(value, dict):
        raise ValueError("Every initial component port must be an object.")
    name = str(value.get("name", ""))
    family = str(value.get("family", ""))
    common = {"name", "family", "description"}
    description = value.get("description")
    if description is not None and not isinstance(description, str):
        raise ValueError("Initial component port description must be a string or null.")
    if family == "wire":
        _reject_unknown_keys(value, common | {"direction", "range"}, "initial wire port")
        direction = str(value.get("direction", ""))
        if direction not in {"in", "out", "inout"}:
            raise ValueError("Initial wire port direction must be in, out, or inout.")
        port_range = value.get("range")
        if port_range is not None and not isinstance(port_range, str):
            raise ValueError("Initial wire port range must be a string or null.")
        port = WirePortInput(typing.cast(typing.Any, direction), port_range, description)
    elif family == "transactional":
        _reject_unknown_keys(
            value,
            common | {"initiative", "kind", "custom_kind", "bus_width"},
            "initial transactional port",
        )
        initiative = str(value.get("initiative", ""))
        if initiative not in {"requires", "provides", "both"}:
            raise ValueError("Initial transactional port initiative must be requires, provides, or both.")
        port = TransactionalPortInput(
            typing.cast(typing.Any, initiative),
            typing.cast(typing.Any, value.get("kind")),
            typing.cast(str | None, value.get("custom_kind")),
            typing.cast(str | None, value.get("bus_width")),
            description,
        )
    elif family == "structured":
        _reject_unknown_keys(value, common | {"direction"}, "initial structured port")
        direction = str(value.get("direction", ""))
        if direction not in {"in", "out", "inout"}:
            raise ValueError("Initial structured port direction must be in, out, or inout.")
        port = StructuredPortInput(typing.cast(typing.Any, direction), description)
    else:
        raise ValueError("Initial component port family must be wire, transactional, or structured.")
    return InitialComponentPort(name=name, port=port)


def _mapping(value: dict[str, typing.Any], key: str) -> dict[str, typing.Any]:
    result = value.get(key)
    if not isinstance(result, dict):
        raise ValueError(f"{key} must be an object.")
    return result


def _list(value: dict[str, typing.Any], key: str) -> list[typing.Any]:
    result = value.get(key)
    if not isinstance(result, list):
        raise ValueError(f"{key} must be an array.")
    return result


def _strings(value: dict[str, typing.Any], key: str) -> list[str]:
    result = _list(value, key)
    if any(not isinstance(item, str) for item in result):
        raise ValueError(f"{key} must contain only strings.")
    return typing.cast(list[str], result)


def _reject_unknown_keys(value: dict[str, typing.Any], allowed: set[str], label: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"{label} contains unsupported fields: {', '.join(sorted(unknown))}")


def _connection(value: dict[str, typing.Any]) -> ConnectionIR:
    kind = str(value.get("kind", ""))
    interface_endpoints = value.get("interface_endpoints", [])
    port_endpoints = value.get("port_endpoints", [])
    external_ports = value.get("external_ports", [])
    hierarchy_interfaces = value.get("hierarchy_interfaces", [])
    if kind == "interface":
        if port_endpoints or external_ports:
            raise ValueError("An interface connection cannot contain port endpoints.")
        if len(interface_endpoints) < 2:
            raise ValueError(
                "An interface connection requires at least two interface endpoints."
            )
    elif kind == "ad_hoc":
        if interface_endpoints or hierarchy_interfaces:
            raise ValueError("An ad-hoc connection cannot contain interface endpoints.")
        if len(port_endpoints) + len(external_ports) < 2:
            raise ValueError(
                "An ad-hoc connection requires at least two port endpoints."
            )
    else:
        raise ValueError("Connection kind must be interface or ad_hoc.")
    return ConnectionIR(
        name=str(value["name"]),
        kind=typing.cast(typing.Any, kind),
        interface_endpoints=tuple(
            InterfaceEndpointIR(**item) for item in interface_endpoints
        ),
        port_endpoints=tuple(_port_endpoint(item) for item in port_endpoints),
        external_ports=tuple(_external_endpoint(item) for item in external_ports),
        hierarchy_interfaces=tuple(str(item) for item in hierarchy_interfaces),
    )


def _endpoint_slice(value: typing.Any) -> EndpointSliceIR | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"lsb", "width"}:
        raise ValueError("Endpoint slice requires lsb and width.")
    if any(type(value[key]) is not int for key in ("lsb", "width")) or value["lsb"] < 0 or value["width"] < 1:
        raise ValueError("Endpoint slices require nonnegative lsb and positive width integers.")
    return EndpointSliceIR(**value)


def _port_endpoint(value: dict[str, typing.Any]) -> PortEndpointIR:
    _reject_unknown_keys(value, {"instance_name", "port_name", "slice"}, "port endpoint")
    return PortEndpointIR(value["instance_name"], value["port_name"], _endpoint_slice(value.get("slice")))


def _external_endpoint(value: typing.Any) -> ExternalPortEndpointIR:
    if isinstance(value, str):
        return ExternalPortEndpointIR(value)
    if not isinstance(value, dict):
        raise ValueError("Boundary endpoint requires a port name or endpoint object.")
    _reject_unknown_keys(value, {"port_name", "slice"}, "boundary endpoint")
    return ExternalPortEndpointIR(value["port_name"], _endpoint_slice(value.get("slice")))


def _q(name: str) -> str:
    return f"{{{ipxact.IPXACT_NAMESPACE}}}{name}"


def _local(node: etree._Element) -> str:
    return etree.QName(node).localname


def _child(parent: etree._Element, name: str) -> etree._Element | None:
    return next((item for item in parent if _local(item) == name), None)


def _text(parent: etree._Element, name: str) -> str:
    item = _child(parent, name)
    return (item.text or "").strip() if item is not None else ""


def _named(parent: etree._Element, tag: str, field: str, name: str) -> etree._Element | None:
    return next((item for item in parent if _local(item) == tag and _text(item, field) == name), None)


ROOT_ORDER = {
    "component": ["vendor", "library", "name", "version", "displayName", "shortDescription", "description", "busInterfaces", "channels", "model", "choices", "parameters", "assertions"],
    "design": ["vendor", "library", "name", "version", "displayName", "shortDescription", "description", "componentInstances", "interconnections", "adHocConnections", "choices", "parameters", "assertions"],
    "busDefinition": ["vendor", "library", "name", "version", "displayName", "shortDescription", "description", "directConnection", "broadcast", "isAddressable", "extends", "maxInitiators", "maxTargets", "systemGroupNames", "choices", "parameters", "assertions"],
    "abstractionDefinition": ["vendor", "library", "name", "version", "displayName", "shortDescription", "description", "busType", "extends", "ports", "choices", "parameters", "assertions"],
}


def _ensure_ordered(parent: etree._Element, name: str, order: list[str]) -> etree._Element:
    existing = _child(parent, name)
    if existing is not None:
        return existing
    node = etree.Element(_q(name))
    position = order.index(name)
    for index, child in enumerate(parent):
        child_name = _local(child)
        if child_name in order and order.index(child_name) > position:
            parent.insert(index, node)
            return node
    parent.append(node)
    return node


def _set_optional(parent: etree._Element, name: str, value: typing.Any, order: list[str]) -> None:
    existing = _child(parent, name)
    if value is None or value == "":
        if existing is not None:
            parent.remove(existing)
        return
    node = existing or _ensure_ordered(parent, name, order)
    node.text = "true" if value is True else "false" if value is False else str(value)


def _set_metadata(root: etree._Element, operation: dict[str, typing.Any]) -> None:
    present = [name for name in ("display_name", "short_description", "description") if name in operation]
    if not present:
        raise ValueError("set_entity_metadata must set at least one editable field.")
    values: dict[str, str | None] = {}
    for name in ("display_name", "short_description", "description"):
        if name in operation:
            values[name] = typing.cast(str | None, operation[name])
        else:
            current = _child(root, {
                "display_name": "displayName",
                "short_description": "shortDescription",
                "description": "description",
            }[name])
            values[name] = (current.text or "") if current is not None else None
    set_entity_metadata(root, **values)


def _upsert_parameter(root: etree._Element, value: dict[str, typing.Any]) -> None:
    allowed = {"name", "value", "resolve", "data_type", "rtl_type", "sign", "choice_ref", "minimum", "maximum", "description"}
    _reject_unknown_keys(value, allowed, "parameter")
    name = str(value.get("name", "")).strip()
    if not name:
        raise ValueError("Parameter name is required.")
    container = _ensure_ordered(root, "parameters", ROOT_ORDER[_local(root)])
    existing = _named(container, "parameter", "name", name)
    if existing is not None:
        container.remove(existing)
    parameter = etree.Element(_q("parameter"))
    if "rtl_type" in value:
        from spec2gds.spec.spec_format.rtl_interface import RTL_NAMESPACE
        parameter.set(f"{{{RTL_NAMESPACE}}}type", str(value["rtl_type"]))
    etree.SubElement(parameter, _q("name")).text = name
    if value.get("description"):
        etree.SubElement(parameter, _q("description")).text = str(value["description"])
    result = etree.SubElement(parameter, _q("value"))
    result.text = str(value.get("value", ""))
    for api_name, xml_name in (("resolve", "resolve"), ("data_type", "type"), ("sign", "sign"), ("choice_ref", "choiceRef"), ("minimum", "minimum"), ("maximum", "maximum")):
        if value.get(api_name) not in (None, ""):
            parameter.set(xml_name, str(value[api_name]))
    container.append(parameter)


def _delete_named(root: etree._Element, container_name: str, tag: str, field: str, name: str, *, prune: bool = True) -> None:
    container = _child(root, container_name)
    target = _named(container, tag, field, name) if container is not None else None
    if container is None or target is None:
        raise KeyError(f"Unknown {tag} named {name}.")
    container.remove(target)
    if prune and not len(container):
        root.remove(container)


def _upsert_component_port(root: etree._Element, value: dict[str, typing.Any]) -> None:
    upsert_component_port(root, value)


def _delete_component_port(root: etree._Element, name: str) -> None:
    model = _child(root, "model")
    ports = _child(model, "ports") if model is not None else None
    target = _named(ports, "port", "name", name) if ports is not None else None
    if model is None or ports is None or target is None:
        raise KeyError(f"Unknown component port: {name}")
    ports.remove(target)
    if not len(ports):
        model.remove(ports)
    if not len(model):
        root.remove(model)


def _vlnv_attrs(vlnv: str) -> dict[str, str]:
    parts = vlnv.split(":")
    if len(parts) != 4 or any(not item for item in parts):
        raise ValueError("VLNV must contain vendor:library:name:version.")
    return dict(zip(("vendor", "library", "name", "version"), parts, strict=True))


def _require_vlnv(revision: SpecRevision, kind: str, vlnv: str) -> None:
    revision.by_vlnv(typing.cast(typing.Any, kind), vlnv)


def _upsert_bus_interface(revision: SpecRevision, root: etree._Element, value: dict[str, typing.Any]) -> None:
    """Replace one interface after validating its declared protocol and port maps.

    Protocol VLNVs resolve against this revision; physical/logical names must exist.
    This supports owner operations even though the normal editor hides interfaces.
    """
    allowed = {"name", "role", "bus_vlnv", "abstraction_vlnv", "connection_required", "bits_in_lau", "endianness", "description", "port_maps"}
    _reject_unknown_keys(value, allowed, "bus interface")
    name = str(value.get("name", "")).strip()
    role = str(value.get("role", ""))
    bus_vlnv = str(value.get("bus_vlnv", ""))
    abstraction_vlnv = str(value.get("abstraction_vlnv", ""))
    if not name or role not in {"initiator", "target", "system", "monitor"}:
        raise ValueError("Bus interface requires a name and supported role.")
    _require_vlnv(revision, "bus_definition", bus_vlnv)
    _require_vlnv(revision, "abstraction_definition", abstraction_vlnv)
    abstraction = revision.by_vlnv("abstraction_definition", abstraction_vlnv)
    if getattr(abstraction, "bus_vlnv", "") != bus_vlnv:
        raise ValueError("Abstraction definition does not implement the selected bus definition.")
    container = _ensure_ordered(root, "busInterfaces", ROOT_ORDER["component"])
    existing = _named(container, "busInterface", "name", name)
    if existing is not None:
        container.remove(existing)
    node = etree.Element(_q("busInterface"))
    etree.SubElement(node, _q("name")).text = name
    if value.get("description"):
        etree.SubElement(node, _q("description")).text = str(value["description"])
    etree.SubElement(node, _q("busType"), **_vlnv_attrs(bus_vlnv))
    abstraction_types = etree.SubElement(node, _q("abstractionTypes"))
    abstraction_type = etree.SubElement(abstraction_types, _q("abstractionType"))
    etree.SubElement(abstraction_type, _q("abstractionRef"), **_vlnv_attrs(abstraction_vlnv))
    maps = value.get("port_maps", [])
    if not isinstance(maps, list):
        raise ValueError("port_maps must be an array.")
    if maps:
        map_container = etree.SubElement(abstraction_type, _q("portMaps"))
        model = _child(root, "model")
        physical_container = _child(model, "ports") if model is not None else None
        physical_ports = {
            _text(item, "name")
            for item in (list(physical_container) if physical_container is not None else [])
            if _local(item) == "port"
        }
        logical_ports = set(getattr(abstraction, "logical_ports", ()))
        for mapping in maps:
            if not isinstance(mapping, dict):
                raise ValueError("Each port map must be an object.")
            logical = str(mapping.get("logical", ""))
            physical = str(mapping.get("physical", ""))
            if logical not in logical_ports or physical not in physical_ports:
                raise ValueError("Port maps must reference existing logical and physical ports.")
            port_map = etree.SubElement(map_container, _q("portMap"))
            logical_node = etree.SubElement(port_map, _q("logicalPort"))
            etree.SubElement(logical_node, _q("name")).text = logical
            physical_node = etree.SubElement(port_map, _q("physicalPort"))
            etree.SubElement(physical_node, _q("name")).text = physical
            if mapping.get("tie_off") not in (None, ""):
                etree.SubElement(port_map, _q("logicalTieOff")).text = str(mapping["tie_off"])
            if mapping.get("invert") is True:
                port_map.set("invert", "true")
            if mapping.get("informative") is True:
                etree.SubElement(port_map, _q("isInformative")).text = "true"
    etree.SubElement(node, _q(role))
    for key, xml_name in (("connection_required", "connectionRequired"), ("bits_in_lau", "bitsInLau"), ("endianness", "endianness")):
        if value.get(key) not in (None, ""):
            item = etree.SubElement(node, _q(xml_name))
            item.text = "true" if value[key] is True else "false" if value[key] is False else str(value[key])
    container.append(node)


def _upsert_channel(root: etree._Element, value: dict[str, typing.Any]) -> None:
    _reject_unknown_keys(value, {"name", "interfaces", "description"}, "channel")
    name = str(value.get("name", ""))
    interfaces = value.get("interfaces")
    if not name or not isinstance(interfaces, list) or len(interfaces) < 2:
        raise ValueError("Channel requires a name and at least two interface names.")
    interface_container = _child(root, "busInterfaces")
    known = {
        _text(item, "name")
        for item in (list(interface_container) if interface_container is not None else [])
        if _local(item) == "busInterface"
    }
    if any(str(item) not in known for item in interfaces):
        raise ValueError("Channel references an unknown component interface.")
    container = _ensure_ordered(root, "channels", ROOT_ORDER["component"])
    existing = _named(container, "channel", "name", name)
    if existing is not None:
        container.remove(existing)
    channel = etree.Element(_q("channel"))
    etree.SubElement(channel, _q("name")).text = name
    if value.get("description"):
        etree.SubElement(channel, _q("description")).text = str(value["description"])
    for interface in interfaces:
        reference = etree.SubElement(channel, _q("busInterfaceRef"))
        etree.SubElement(reference, _q("localName")).text = str(interface)
    container.append(channel)


def _update_bus_definition(revision: SpecRevision, root: etree._Element, value: dict[str, typing.Any]) -> None:
    allowed = {"direct_connection", "broadcast", "addressable", "extends_vlnv", "max_initiators", "max_targets", "system_groups"}
    _reject_unknown_keys(value, allowed, "bus definition properties")
    if not value:
        raise ValueError("Bus definition update requires at least one property.")
    order = ROOT_ORDER["busDefinition"]
    for key, xml_name in (("direct_connection", "directConnection"), ("broadcast", "broadcast"), ("addressable", "isAddressable"), ("max_initiators", "maxInitiators"), ("max_targets", "maxTargets")):
        if key in value:
            _set_optional(root, xml_name, value[key], order)
    if "extends_vlnv" in value:
        vlnv = str(value["extends_vlnv"] or "")
        existing = _child(root, "extends")
        if not vlnv:
            if existing is not None:
                root.remove(existing)
        else:
            _require_vlnv(revision, "bus_definition", vlnv)
            node = existing or _ensure_ordered(root, "extends", order)
            node.attrib.clear()
            node.attrib.update(_vlnv_attrs(vlnv))
    if "system_groups" in value:
        groups = value["system_groups"]
        existing = _child(root, "systemGroupNames")
        if not isinstance(groups, list):
            raise ValueError("system_groups must be an array.")
        if not groups:
            if existing is not None:
                root.remove(existing)
        else:
            node = existing or _ensure_ordered(root, "systemGroupNames", order)
            node.clear()
            for group in groups:
                etree.SubElement(node, _q("systemGroupName")).text = str(group)


def _set_abstraction_bus_type(revision: SpecRevision, root: etree._Element, vlnv: str) -> None:
    _require_vlnv(revision, "bus_definition", vlnv)
    node = _child(root, "busType")
    if node is None:
        node = _ensure_ordered(root, "busType", ROOT_ORDER["abstractionDefinition"])
    node.attrib.clear()
    node.attrib.update(_vlnv_attrs(vlnv))


def _upsert_abstraction_port(root: etree._Element, value: dict[str, typing.Any]) -> None:
    allowed = {"name", "style", "match", "description", "qualifiers", "on_initiator", "on_target", "on_system"}
    _reject_unknown_keys(value, allowed, "abstraction port")
    name = str(value.get("name", ""))
    style = str(value.get("style", "wire"))
    if not name or style not in {"wire", "transactional"}:
        raise ValueError("Abstraction port requires a name and wire/transactional style.")
    container = _child(root, "ports")
    if container is None:
        container = _ensure_ordered(root, "ports", ROOT_ORDER["abstractionDefinition"])
    existing = _named(container, "port", "logicalName", name)
    if existing is not None:
        container.remove(existing)
    port = etree.Element(_q("port"))
    etree.SubElement(port, _q("logicalName")).text = name
    if value.get("description"):
        etree.SubElement(port, _q("description")).text = str(value["description"])
    if value.get("match") is True:
        etree.SubElement(port, _q("match")).text = "true"
    style_node = etree.SubElement(port, _q(style))
    qualifiers = value.get("qualifiers", [])
    if qualifiers:
        if not isinstance(qualifiers, list):
            raise ValueError("qualifiers must be an array.")
        qualifier = etree.SubElement(style_node, _q("qualifier"))
        for item in qualifiers:
            etree.SubElement(qualifier, _q(str(item))).text = "true"
    systems = value.get("on_system", [])
    if systems and not isinstance(systems, list):
        raise ValueError("on_system must be an array.")
    for mode_name, xml_name in (("on_initiator", "onInitiator"), ("on_target", "onTarget")):
        mode = value.get(mode_name)
        if mode:
            _append_abstraction_mode(style_node, xml_name, typing.cast(dict[str, typing.Any], mode), style)
    for mode in systems or []:
        _append_abstraction_mode(style_node, "onSystem", typing.cast(dict[str, typing.Any], mode), style)
    container.append(port)


def _append_abstraction_mode(parent: etree._Element, name: str, value: dict[str, typing.Any], style: str) -> None:
    allowed = {"group", "direction", "initiative", "presence", "width", "bus_width"}
    _reject_unknown_keys(value, allowed, f"abstraction {name} mode")
    node = etree.SubElement(parent, _q(name))
    if name == "onSystem":
        group = str(value.get("group", ""))
        if not group:
            raise ValueError("onSystem mode requires group.")
        etree.SubElement(node, _q("group")).text = group
    if value.get("presence"):
        etree.SubElement(node, _q("presence")).text = str(value["presence"])
    if style == "wire":
        if value.get("width") not in (None, ""):
            etree.SubElement(node, _q("width")).text = str(value["width"])
        if value.get("direction"):
            etree.SubElement(node, _q("direction")).text = str(value["direction"])
    else:
        if value.get("initiative"):
            etree.SubElement(node, _q("initiative")).text = str(value["initiative"])
        if value.get("bus_width") not in (None, ""):
            etree.SubElement(node, _q("busWidth")).text = str(value["bus_width"])


def _jsonable(value: typing.Any) -> typing.Any:
    if isinstance(value, pydantic.BaseModel):
        return value.model_dump(mode="json")
    if dataclasses.is_dataclass(value):
        return {field.name: _jsonable(getattr(value, field.name)) for field in dataclasses.fields(value) if not field.name.startswith("_")}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value
