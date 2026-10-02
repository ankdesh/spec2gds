"""Read-only two-level Activity access to one immutable SpecRevision."""

from __future__ import annotations

import typing
from collections.abc import Callable, Iterator, Sequence

from spec2gds.agent_spec.spec_format.ir import (
    AbstractionDefinitionIR,
    BusDefinitionIR,
    ComponentIR,
    DesignIR,
    SemanticEntity,
    SpecRevision,
)
from spec2gds.agent_spec.spec_format.models import (
    AssetEntry,
    EntityKind,
    EntityRef,
    NarrativeBlock,
    NarrativeDocument,
    SpecManifest,
    StrictModel,
)
from spec2gds.agent_spec.spec_format.sections import EntitySectionIR


class EntitySummary(StrictModel):
    """Stable high-level identity shared by every supported source entity."""

    ref: EntityRef
    name: str
    display_name: str = ""
    vlnv: str = ""


class TextBlockView(StrictModel):
    """Generic, immutable narrative block representation for Activities."""

    ref: EntityRef
    block_type: str
    text: str
    entity_refs: tuple[EntityRef, ...] = ()


ItemT = typing.TypeVar("ItemT")


class Query(Sequence[ItemT], typing.Generic[ItemT]):
    """Small deterministic query result supporting iteration and predicates."""

    def __init__(self, values: typing.Iterable[ItemT]) -> None:
        self._values = tuple(values)

    def __iter__(self) -> Iterator[ItemT]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __getitem__(self, index: int | slice) -> ItemT | tuple[ItemT, ...]:
        return self._values[index]

    def filter(self, predicate: Callable[[ItemT], bool]) -> "Query[ItemT]":
        """Return values accepted by one in-process Python predicate."""
        return Query(value for value in self._values if predicate(value))

    def all(self) -> tuple[ItemT, ...]:
        """Materialize the deterministic result as an immutable tuple."""
        return self._values

    def first(self) -> ItemT | None:
        """Return the first result or ``None`` when the query is empty."""
        return self._values[0] if self._values else None

    def one(self) -> ItemT:
        """Require exactly one result."""
        if len(self._values) != 1:
            raise ValueError(f"Expected exactly one result, found {len(self._values)}.")
        return self._values[0]


class EntityQuery(Query[EntitySummary]):
    """High-level entity query with common identity filters."""

    def where(
        self,
        *,
        kind: EntityKind | None = None,
        entity_id: str | None = None,
        name: str | None = None,
        vlnv: str | None = None,
    ) -> "EntityQuery":
        """Filter without requiring callers to know concrete IR classes."""
        return EntityQuery(
            value
            for value in self
            if (kind is None or value.ref.entity_kind == kind)
            and (entity_id is None or value.ref.entity_id == entity_id)
            and (name is None or value.name == name)
            and (vlnv is None or value.vlnv == vlnv)
        )


class TextQuery(Query[TextBlockView]):
    """Narrative query with deterministic plain-text rendering."""

    def plain_text(self) -> str:
        """Join non-empty block text in document order."""
        return "\n\n".join(value.text for value in self if value.text)


class HighLevelTextApi:
    """Generic narrative selection independent of concrete block models."""

    def __init__(self, revision: SpecRevision) -> None:
        self._revision = revision

    def all(self) -> TextQuery:
        """Return every narrative block in depth-first document order."""
        return TextQuery(_text_view(self._revision.document_id, block) for block in _blocks(self._revision.narrative.blocks))

    def linked_to(self, reference: EntityRef) -> TextQuery:
        """Return blocks that directly link to a stable source entity."""
        return TextQuery(
            _text_view(self._revision.document_id, block)
            for block in self._revision.narrative_blocks_for(reference)
        )


class HighLevelSpecApi:
    """Stable generic selection, relationship, and narrative API."""

    def __init__(self, revision: SpecRevision, target: EntityRef | None) -> None:
        self._revision = revision
        self.target = target
        self.text = HighLevelTextApi(revision)

    @property
    def document(self) -> dict[str, str]:
        """Return compact immutable-by-copy document identity metadata."""
        return {
            "document_id": self._revision.document_id,
            "title": self._revision.narrative.title or "Specification",
            "source_revision_hash": self._revision.source_revision_hash,
        }

    def entities(self, kind: EntityKind | None = None) -> EntityQuery:
        """Iterate source entities in manifest and narrative document order."""
        summaries: list[EntitySummary] = []
        for entry in self._revision.manifest.documents:
            reference = EntityRef(
                document_id=self._revision.document_id,
                entity_id=entry.entity_id,
                entity_kind=entry.kind,
            )
            summaries.append(_summary(self._revision.resolve(reference)))
        summaries.extend(
            _summary(block, self._revision.document_id)
            for block in _blocks(self._revision.narrative.blocks)
        )
        summaries.extend(_summary(asset, self._revision.document_id) for asset in self._revision.assets)
        result = EntityQuery(summaries)
        return result.where(kind=kind) if kind is not None else result

    def project_path(self, reference: EntityRef, family: str) -> str:
        """Readable public generation path; ownership remains reference-based."""
        from spec2gds.agent_spec.spec_format.naming import generated_path
        self._revision.resolve(reference)
        return generated_path(self._revision, reference, family)

    def entity(self, reference: EntityRef) -> EntitySummary:
        """Resolve one entity to its generic high-level identity."""
        return _summary(self._revision.resolve(reference), self._revision.document_id)

    def related(
        self,
        reference: EntityRef,
        relation: typing.Literal["dependencies", "usages"],
    ) -> EntityQuery:
        """Traverse a supported semantic relationship from one entity."""
        self._revision.resolve(reference)
        refs = (
            _dependencies(self._revision, reference)
            if relation == "dependencies"
            else _usages(self._revision, reference)
        )
        return EntityQuery(self.entity(item) for item in refs)


class LowLevelSpecApi:
    """Concrete typed IR access without package mutation or raw XML."""

    def __init__(self, revision: SpecRevision) -> None:
        self._revision = revision

    @property
    def manifest(self) -> SpecManifest:
        """Expose immutable package identity and document-entry metadata."""
        return self._revision.manifest

    @property
    def narrative(self) -> NarrativeDocument:
        """Expose the immutable typed narrative document."""
        return self._revision.narrative

    @property
    def entity_sections(self) -> tuple[EntitySectionIR, ...]:
        """Expose all indexed extension sections in deterministic order."""
        return self._revision.entity_sections

    def entity_sections_for(
        self, reference: EntityRef, section_type: str | None = None
    ) -> tuple[EntitySectionIR, ...]:
        """Select extension sections owned by an entity and optional type."""
        return self._revision.entity_sections_for(reference, section_type)

    @property
    def components(self) -> tuple[ComponentIR, ...]:
        """Expose concrete component IR values in manifest order."""
        return self._revision.components

    @property
    def designs(self) -> tuple[DesignIR, ...]:
        """Expose concrete design IR values in manifest order."""
        return self._revision.designs

    @property
    def bus_definitions(self) -> tuple[BusDefinitionIR, ...]:
        """Expose concrete bus-definition IR values in manifest order."""
        return self._revision.bus_definitions

    @property
    def abstraction_definitions(self) -> tuple[AbstractionDefinitionIR, ...]:
        """Expose concrete abstraction-definition IR values in manifest order."""
        return self._revision.abstraction_definitions

    def resolve(self, reference: EntityRef) -> SemanticEntity:
        """Resolve a stable reference to its concrete immutable IR value."""
        return self._revision.resolve(reference)

    def entry_designs(self) -> tuple[DesignIR, ...]:
        """Return the designs declared as package entry points."""
        return self._revision.entry_designs()

    def internal_design(self, reference: ComponentIR | EntityRef) -> DesignIR | None:
        """Return the design composing a component, when one is assigned."""
        return self._revision.internal_design(reference)

    def connections(self, reference: DesignIR | EntityRef) -> tuple[typing.Any, ...]:
        """Return all typed connections owned by one design."""
        return self._revision.connections(reference)

    def dependencies(self, reference: ComponentIR | DesignIR | EntityRef) -> tuple[EntityRef, ...]:
        """Return the transitive component/design dependency closure."""
        return self._revision.dependency_closure(reference)

    def narrative_blocks_for(self, reference: EntityRef) -> tuple[NarrativeBlock, ...]:
        """Return narrative blocks that directly link to an entity."""
        return self._revision.narrative_blocks_for(reference)


class SpecAccess:
    """Explicit root exposing the high- and low-level read-only APIs."""

    def __init__(self, revision: SpecRevision, target: EntityRef | None = None) -> None:
        if target is not None:
            revision.resolve(target)
        self.high = HighLevelSpecApi(revision, target)
        self.low = LowLevelSpecApi(revision)


def _blocks(blocks: list[NarrativeBlock]) -> Iterator[NarrativeBlock]:
    for block in blocks:
        yield block
        yield from _blocks(block.children)


def _block_text(block: NarrativeBlock) -> str:
    pieces = [block.text, "".join(inline.text for inline in block.inlines)]
    pieces.extend(" | ".join(row) for row in block.rows)
    pieces.extend((block.caption, block.alt_text))
    return "\n".join(piece for piece in pieces if piece)


def _block_refs(block: NarrativeBlock) -> tuple[EntityRef, ...]:
    refs = [*block.entity_refs, *(item.entity_ref for item in block.inlines if item.entity_ref)]
    return tuple(refs)


def _text_view(document_id: str, block: NarrativeBlock) -> TextBlockView:
    return TextBlockView(
        ref=EntityRef(document_id=document_id, entity_kind="narrative_block", entity_id=block.block_id),
        block_type=block.type,
        text=_block_text(block),
        entity_refs=_block_refs(block),
    )


def _summary(entity: typing.Any, document_id: str | None = None) -> EntitySummary:
    from spec2gds.agent_spec.spec_format.naming import entity_name, readable_name
    if isinstance(entity, (ComponentIR, DesignIR, BusDefinitionIR, AbstractionDefinitionIR)):
        name = entity.vlnv.split(":")[2]
        return EntitySummary(ref=entity.ref, name=name, display_name=entity_name(entity), vlnv=entity.vlnv)
    if isinstance(entity, NarrativeBlock):
        assert document_id is not None
        return EntitySummary(
            ref=EntityRef(document_id=document_id, entity_kind="narrative_block", entity_id=entity.block_id),
            name=entity.block_id,
            display_name=(entity.text.strip().splitlines() or ["Note"])[0][:200] or "Note",
        )
    if isinstance(entity, AssetEntry):
        assert document_id is not None
        return EntitySummary(
            ref=EntityRef(document_id=document_id, entity_kind="asset", entity_id=entity.asset_id),
            name=entity.asset_id,
            display_name=readable_name(entity.asset_id, "Image"),
        )
    raise TypeError(f"Unsupported semantic entity: {type(entity).__name__}")


def _dependencies(revision: SpecRevision, reference: EntityRef) -> tuple[EntityRef, ...]:
    if reference.entity_kind in {"component", "design"}:
        return revision.dependency_closure(reference)
    return (reference,)


def _usages(revision: SpecRevision, reference: EntityRef) -> tuple[EntityRef, ...]:
    matches: dict[tuple[str, str], EntityRef] = {}

    def add(candidate: EntityRef) -> None:
        matches[(candidate.entity_kind, candidate.entity_id)] = candidate

    entity = revision.resolve(reference)
    if isinstance(entity, ComponentIR):
        for design in revision.designs:
            if any(instance.component_vlnv == entity.vlnv for instance in design.instances):
                add(design.ref)
    elif isinstance(entity, DesignIR):
        for composition in revision.manifest.component_compositions:
            if composition.internal_design == entity.ref:
                add(composition.component)
    elif isinstance(entity, BusDefinitionIR):
        for component in revision.components:
            if any(interface.bus_vlnv == entity.vlnv for interface in component.interfaces):
                add(component.ref)
    elif isinstance(entity, AbstractionDefinitionIR):
        for component in revision.components:
            if any(interface.abstraction_vlnv == entity.vlnv for interface in component.interfaces):
                add(component.ref)
    for block in _blocks(revision.narrative.blocks):
        if reference in _block_refs(block) or (
            reference.entity_kind == "asset" and block.asset_id == reference.entity_id
        ):
            add(
                EntityRef(
                    document_id=revision.document_id,
                    entity_kind="narrative_block",
                    entity_id=block.block_id,
                )
            )
    return tuple(matches[key] for key in sorted(matches))
