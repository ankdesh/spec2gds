"""Persisted editor-only relationships that do not belong in document text.

The semantic document parser can infer headings, paragraphs, tables, and links
from `content.xml`, but it cannot infer every relationship the editor needs.
This module owns the small JSON sidecar stored inside the `.spec` archive under
`spec_data/agent-spec-editor/`. Keeping this shape explicit lets the editor
round-trip UI state without polluting the user-visible document body.
"""

import json
import typing

import pydantic


RELATIONS_PATH: str = "spec_data/agent-spec-editor/relations.json"
RELATIONS_MEDIA_TYPE: str = "application/vnd.spec2gds.spec-editor-relations+json"


class HeadingIpxactAttachment(pydantic.BaseModel):
    """An IP-XACT file attached to a document heading."""

    file_path: str


class SectionVersionRef(pydantic.BaseModel):
    """One variant in a metadata-owned section version group."""

    version: str
    heading_id: str
    block_ids: list[str] = pydantic.Field(default_factory=list)


class SectionVersionGroup(pydantic.BaseModel):
    """Metadata relation describing mutually exclusive heading sections."""

    group_id: str
    title: str
    level: int
    variants: list[SectionVersionRef]
    active_version: str


class EditorRelations(pydantic.BaseModel):
    """Global editor relations stored as custom agent-spec metadata."""

    version: int = 2
    section_groups: list[SectionVersionGroup] = pydantic.Field(default_factory=list)
    ipxact_attachments: dict[str, list[HeadingIpxactAttachment]] = pydantic.Field(default_factory=dict)

    def active_versions(self) -> dict[str, str]:
        return {group.group_id: group.active_version for group in self.section_groups}


def load_relations(raw_bytes: bytes | None) -> EditorRelations:
    """Load editor relations from archive bytes, falling back to an empty model.

    Relations are user-editable metadata, so callers should be resilient to
    older files, missing files, and partially written JSON. Invalid relation
    state should not make the whole document unreadable.
    """
    if raw_bytes is None:
        return EditorRelations()
    try:
        raw_data = json.loads(raw_bytes.decode("utf-8"))
    except Exception:
        return EditorRelations()
    if not isinstance(raw_data, dict):
        return EditorRelations()
    try:
        return EditorRelations.model_validate(raw_data)
    except Exception:
        return EditorRelations()


def dump_relations(relations: EditorRelations) -> bytes:
    """Serialize relations deterministically for stable diffs and hashes."""
    return json.dumps(
        relations.model_dump(),
        indent=2,
        sort_keys=True,
    ).encode("utf-8")


def normalize_ipxact_path(file_path: str) -> str:
    """Normalize user/editor IP-XACT file references to archive paths.

    The UI often deals in friendly names such as `timer` or `timer.xml`, while
    the package stores the actual bytes under `spec_data/ipxact/`. Normalizing
    at the boundary keeps relation records consistent.
    """
    if file_path.startswith("spec_data/ipxact/"):
        return file_path
    if file_path.endswith(".xml"):
        return f"spec_data/ipxact/{file_path}"
    return f"spec_data/ipxact/{file_path}.xml"


def attachment_paths(
    attachments: typing.Iterable[HeadingIpxactAttachment | dict[str, typing.Any]],
) -> list[str]:
    """Return unique normalized attachment paths while preserving first-seen order.

    The `dict` arm is intentional: API payloads may be plain JSON dictionaries
    before Pydantic has rebuilt them as `HeadingIpxactAttachment` instances.
    """
    seen: set[str] = set()
    paths: list[str] = []
    for attachment in attachments:
        if isinstance(attachment, dict):
            raw_path = attachment.get("file_path", "")
        else:
            raw_path = attachment.file_path
        if not isinstance(raw_path, str) or not raw_path:
            continue
        path = normalize_ipxact_path(raw_path)
        if path in seen:
            continue
        seen.add(path)
        paths.append(path)
    return paths
