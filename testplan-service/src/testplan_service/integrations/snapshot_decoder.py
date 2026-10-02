"""Decoder projecting spec2gds Activity Snapshot v1 into SourceSnapshotView.

Reviewer path: validate container admission and source identity before deriving
entity/occurrence views. Projection is read-only and intentionally avoids runtime
imports from the live Spec owner; imported narrative remains untrusted content.
"""

from __future__ import annotations

import json
from typing import Any

from spec2gds.agent_spec.activities import ActivitySnapshot
from spec2gds.agent_spec.spec_format.models import NarrativeDocument

from testplan_service.domain.hash import sha256_digest
from testplan_service.exceptions import SnapshotError
from testplan_service.integrations.models import (
    EntitySummary,
    OccurrenceSummary,
    SourceSectionSummary,
    SourceSnapshotView,
)


def decode_snapshot_bytes(data: bytes) -> SourceSnapshotView:
    """Decode, validate and project Activity Snapshot v1 bytes into SourceSnapshotView."""
    try:
        snapshot = ActivitySnapshot.from_bytes(data)
    except Exception as exc:
        raise SnapshotError(f"Activity Snapshot decoding failed: {exc}") from exc

    manifest = snapshot.manifest
    revision = snapshot.revision

    target_ref_dict = (
        {
            "document_id": manifest.scope.target.document_id,
            "entity_kind": manifest.scope.target.entity_kind,
            "entity_id": manifest.scope.target.entity_id,
        }
        if manifest.scope.target
        else None
    )

    entities: list[EntitySummary] = []
    occurrences: list[OccurrenceSummary] = []
    source_sections: list[SourceSectionSummary] = []
    diagnostics: list[str] = list(revision.diagnostics)

    # 1. Project Components
    for comp in revision.components:
        ports_list = [
            {
                "name": p.name,
                "direction": p.direction,
                "width": p.width or 1,
                "style": p.style,
            }
            for p in comp.ports
        ]
        entities.append(
            EntitySummary(
                entity_ref={
                    "document_id": comp.ref.document_id,
                    "entity_kind": comp.ref.entity_kind,
                    "entity_id": comp.ref.entity_id,
                },
                name=comp.ref.entity_id,
                kind="component",
                vlnv=comp.vlnv,
                ports=ports_list,
            )
        )

    # 2. Project Designs
    for des in revision.designs:
        entities.append(
            EntitySummary(
                entity_ref={
                    "document_id": des.ref.document_id,
                    "entity_kind": des.ref.entity_kind,
                    "entity_id": des.ref.entity_id,
                },
                name=des.ref.entity_id,
                kind="design",
                vlnv=des.vlnv,
            )
        )

    # 3. Project Occurrences based on Target Scope
    target = manifest.scope.target
    if target and target.entity_kind == "component":
        # Standalone component root
        comp = next((c for c in revision.components if c.ref.entity_id == target.entity_id), None)
        ports = [
            {"name": p.name, "direction": p.direction, "width": p.width or 1}
            for p in comp.ports
        ] if comp else []
        occurrences.append(
            OccurrenceSummary(
                occurrence_id=target.entity_id,
                name=target.entity_id,
                kind="component",
                component_ref=target_ref_dict,
                component_name=target.entity_id,
                path=target.entity_id,
                instance_chain=[target.entity_id],
                ports=ports,
            )
        )
    elif target and target.entity_kind == "design":
        # Design root + reachable instance occurrences
        des = next((d for d in revision.designs if d.ref.entity_id == target.entity_id), None)
        occurrences.append(
            OccurrenceSummary(
                occurrence_id=target.entity_id,
                name=target.entity_id,
                kind="design",
                path=target.entity_id,
                instance_chain=[target.entity_id],
            )
        )
        inst_meta: dict[str, dict[str, str]] = {}
        if hasattr(snapshot, "source_package") and snapshot.source_package:
            try:
                from lxml import etree
                from spec2gds.agent_spec.spec_format.archive import SpecPackage
                pkg = SpecPackage.from_bytes(snapshot.source_package)
                for fpath, fcontent in pkg.files.items():
                    if "designs/" in fpath:
                        root_elem = etree.fromstring(fcontent)
                        for inst_node in root_elem.xpath("./*[local-name()='componentInstances']/*[local-name()='componentInstance']"):
                            iname_node = inst_node.xpath("./*[local-name()='instanceName']")
                            iname = iname_node[0].text.strip() if iname_node and iname_node[0].text else ""
                            stable_id = (
                                inst_node.get("{http://www.w3.org/XML/1998/namespace}id")
                                or inst_node.get("id")
                                or iname
                            )
                            dname_node = inst_node.xpath("./*[local-name()='displayName']")
                            dname = dname_node[0].text.strip() if dname_node and dname_node[0].text else iname
                            if iname:
                                inst_meta[iname] = {"stable_id": stable_id, "display_name": dname}
            except Exception:
                pass

        if des:
            for inst in des.instances:
                meta = inst_meta.get(inst.name, {})
                stable_id = meta.get("stable_id", inst.name)
                display_name = meta.get("display_name", inst.name)

                # Find matching component
                c_match = next((c for c in revision.components if c.vlnv == inst.component_vlnv or c.ref.entity_id == inst.name), None)
                c_name = c_match.ref.entity_id if c_match else inst.name
                c_ref = (
                    {
                        "document_id": c_match.ref.document_id,
                        "entity_kind": c_match.ref.entity_kind,
                        "entity_id": c_match.ref.entity_id,
                    }
                    if c_match
                    else None
                )
                ports = [
                    {"name": p.name, "direction": p.direction, "width": p.width or 1}
                    for p in c_match.ports
                ] if c_match else []
                occurrences.append(
                    OccurrenceSummary(
                        occurrence_id=stable_id,
                        name=display_name,
                        kind="component",
                        component_ref=c_ref,
                        component_name=c_name,
                        path=f"{target.entity_id}/{display_name}" if display_name else f"{target.entity_id}/{inst.name}",
                        instance_chain=[target.entity_id, inst.name],
                        ports=ports,
                    )
                )

    # 4. Project Narrative Sections
    if revision._narrative_json:
        try:
            narrative = NarrativeDocument.model_validate_json(revision._narrative_json)
            for block in narrative.blocks:
                text = block.text or ""
                # Also include children text if present
                if block.children:
                    child_texts = [c.text for c in block.children if c.text]
                    if child_texts:
                        text = f"{text}\n" + "\n".join(child_texts) if text else "\n".join(child_texts)
                digest = sha256_digest(text)
                title = block.text[:100] if block.text else f"Section {block.block_id}"
                ref = target_ref_dict or {
                    "document_id": manifest.source.document_id,
                    "entity_kind": "document",
                    "entity_id": manifest.source.document_id,
                }
                source_sections.append(
                    SourceSectionSummary(
                        section_id=block.block_id,
                        title=title,
                        entity_ref=ref,
                        locator={
                            "snapshot_id": manifest.snapshot_id,
                            "entity_ref": ref,
                            "section_id": block.block_id,
                            "text_range": [0, len(text)],
                            "quoted_text": text,
                            "section_digest": digest,
                        },
                        text=text,
                        content_digest=digest,
                    )
                )
        except Exception as e:
            diagnostics.append(f"Narrative decoding warning: {e}")

    return SourceSnapshotView(
        snapshot_id=manifest.snapshot_id,
        source_document_id=manifest.source.document_id,
        source_revision_hash=manifest.source.source_revision_hash,
        root_ref=target_ref_dict,
        entities=entities,
        occurrences=occurrences,
        source_sections=source_sections,
        diagnostics=diagnostics,
    )
