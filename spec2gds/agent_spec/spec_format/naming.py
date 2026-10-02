"""Human-facing names, independent of source identity and hardware symbols.

Names live in existing title/displayName fields. This module supplies the single
Spec-side policy used by owners, projections, snapshots, and generators.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

from spec2gds.agent_spec.spec_format import ipxact

if TYPE_CHECKING:
    from spec2gds.agent_spec.spec_format.archive import SpecPackage
    from spec2gds.agent_spec.spec_format.ir import SpecRevision
    from spec2gds.agent_spec.spec_format.models import EntityRef


def clean_name(value: str) -> str:
    """Normalize a readable, single-line name without changing its case."""
    value = " ".join(unicodedata.normalize("NFKC", value).split())
    if not value:
        raise ValueError("A name is required.")
    if len(value) > 200:
        raise ValueError("Name must contain 1 to 200 characters.")
    return value


def name_key(value: str) -> str:
    return clean_name(value).casefold()


def unique_name(value: str, existing: Iterable[str]) -> str:
    """Return the base name or its first available readable numeric suffix."""
    value = clean_name(value)
    occupied = {name_key(item) for item in existing if item.strip()}
    candidate, number = value, 2
    while name_key(candidate) in occupied:
        suffix = f" {number}"
        candidate = value[:200 - len(suffix)].rstrip() + suffix
        number += 1
    return candidate


def require_unique_name(value: str, existing: Iterable[str]) -> str:
    value = clean_name(value)
    suggested = unique_name(value, existing)
    if suggested != value:
        raise ValueError(f'A name "{value}" already exists. Use "{suggested}" or another name.')
    return value


def readable_name(value: str, default: str = "Specification") -> str:
    """Provide a readable fallback; opaque machine identities are never labels."""
    if not value or re.search(r"[0-9a-f]{24,}", value, re.I):
        return default
    return " ".join(value.replace("_", " ").replace("-", " ").split()) or default


def filename_stem(value: str, default: str = "document") -> str:
    """Portable public filenames; private identity and archive paths stay intact."""
    ascii_name = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    stem = re.sub(r"[^A-Za-z0-9]+", "-", ascii_name).strip("-")[:80].rstrip("-").lower() or default
    if stem.split(".", 1)[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        stem = f"{default}-{stem}"
    return stem


def hardware_name(value: str, existing: Iterable[str] = ()) -> str:
    """Derive a hardware name only at creation, never on a display rename."""
    # Preserve existing valid symbols supplied by callers.
    base = value if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value) else filename_stem(value, "component").replace("-", "_")
    if not base[0].isalpha() and base[0] != "_":
        base = f"component_{base}"
    occupied = set(existing)
    candidate, number = base, 2
    while candidate in occupied:
        candidate = f"{base}_{number}"
        number += 1
    return candidate


def entity_name(entity: Any) -> str:
    return getattr(entity, "display_name", "") or readable_name(entity.vlnv.split(":")[2], "Entity")


def document_name(revision: SpecRevision) -> str:
    return revision.narrative.title or "Specification"


def reference_name(revision: SpecRevision, ref: EntityRef) -> str:
    entity = revision.resolve(ref)
    if hasattr(entity, "vlnv"):
        return entity_name(entity)
    if hasattr(entity, "text"):
        return (entity.text.strip().splitlines() or ["Note"])[0][:200] or "Note"
    if hasattr(entity, "asset_id"):
        for block in _blocks(revision.narrative.blocks):
            if block.asset_id == entity.asset_id:
                return block.caption or block.alt_text or "Image"
        return "Image"
    return "Entity"


def qualified_reference_name(revision: SpecRevision, ref: EntityRef) -> str:
    """Readable source context alongside the stable reference."""
    if ref.entity_kind == "narrative_block":
        def find(blocks: Iterable[Any], parents: tuple[str, ...]) -> tuple[str, ...] | None:
            for block in blocks:
                names = (*parents, (block.text.strip().splitlines() or ["Section"])[0]) if block.type == "section" else parents
                if block.block_id == ref.entity_id:
                    return names or (reference_name(revision, ref),)
                result = find(block.children, names)
                if result:
                    return result
            return None
        return " › ".join((document_name(revision), *(find(revision.narrative.blocks, ()) or ("Section",))))
    return f"{document_name(revision)} › {reference_name(revision, ref)}"


def select_entity(revision: SpecRevision, selection: str, kinds: tuple[str, ...] = ("component", "design")) -> Any:
    """Resolve a readable name in one exact package; retain technical selectors."""
    entities = [item for item in (*revision.components, *revision.designs, *revision.bus_definitions, *revision.abstraction_definitions) if item.ref.entity_kind in kinds]
    exact = [item for item in entities if selection in (item.ref.entity_id, item.vlnv)]
    named = [item for item in entities if name_key(entity_name(item)) == name_key(selection)]
    matches = list({item.ref.entity_id: item for item in (*exact, *named)}.values())
    if len(matches) != 1:
        choices = ", ".join(f'"{entity_name(item)}" ({item.ref.entity_kind})' for item in entities)
        raise ValueError(f'Unknown or ambiguous target "{selection}". Choose: {choices or "no available targets"}.')
    return matches[0]


def select_reference(revision: SpecRevision, selection: str, kind: str | None = None) -> EntityRef:
    """Resolve an entity or authored heading inside one selected package."""
    from spec2gds.agent_spec.spec_format.models import EntityRef
    refs = [entity.ref for entity in (*revision.components, *revision.designs,
            *revision.bus_definitions, *revision.abstraction_definitions)]
    refs.extend(EntityRef(document_id=revision.document_id, entity_kind="narrative_block", entity_id=block.block_id)
                for block in _blocks(revision.narrative.blocks) if block.type == "section")
    refs = [ref for ref in refs if kind is None or ref.entity_kind == kind]
    wanted = name_key(selection)
    matches = []
    for ref in refs:
        qualified = qualified_reference_name(revision, ref)
        names = (reference_name(revision, ref), qualified, qualified.split(" › ", 1)[-1])
        if wanted in {name_key(name) for name in names}:
            matches.append(ref)
    if len(matches) != 1:
        choices = ", ".join(f'"{qualified_reference_name(revision, ref)}" ({ref.entity_kind})' for ref in refs)
        raise ValueError(f'Unknown or ambiguous target "{selection}". Choose: {choices or "no available targets"}.')
    return matches[0]


def presentation_text(revision: SpecRevision, value: str) -> str:
    """Resolve known references in human summaries while retaining raw payloads."""
    replacements = {revision.document_id: document_name(revision),
                    revision.source_revision_hash: "source revision"}
    for entity in (*revision.components, *revision.designs, *revision.bus_definitions,
                   *revision.abstraction_definitions):
        replacements[entity.vlnv] = entity_name(entity)
        replacements[entity.ref.entity_id] = entity_name(entity)
    for section in revision.entity_sections:
        label = f"{reference_name(revision, section.owner)} › {section.title}"
        replacements[section.source_path] = label
        replacements[section.section_id] = label
    for key in sorted(replacements, key=len, reverse=True):
        value = re.sub(r"(?<!\w)" + re.escape(key) + r"(?!\w)",
                       lambda _match: replacements[key], value)
    return value


def generated_path(revision: SpecRevision, target: EntityRef, family: str) -> str:
    """Readable project paths with package-local slug collision disambiguation."""
    entities = (*revision.components, *revision.designs)
    used: set[str] = set()
    selected = "entity"
    for entity in entities:
        stem = filename_stem(entity_name(entity), "entity")
        candidate, number = stem, 2
        while candidate in used:
            candidate = f"{stem}-{number}"
            number += 1
        used.add(candidate)
        if entity.ref == target:
            selected = candidate
    return f"{family}/{filename_stem(document_name(revision))}/{selected}"


def _blocks(blocks: Iterable[Any]) -> Iterable[Any]:
    for block in blocks:
        yield block
        yield from _blocks(block.children)


def normalize_package_names(package: SpecPackage, title: str | None = None) -> bool:
    """Normalize admitted source metadata in place, retaining stable references.

    The caller owns validated persistence. Reads of immutable revisions do not
    normalize or write, and archived historical snapshots remain unchanged.
    """
    from lxml import etree

    from spec2gds.agent_spec.spec_format.source_edits import set_entity_metadata

    changed = False
    desired = clean_name(title or package.narrative.title or readable_name(Path(getattr(package, "path", None) or "Specification").stem))
    if desired != package.narrative.title:
        package.narrative = package.narrative.model_copy(update={"title": desired})
        changed = True
    occupied: list[str] = []
    for entry in list(package.manifest.documents):
        root = ipxact.parse_xml(package.files[entry.path])
        def text(field: str) -> str:
            return "".join(root.xpath(f"./*[local-name()='{field}']/text()"))
        display = unique_name(text("displayName") or readable_name(entry.vlnv.split(":")[2], "Entity"), occupied)
        occupied.append(display)
        if text("displayName") != display:
            set_entity_metadata(root, display_name=display, short_description=text("shortDescription") or None, description=text("description") or None)
            package.add_document(entry.kind, etree.tostring(root, encoding="UTF-8", xml_declaration=True))
            changed = True
    def normalize_blocks(blocks: list[Any]) -> list[Any]:
        nonlocal changed
        names: list[str] = []
        result = []
        for block in blocks:
            updates: dict[str, Any] = {"children": normalize_blocks(block.children)}
            if block.type == "section":
                name = unique_name(block.text or "Section", names)
                names.append(name)
                if name != block.text:
                    updates["text"] = name
                    changed = True
            result.append(block.model_copy(update=updates))
        return result
    blocks = normalize_blocks(package.narrative.blocks)
    if changed:
        package.narrative = package.narrative.model_copy(update={"blocks": blocks})
    return changed


def validate_package_names(package: SpecPackage) -> None:
    """Reject naming conflicts at the transaction boundary, not in renderers."""
    occupied: list[str] = []
    for entry in package.manifest.documents:
        root = ipxact.parse_xml(package.files[entry.path])
        display = "".join(root.xpath("./*[local-name()='displayName']/text()")) or readable_name(entry.vlnv.split(":")[2], "Entity")
        occupied.append(require_unique_name(display, occupied))
    def validate_blocks(blocks: list[Any]) -> None:
        names: list[str] = []
        for block in blocks:
            if block.type == "section":
                names.append(require_unique_name(block.text, names))
            validate_blocks(block.children)
    validate_blocks(package.narrative.blocks)
