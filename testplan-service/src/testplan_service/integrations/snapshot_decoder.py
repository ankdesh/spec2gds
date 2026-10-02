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
from spec2gds.agent_spec.spec_format.naming import document_name, entity_name
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
                name=entity_name(comp),
                qualified_name=f"{document_name(revision)} › {entity_name(comp)}",
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
                name=entity_name(des),
                qualified_name=f"{document_name(revision)} › {entity_name(des)}",
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
                name=entity_name(comp) if comp else "Component",
                qualified_name=f"{document_name(revision)} › {entity_name(comp) if comp else 'Component'}",
                kind="component",
                component_ref=target_ref_dict,
                component_name=entity_name(comp) if comp else "Component",
                path=entity_name(comp) if comp else "Component",
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
                name=entity_name(des) if des else "Design",
                qualified_name=f"{document_name(revision)} › {entity_name(des) if des else 'Design'}",
                kind="design",
                path=entity_name(des) if des else "Design",
                instance_chain=[target.entity_id],
            )
        )
        inst_meta: dict[tuple[str, str], dict[str, str]] = {}
        if hasattr(snapshot, "source_package") and snapshot.source_package:
            try:
                from lxml import etree

                from spec2gds.agent_spec.spec_format.archive import SpecPackage
                pkg = SpecPackage.from_bytes(snapshot.source_package)
                for entry in pkg.manifest.documents:
                    if entry.kind == "design":
                        root_elem = etree.fromstring(pkg.files[entry.path])
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
                                inst_meta[(entry.entity_id, iname)] = {"stable_id": stable_id, "display_name": dname}
            except Exception:
                pass

        def append_instances(design, names, chain, stable_chain, ancestors):
            if design.ref.entity_id in ancestors:
                diagnostics.append(f"Recursive composition at {' / '.join(names)}.")
                return
            for inst in design.instances:
                meta = inst_meta.get((design.ref.entity_id, inst.name), {})
                stable_id = meta.get("stable_id", inst.name)
                display = meta.get("display_name", inst.name)
                component = next((c for c in revision.components if c.vlnv == inst.component_vlnv), None)
                path = "/".join((*names, display))
                occurrence_chain = [*chain, inst.name]
                identity_chain = [*stable_chain, stable_id]
                # Keep legacy top-level references; qualify deeper occurrences so
                # repeated instances of a composite never collapse into one scope.
                occurrence_id = stable_id if len(identity_chain) == 1 else sha256_digest(identity_chain)
                occurrences.append(OccurrenceSummary(
                    occurrence_id=occurrence_id, name=display, kind="component",
                    qualified_name=f"{document_name(revision)} › {path}", path=path,
                    instance_chain=occurrence_chain,
                    component_ref=component.ref.model_dump(mode="json") if component else None,
                    component_name=entity_name(component) if component else "Unavailable component",
                    ports=[{"name": p.name, "direction": p.direction, "width": p.width or 1}
                           for p in component.ports] if component else [],
                ))
                internal = revision.internal_design(component) if component else None
                if internal:
                    append_instances(internal, [*names, display], occurrence_chain,
                                     identity_chain, {*ancestors, design.ref.entity_id})

        if des:
            append_instances(des, [entity_name(des)], [target.entity_id], [], set())

    # 4. Project Narrative Sections
    if revision._narrative_json:
        try:
            narrative = NarrativeDocument.model_validate_json(revision._narrative_json)
            def sections(blocks, parents=()):
                for block in blocks:
                    heading = (block.text or "Section").splitlines()[0][:200]
                    qualified = (*parents, heading) if block.type == "section" else parents
                    if not parents or block.type == "section":
                        yield block, qualified
                    yield from sections(block.children, qualified or parents)
            for block, headings in sections(narrative.blocks):
                text = block.text or ""
                # Also include children text if present
                if block.children:
                    child_texts = [c.text for c in block.children if c.text]
                    if child_texts:
                        text = f"{text}\n" + "\n".join(child_texts) if text else "\n".join(child_texts)
                digest = sha256_digest(text)
                title = block.text.splitlines()[0][:200] if block.text else "Section"
                ref = target_ref_dict or {
                    "document_id": manifest.source.document_id,
                    "entity_kind": "document",
                    "entity_id": manifest.source.document_id,
                }
                source_sections.append(
                    SourceSectionSummary(
                        section_id=block.block_id,
                        title=title,
                        qualified_name=" › ".join((document_name(revision), *headings)) or title,
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
        source_name=document_name(revision),
        source_revision_hash=manifest.source.source_revision_hash,
        root_ref=target_ref_dict,
        entities=entities,
        occurrences=occurrences,
        source_sections=source_sections,
        diagnostics=diagnostics,
    )
