"""Private Component-to-Design creation, committed by one Spec transaction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .ir import SpecRevision
from .models import EntityRef, new_entity_id
from .naming import entity_name, unique_name
from .transactions import (
    CreateHardware,
    DeleteSection,
    SetInternalDesign,
    SetSectionUsage,
    SpecEditTransaction,
)


@dataclass(frozen=True)
class InternalDesignDraft:
    component: EntityRef
    design: EntityRef
    name: str
    sv_sections: tuple[str, ...]

    @classmethod
    def prepare(cls, revision: SpecRevision, component: EntityRef) -> "InternalDesignDraft":
        entity = revision.resolve(component)
        if component.entity_kind != "component" or revision.internal_design(component) is not None:
            raise ValueError("Select a Component without an internal Design.")
        name = unique_name(
            f"{entity_name(entity)[:175]} internal Design",
            (entity_name(item) for item in (*revision.components, *revision.designs)),
        )
        return cls(
            component,
            EntityRef(
                document_id=revision.document_id,
                entity_kind="design",
                entity_id=new_entity_id("design"),
            ),
            name,
            tuple(
                item.section_id
                for item in revision.entity_sections_for(component, "sv")
                if item.usage == "implementation"
            ),
        )

    def creation_operations(self) -> tuple:
        return (
            CreateHardware("design", self.name, self.design.entity_id, entry_design=False),
            SetInternalDesign(self.component, self.design),
        )

    def stage(self, revision: SpecRevision) -> SpecRevision:
        if revision.internal_design(self.component) is not None:
            raise ValueError(
                "The Component already has an internal Design. Reopen its latest source."
            )
        result = SpecEditTransaction(
            revision.source_revision_hash, self.creation_operations(), "authoring"
        ).apply(revision)
        if result.revision is None:
            raise ValueError(" · ".join(result.diagnostics))
        return result.revision

    def sv_operations(self, disposition: Literal["retain_reference", "remove"] | None) -> tuple:
        if self.sv_sections and disposition is None:
            raise ValueError("Choose Retain SV or Remove SV before saving the internal Design.")
        if disposition == "remove":
            return tuple(
                DeleteSection(self.component, "sv", identity) for identity in self.sv_sections
            )
        return tuple(
            SetSectionUsage(self.component, identity, "reference") for identity in self.sv_sections
        )
