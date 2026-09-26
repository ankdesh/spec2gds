"""Owner-published assistant operation schema and validation."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema


@lru_cache(maxsize=1)
def _schema() -> dict[str, Any]:
    path = Path(__file__).with_name("assistant_operation_schema.json")
    schema = json.loads(path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return schema


_NARRATIVE_OPERATIONS = {
    "upsert_narrative_block", "delete_narrative_block", "reorder_narrative_blocks",
    "set_narrative_entity_links",
}
_DESIGN_OPERATIONS = {
    "upsert_instance", "delete_instance", "reorder_instances", "upsert_connection",
    "delete_connection", "reorder_connections",
}
_COMPONENT_OPERATIONS = {
    "upsert_parameter", "delete_parameter", "upsert_component_port", "delete_component_port",
    "upsert_bus_interface", "delete_bus_interface", "upsert_channel", "delete_channel",
    "set_internal_design", "clear_internal_design",
}
_ENTITY_SECTIONS = {"upsert_entity_section", "delete_entity_section"}


def operation_contract(
    scope: str,
    entity_kind: str | None = None,
    include_owned_design: bool = False,
) -> dict[str, Any]:
    if scope not in {"document", "entity"}:
        raise ValueError("scope must be document or entity.")
    if scope == "entity" and entity_kind not in {
        "component", "design", "bus_definition", "abstraction_definition", "narrative_block"
    }:
        raise ValueError("Unsupported entity kind for assistant operations.")
    allowed = {"create_entity"} if scope == "document" else set(_NARRATIVE_OPERATIONS)
    if scope == "entity" and entity_kind != "narrative_block":
        allowed |= {"set_entity_metadata", *_ENTITY_SECTIONS}
    if entity_kind == "component":
        allowed |= _COMPONENT_OPERATIONS
        if include_owned_design:
            allowed |= _DESIGN_OPERATIONS
            allowed -= {"upsert_component_port", "delete_component_port"}
    elif entity_kind == "design":
        allowed |= _DESIGN_OPERATIONS
    elif entity_kind == "bus_definition":
        allowed.add("update_bus_definition")
    elif entity_kind == "abstraction_definition":
        allowed |= {"set_abstraction_bus_type", "upsert_abstraction_port", "delete_abstraction_port"}
    source = _schema()
    branches = [
        branch for branch in source["oneOf"]
        if branch["properties"]["type"]["const"] in allowed
    ]
    schema = {"$schema": source["$schema"], "oneOf": branches}
    digest = hashlib.sha256(
        json.dumps(schema, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {"schema_version": 1, "digest": f"sha256:{digest}", "operation_schema": schema}


def validate_assistant_operations(
    scope: str, operations: list[dict[str, Any]], entity_kind: str | None = None,
    include_owned_design: bool = False,
) -> None:
    validator = jsonschema.Draft202012Validator(
        operation_contract(scope, entity_kind, include_owned_design)["operation_schema"]
    )
    for index, operation in enumerate(operations):
        errors = list(validator.iter_errors(operation))
        if errors:
            raise ValueError(f"Operation {index + 1} does not match the owner schema: {errors[0].message}")
