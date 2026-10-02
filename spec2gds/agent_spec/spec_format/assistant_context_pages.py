"""Lossless, revision-bound semantic context pages for model-facing reads.

Records use JSON paths and string offsets so even a large SV body remains readable
without an opaque spill file. Projection text and duplicate full IR are omitted.
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Iterator
from typing import Any

from spec2gds.agent_spec.spec_format import ipxact
from spec2gds.agent_spec.spec_format.assistant import (
    SUPPORTED_OPERATION_TYPES,
    _identity,
    _jsonable,
    _ref_key,
    _writable_narrative_ids,
    _writable_refs,
)
from spec2gds.agent_spec.spec_format.ir import SpecRevision, _walk_blocks
from spec2gds.agent_spec.spec_format.models import EntityRef
from spec2gds.agent_spec.spec_format.naming import document_name

PAGE_BYTES = 30 * 1024


def _records(value: Any, path: tuple[str | int, ...] = ()) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict) and value:
        for key, item in value.items():
            yield from _records(item, (*path, key))
    elif isinstance(value, list) and value:
        for index, item in enumerate(value):
            yield from _records(item, (*path, index))
    elif isinstance(value, str):
        offset = 0
        if not value:
            yield {"path": path, "value": value}
        while offset < len(value):
            end = min(len(value), offset + 4096)
            while len(json.dumps(value[offset:end], ensure_ascii=False).encode()) > 8192:
                end = offset + (end - offset) // 2
            yield {"path": path, "value": value[offset:end], "offset": offset, "length": len(value)}
            offset = end
    else:
        yield {"path": path, "value": value}


def build_context_page(
    revision: SpecRevision,
    target: EntityRef | None = None,
    *,
    entity_ids: list[str] | None = None,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Return a bounded page; changed revision, selection or malformed cursor fails."""
    entities = (
        *revision.components,
        *revision.designs,
        *revision.bus_definitions,
        *revision.abstraction_definitions,
    )
    known = {item.ref.entity_id for item in entities} | {
        item.block_id for item in _walk_blocks(revision.narrative.blocks)
    }
    if entity_ids is not None and (
        not entity_ids
        or len(set(entity_ids)) != len(entity_ids)
        or any(item not in known for item in entity_ids)
    ):
        raise ValueError("entity_ids must contain distinct existing entity IDs.")
    if target:
        revision.resolve(target)
    writable_refs = (
        _writable_refs(revision, target) if target else tuple(item.ref for item in entities)
    )
    writable = {_ref_key(item) for item in writable_refs}
    writable_narrative = (
        _writable_narrative_ids(revision, target)
        if target
        else {block.block_id for block in _walk_blocks(revision.narrative.blocks)}
    )
    selection = hashlib.sha256(
        json.dumps(
            [target.model_dump() if target else None, sorted(entity_ids or [])], sort_keys=True
        ).encode()
    ).hexdigest()
    offset = 0
    if cursor:
        try:
            decoded = json.loads(base64.urlsafe_b64decode(cursor.encode()))
            if (
                set(decoded) != {"revision", "selection", "offset"}
                or type(decoded["offset"]) is not int
                or decoded["offset"] < 0
            ):
                raise ValueError("Malformed context cursor.")
            if (
                decoded["revision"] != revision.source_revision_hash
                or decoded["selection"] != selection
            ):
                raise ValueError(
                    "Context cursor is stale or belongs to a different selection; start a fresh read."
                )
            offset = decoded["offset"]
        except (TypeError, KeyError, json.JSONDecodeError, UnicodeError) as exc:
            raise ValueError("Malformed context cursor.") from exc
    package = revision.to_package()
    documents = {item.entity_id: item for item in revision.manifest.documents}
    content: dict[str, Any] = {
        "writable": {
            "entity_refs": [item.model_dump(mode="json") for item in writable_refs],
            "narrative_block_ids": sorted(writable_narrative),
            "document_operations": sorted(SUPPORTED_OPERATION_TYPES) if target is None else [],
        },
        "entities": [],
        "narrative": [],
        "available_references": [_identity(item) for item in entities],
        "diagnostics": list(revision.diagnostics),
    }
    for entity in entities:
        if entity_ids is not None and entity.ref.entity_id not in entity_ids:
            continue
        root = ipxact.parse_xml(package.files[documents[entity.ref.entity_id].path])
        descriptions = root.xpath("./*[local-name()='description']/text()")
        internal = (
            revision.internal_design(entity.ref) if entity.ref.entity_kind == "component" else None
        )
        content["entities"].append(
            {
                "entity": _jsonable(entity),
                "writable": _ref_key(entity.ref) in writable,
                "description": "".join(descriptions),
                "sections": [_jsonable(item) for item in revision.entity_sections_for(entity.ref)],
                "internal_design": internal.ref.model_dump(mode="json") if internal else None,
            }
        )
    for block in revision.narrative.blocks:
        if entity_ids is None or any(
            item.block_id in entity_ids
            or any(ref.entity_id in entity_ids for ref in item.entity_refs)
            for item in _walk_blocks([block])
        ):
            content["narrative"].append(_jsonable(block))
    all_records = list(_records(content))
    if offset > len(all_records):
        raise ValueError("Context cursor offset is outside this result.")
    page: dict[str, Any] = {
        "schema_version": "spec2gds.assistant-context-page.v1",
        "document_id": revision.document_id,
        "name": document_name(revision),
        "source_revision_hash": revision.source_revision_hash,
        "scope": "entity" if target else "document",
        "target": target.model_dump(mode="json") if target else None,
        "records": [],
        "incomplete": False,
        "next_cursor": None,
        "instructions": "Records use JSON paths; concatenate string fragments at their offset. Read next_cursor until complete before replacing fields. Stored RTL is behavioral authority; descriptions are advisory.",
    }
    while offset < len(all_records):
        candidate = {**page, "records": [*page["records"], all_records[offset]]}
        if len(json.dumps(candidate, ensure_ascii=False).encode()) > PAGE_BYTES - 1024:
            if not page["records"]:
                raise ValueError("Context record cannot fit within the reply budget.")
            break
        page["records"].append(all_records[offset])
        offset += 1
    if offset < len(all_records):
        page["incomplete"] = True
        page["next_cursor"] = base64.urlsafe_b64encode(
            json.dumps(
                {
                    "revision": revision.source_revision_hash,
                    "selection": selection,
                    "offset": offset,
                }
            ).encode()
        ).decode()
    return page
