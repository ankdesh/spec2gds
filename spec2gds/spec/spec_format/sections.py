"""Typed, forward-compatible entity sections stored in ``.spec`` annotations.

Reviewer path: section registration, indexed annotation files and parent
references form one package contract. SystemVerilog bodies remain explicit
source content; rendering or generator templates must not invent their behavior.
"""

from __future__ import annotations

import json
import re
import typing
from dataclasses import dataclass

import pydantic

from spec2gds.spec.spec_format.models import (
    ID_PATTERN,
    AnnotationSchemaEntry,
    EntityRef,
    StrictModel,
    sha256_digest,
    validate_safe_path,
)

SECTION_NAMESPACE = "spec2gds.entity-sections"
SECTION_ROOT = "annotations/entity-sections"
SECTION_INDEX_PATH = f"{SECTION_ROOT}/index.json"
SECTION_INDEX_VERSION = 1
SV_MEDIA_TYPE = "text/x-systemverilog"
SV_MAX_BYTES = 256 * 1024


@dataclass(frozen=True)
class SectionTypeDefinition:
    """One centrally registered entity-section contract."""

    section_type: str
    version: int
    title: str
    entity_kinds: tuple[str, ...]
    maximum_per_entity: int
    order: int
    payload_validator: typing.Callable[[typing.Mapping[str, typing.Any]], typing.Any]
    storage_codec: str
    renderer_key: str
    persisted: bool
    editable: bool
    deletable: bool
    downstream_consumers: tuple[str, ...] = ()


def _content_payload(payload: typing.Mapping[str, typing.Any]) -> str:
    content = payload.get("content")
    if not isinstance(content, str):
        raise ValueError("Section payload requires a string content field.")
    return content


def _ports_payload(payload: typing.Mapping[str, typing.Any]) -> list[typing.Any]:
    ports = payload.get("ports")
    if not isinstance(ports, list):
        raise ValueError("Ports section payload requires a ports list.")
    return ports


SECTION_TYPES: dict[str, SectionTypeDefinition] = {
    "text": SectionTypeDefinition(
        "text", 1, "Text", ("component", "design"), 1, 10,
        _content_payload, "ipxact.description", "text", False, True, False,
    ),
    "ports": SectionTypeDefinition(
        "ports", 1, "Ports", ("component",), 1, 20,
        _ports_payload, "ipxact.ports", "ports", False, True, False,
    ),
    "sv": SectionTypeDefinition(
        "sv", 1, "SystemVerilog", ("component", "design"), 1, 30,
        lambda payload: normalize_systemverilog(_content_payload(payload)),
        "annotation.utf8_lf", "sv", True, True, True, ("rtl.generate", "ai-assistant"),
    ),
}


class SectionIndexEntry(StrictModel):
    """Persisted parentship and integrity metadata for one section payload."""

    section_id: str
    section_type: str
    type_version: int
    parent: EntityRef = pydantic.Field(validation_alias=pydantic.AliasChoices("parent", "owner"))
    path: str
    media_type: str
    sha256: str
    usage: typing.Literal["implementation", "reference"] = "implementation"

    @pydantic.field_validator("section_id")
    @classmethod
    def _section_id(cls, value: str) -> str:
        if not ID_PATTERN.fullmatch(value):
            raise ValueError("Entity section IDs must be XML-ID-compatible.")
        return value

    @pydantic.field_validator("path")
    @classmethod
    def _path(cls, value: str) -> str:
        value = validate_safe_path(value)
        if not value.startswith(f"{SECTION_ROOT}/"):
            raise ValueError("Entity section content must be below its registered annotation root.")
        return value


class SectionIndex(StrictModel):
    """Versioned index for persisted entity sections."""

    version: typing.Literal[1, 2] = SECTION_INDEX_VERSION
    sections: list[SectionIndexEntry] = pydantic.Field(default_factory=list)

    @pydantic.model_validator(mode="after")
    def _usage_version(self) -> "SectionIndex":
        if self.version == 1 and any(item.usage != "implementation" for item in self.sections):
            raise ValueError("Reference SV requires entity-section index version 2.")
        return self


@dataclass(frozen=True)
class SectionIR:
    """Immutable decoded entity section exposed by SpecIR."""

    section_id: str
    section_type: str
    type_version: int
    title: str
    parent: EntityRef
    media_type: str
    source_path: str
    source_sha256: str
    content: str
    usage: typing.Literal["implementation", "reference"] = "implementation"


def _json_bytes(value: typing.Any) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _registered(manifest: typing.Any) -> bool:
    return any(item.namespace == SECTION_NAMESPACE for item in manifest.annotation_schemas)


def load_entity_sections(manifest: typing.Any, files: typing.Mapping[str, bytes]) -> tuple[SectionIR, ...]:
    """Decode and strictly validate all registered persisted sections."""
    if SECTION_INDEX_PATH not in files:
        if _registered(manifest):
            raise ValueError("Entity-section annotation registration is missing index.json.")
        return ()
    if not _registered(manifest):
        raise ValueError("Entity-section index is not owned by a registered annotation schema.")
    index = SectionIndex.model_validate_json(files[SECTION_INDEX_PATH])
    known = {item.entity_id: item.kind for item in manifest.documents}
    seen_ids: set[str] = set()
    counts: dict[tuple[str, str], int] = {}
    result: list[SectionIR] = []
    indexed_paths = {SECTION_INDEX_PATH}
    for entry in index.sections:
        if entry.section_id in seen_ids:
            raise ValueError(f"Duplicate entity section ID: {entry.section_id}")
        seen_ids.add(entry.section_id)
        definition = SECTION_TYPES.get(entry.section_type)
        if definition is None or not definition.persisted:
            raise ValueError(f"Unsupported persisted entity section type: {entry.section_type}")
        if entry.type_version != definition.version:
            raise ValueError(f"Unsupported {entry.section_type} section version: {entry.type_version}")
        if entry.parent.document_id != manifest.document_id or known.get(entry.parent.entity_id) != entry.parent.entity_kind:
            raise ValueError(f"Entity section {entry.section_id} references an unknown parent.")
        if entry.parent.entity_kind not in definition.entity_kinds:
            raise ValueError(f"Section type {entry.section_type} cannot attach to {entry.parent.entity_kind}.")
        key = (entry.parent.entity_id, entry.section_type)
        counts[key] = counts.get(key, 0) + 1
        if counts[key] > definition.maximum_per_entity:
            raise ValueError(f"Parent {entry.parent.entity_id} has too many {entry.section_type} sections.")
        data = files.get(entry.path)
        if data is None:
            raise ValueError(f"Missing entity section content: {entry.path}")
        indexed_paths.add(entry.path)
        if sha256_digest(data) != entry.sha256:
            raise ValueError(f"Entity section hash mismatch: {entry.path}")
        if entry.section_type == "sv":
            if entry.media_type != SV_MEDIA_TYPE or not entry.path.endswith(".sv"):
                raise ValueError("SystemVerilog sections require text/x-systemverilog .sv content.")
            if len(data) > SV_MAX_BYTES:
                raise ValueError("SystemVerilog section exceeds the 256 KiB limit.")
            try:
                content = data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("SystemVerilog section content must be UTF-8.") from exc
            if normalize_systemverilog(content) != content:
                raise ValueError("SystemVerilog section content must use normalized LF line endings.")
        else:  # pragma: no cover - registry currently has one persisted type.
            content = data.decode("utf-8")
        result.append(SectionIR(
            entry.section_id, entry.section_type, entry.type_version,
            "SystemVerilog reference — excluded from implementation" if entry.usage == "reference" else definition.title,
            entry.parent, entry.media_type, entry.path, entry.sha256, content, entry.usage,
        ))
    actual_paths = {path for path in files if path.startswith(f"{SECTION_ROOT}/")}
    if actual_paths != indexed_paths:
        raise ValueError("Entity-section index does not match its annotation files.")
    return tuple(result)


def normalize_systemverilog(value: str) -> str:
    """Normalize portable editor text before size and syntax-boundary checks."""
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    if "\x00" in normalized:
        raise ValueError("SystemVerilog sections cannot contain NUL characters.")
    if len(normalized.encode("utf-8")) > SV_MAX_BYTES:
        raise ValueError("SystemVerilog section exceeds the 256 KiB limit.")
    validate_systemverilog_body(normalized)
    return normalized


def _code_without_comments_or_strings(value: str) -> str:
    """Return token-bearing text while preserving newlines for diagnostics."""
    output: list[str] = []
    index = 0
    state = "code"
    while index < len(value):
        char = value[index]
        pair = value[index:index + 2]
        if state == "code" and pair == "//":
            state = "line"
            output.extend("  ")
            index += 2
        elif state == "code" and pair == "/*":
            state = "block"
            output.extend("  ")
            index += 2
        elif state == "code" and char == '"':
            state = "string"
            output.append(" ")
            index += 1
        elif state == "line":
            output.append("\n" if char == "\n" else " ")
            if char == "\n":
                state = "code"
            index += 1
        elif state == "block":
            output.append("\n" if char == "\n" else " ")
            if pair == "*/":
                output.append(" ")
                index += 2
                state = "code"
            else:
                index += 1
        elif state == "string":
            output.append("\n" if char == "\n" else " ")
            if char == "\\" and index + 1 < len(value):
                output.append(" ")
                index += 2
            else:
                if char == '"':
                    state = "code"
                index += 1
        else:
            output.append(char)
            index += 1
    return "".join(output)


def validate_systemverilog_body(value: str) -> None:
    """Reject constructs that escape the portable generated-module boundary."""
    code = _code_without_comments_or_strings(value)
    if re.search(r"\b(?:module|endmodule)\b", code):
        raise ValueError("SystemVerilog sections are module bodies and cannot declare module/endmodule.")
    if re.search(r"`(?:include|line)\b", code):
        raise ValueError("SystemVerilog sections cannot use external `include or user `line directives.")


def upsert_systemverilog_section(package: typing.Any, parent: EntityRef, content: str, section_id: str | None = None) -> SectionIR:
    """Create or replace the singleton SV section attached to one parent."""
    if parent.document_id != package.manifest.document_id or parent.entity_kind not in {"component", "design"}:
        raise ValueError("SystemVerilog sections require a local component or design parent.")
    known = {item.entity_id: item.kind for item in package.manifest.documents}
    if known.get(parent.entity_id) != parent.entity_kind:
        raise KeyError(f"Unknown {parent.entity_kind}: {parent.entity_id}")
    definition = SECTION_TYPES["sv"]
    normalized = typing.cast(str, definition.payload_validator({"content": content}))
    existing = next((item for item in load_entity_sections(package.manifest, package.files)
                     if item.parent == parent and item.section_type == "sv"), None)
    identity = existing.section_id if existing else (section_id or f"section_sv_{parent.entity_id}")
    if not ID_PATTERN.fullmatch(identity):
        raise ValueError("Entity section IDs must be XML-ID-compatible.")
    if existing and section_id and section_id != existing.section_id:
        raise ValueError("The singleton SystemVerilog section ID cannot be changed.")
    path = f"{SECTION_ROOT}/sv/{identity}.sv"
    data = normalized.encode("utf-8")
    entry = SectionIndexEntry(
        section_id=identity, section_type="sv", type_version=1, parent=parent,
        path=path, media_type=SV_MEDIA_TYPE, sha256=sha256_digest(data),
        usage=existing.usage if existing else "implementation",
    )
    current = SectionIndex.model_validate_json(package.files[SECTION_INDEX_PATH]) if SECTION_INDEX_PATH in package.files else SectionIndex()
    entries = [item for item in current.sections if not (item.parent == parent and item.section_type == "sv")]
    entries.append(entry)
    entries.sort(key=lambda item: (item.parent.entity_kind, item.parent.entity_id, item.section_type, item.section_id))
    for item in current.sections:
        if item.parent == parent and item.section_type == "sv":
            package.files.pop(item.path, None)
    package.files[path] = data
    _write_section_index(package, entries, current.version)
    return next(item for item in load_entity_sections(package.manifest, package.files) if item.section_id == identity)


def _write_section_index(package: typing.Any, entries: list[SectionIndexEntry], previous_version: int = 1) -> None:
    """Keep legacy bytes readable and fail closed on reference-SV metadata."""
    version = 2 if previous_version == 2 or any(item.usage == "reference" for item in entries) else 1
    value = SectionIndex(version=version, sections=entries).model_dump(mode="json")
    if version == 1:
        for entry in value["sections"]:
            entry.pop("usage", None)
    package.files[SECTION_INDEX_PATH] = _json_bytes(value)
    schemas = [item for item in package.manifest.annotation_schemas if item.namespace != SECTION_NAMESPACE]
    schemas.append(AnnotationSchemaEntry(namespace=SECTION_NAMESPACE, version=version, path_prefix=SECTION_ROOT))
    package.manifest = package.manifest.model_copy(update={"annotation_schemas": schemas})


def set_section_usage(package: typing.Any, parent: EntityRef, section_id: str, usage: typing.Literal["implementation", "reference"]) -> None:
    """Change an SV Section's role without changing its content or identity."""
    load_entity_sections(package.manifest, package.files)
    index = SectionIndex.model_validate_json(package.files[SECTION_INDEX_PATH])
    match = next((item for item in index.sections if item.section_id == section_id and item.parent == parent and item.section_type == "sv"), None)
    if match is None:
        raise ValueError("Unknown SystemVerilog Section.")
    replacement = SectionIndexEntry.model_validate({**match.model_dump(), "usage": usage})
    _write_section_index(package, [replacement if item.section_id == section_id else item for item in index.sections], index.version)


def delete_entity_section(package: typing.Any, parent: EntityRef, section_type: str, section_id: str | None = None) -> None:
    """Delete one registered persisted section and clean an empty annotation root."""
    sections = load_entity_sections(package.manifest, package.files)
    matches = [item for item in sections if item.parent == parent and item.section_type == section_type
               and (section_id is None or item.section_id == section_id)]
    if not matches:
        raise KeyError(f"Parent {parent.entity_id} has no {section_type} section.")
    for item in matches:
        package.files.pop(item.source_path, None)
    remaining = [item for item in sections if item not in matches]
    _write_remaining_sections(package, remaining)


def _write_remaining_sections(package: typing.Any, remaining: list[SectionIR]) -> None:
    """Rewrite the shared index/registration after one or more removals."""
    if remaining:
        entries = [SectionIndexEntry(
            section_id=item.section_id, section_type=item.section_type, type_version=item.type_version,
            parent=item.parent, path=item.source_path, media_type=item.media_type, sha256=item.source_sha256, usage=item.usage,
        ) for item in remaining]
        previous = SectionIndex.model_validate_json(package.files[SECTION_INDEX_PATH]).version
        _write_section_index(package, entries, previous)
    else:
        package.files.pop(SECTION_INDEX_PATH, None)
        package.manifest = package.manifest.model_copy(update={
            "annotation_schemas": [item for item in package.manifest.annotation_schemas if item.namespace != SECTION_NAMESPACE]
        })


def delete_sections_for_parent(package: typing.Any, parent: EntityRef) -> None:
    """Cascade persisted sections when their owning source entity is deleted."""
    sections = list(load_entity_sections(package.manifest, package.files))
    matches = [item for item in sections if item.parent == parent]
    for item in matches:
        package.files.pop(item.source_path, None)
    if matches:
        _write_remaining_sections(package, [item for item in sections if item not in matches])
