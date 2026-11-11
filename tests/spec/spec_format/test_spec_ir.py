"""V1.2 semantic graph and atomic transaction acceptance tests."""

import tempfile
from pathlib import Path

from spec2gds.spec.spec_format.ir import (
    ConnectionIR,
    InstanceIR,
    PortEndpointIR,
    SpecRevision,
)
from spec2gds.spec.spec_format.models import EntityRef
from spec2gds.spec.spec_format.testing import build_test_package
from spec2gds.spec.spec_format.transactions import (
    AddComponentPort,
    ClearInternalDesign,
    CreateHardware,
    ReorderInstances,
    SetDocumentTitle,
    SetHardwareMetadata,
    SetInternalDesign,
    SetNarrativeLinks,
    SpecEditTransaction,
    StructuredPortInput,
    TransactionalPortInput,
    UpdateComponentPort,
    UpsertConnection,
    UpsertDocumentXml,
    UpsertInstance,
    WirePortInput,
)


def _revision() -> SpecRevision:
    return SpecRevision.from_package(build_test_package())


def test_queries_resolve_stable_entities_hierarchy_and_dependencies() -> None:
    revision = _revision()
    leaf = revision.by_vlnv("component", "spec2gds.example:demo:leaf:1.0")
    subsystem = revision.by_vlnv("component", "spec2gds.example:demo:subsystem:1.0")
    top_a = revision.by_vlnv("design", "spec2gds.example:demo:top_a:1.0")

    assert revision.resolve(leaf.ref) == leaf
    assert [design.ref.entity_id for design in revision.entry_designs()] == ["design_top_a", "design_top_b"]
    assert revision.internal_design(subsystem).ref.entity_id == "design_subsystem_internal"
    assert revision.document_by_vlnv("design", top_a.vlnv) == top_a
    assert [instance.name for instance in revision.instances(top_a)] == ["subsystem0"]
    assert [interface.name for interface in revision.interfaces(leaf)] == ["link"]
    assert revision.connections(top_a) == ()
    assert {reference.entity_id for reference in revision.dependency_closure(leaf)} == {
        "component_leaf",
        "bus_demo_link",
        "abstraction_demo_link_wire",
    }
    assert {reference.entity_id for reference in revision.dependency_closure(top_a)} == {
        "component_leaf",
        "component_sink",
        "component_subsystem",
        "bus_demo_link",
        "abstraction_demo_link_wire",
        "design_subsystem_internal",
        "design_top_a",
    }
    assert [block.block_id for block in revision.narrative_blocks_for(top_a.ref)] == ["top_a_link"]


def test_public_manifest_and_narrative_copies_cannot_mutate_revision() -> None:
    revision = _revision()
    manifest = revision.manifest
    manifest.entry_designs.clear()
    narrative = revision.narrative
    narrative.blocks.clear()
    assert len(revision.entry_designs()) == 2
    assert revision.narrative.blocks


def test_valid_transaction_updates_instance_connection_and_preserves_ids() -> None:
    revision = _revision()
    top_b = revision.by_vlnv("design", "spec2gds.example:demo:top_b:1.0")
    transaction = SpecEditTransaction(
        revision.source_revision_hash,
        (
            UpsertInstance(top_b.ref, InstanceIR("leaf2", "spec2gds.example:demo:leaf:1.0")),
            UpsertConnection(
                top_b.ref,
                ConnectionIR(
                    name="irq_link",
                    kind="ad_hoc",
                    port_endpoints=(PortEndpointIR("leaf1", "irq"), PortEndpointIR("leaf2", "irq_in")),
                ),
            ),
            ReorderInstances(top_b.ref, ("leaf2", "leaf1")),
        ),
    )
    result = transaction.apply(revision)
    assert result.succeeded, result.diagnostics
    updated = result.revision
    assert updated is not None
    assert updated.source_revision_hash != revision.source_revision_hash
    updated_top_b = updated.by_vlnv("design", top_b.vlnv)
    assert updated_top_b.ref == top_b.ref
    assert [instance.name for instance in updated_top_b.instances] == ["leaf2", "leaf1"]
    assert updated_top_b.connections[0].name == "irq_link"
    assert [instance.name for instance in revision.by_vlnv("design", top_b.vlnv).instances] == ["leaf1"]


def test_invalid_transaction_rolls_back_on_missing_component_and_bad_port_connection() -> None:
    revision = _revision()
    top_b = revision.by_vlnv("design", "spec2gds.example:demo:top_b:1.0")
    missing_component = SpecEditTransaction(
        revision.source_revision_hash,
        (UpsertInstance(top_b.ref, InstanceIR("missing", "example:lib:not_embedded:1.0")),),
    ).apply(revision)
    assert not missing_component.succeeded
    assert any("missing embedded component" in diagnostic or "missing component" in diagnostic for diagnostic in missing_component.diagnostics)

    incompatible_ports = SpecEditTransaction(
        revision.source_revision_hash,
        (
            UpsertInstance(top_b.ref, InstanceIR("leaf2", "spec2gds.example:demo:leaf:1.0")),
            UpsertConnection(
                top_b.ref,
                ConnectionIR(
                    name="bad_irq_link",
                    kind="ad_hoc",
                    port_endpoints=(PortEndpointIR("leaf1", "irq"), PortEndpointIR("leaf2", "irq")),
                ),
            ),
        ),
    ).apply(revision)
    assert not incompatible_ports.succeeded
    assert any("incompatible port directions" in diagnostic for diagnostic in incompatible_ports.diagnostics)
    assert [instance.name for instance in revision.by_vlnv("design", top_b.vlnv).instances] == ["leaf1"]


def test_stale_base_cycle_and_broken_narrative_links_are_rejected() -> None:
    revision = _revision()
    leaf = revision.by_vlnv("component", "spec2gds.example:demo:leaf:1.0")
    internal = revision.by_vlnv("design", "spec2gds.example:demo:subsystem_internal:1.0")
    stale = SpecEditTransaction("sha256:" + "0" * 64, ()).apply(revision)
    assert not stale.succeeded
    assert "Stale base revision" in stale.diagnostics[0]

    subsystem = revision.by_vlnv("component", "spec2gds.example:demo:subsystem:1.0")
    cycle = SpecEditTransaction(
        revision.source_revision_hash,
        (ClearInternalDesign(subsystem.ref), SetInternalDesign(leaf.ref, internal.ref)),
    ).apply(revision)
    assert not cycle.succeeded
    assert any("cycle" in diagnostic for diagnostic in cycle.diagnostics)

    broken_link = SpecEditTransaction(
        revision.source_revision_hash,
        (
            SetNarrativeLinks(
                "top_a_link",
                (EntityRef(document_id=revision.document_id, entity_id="component_missing", entity_kind="component"),),
            ),
        ),
    ).apply(revision)
    assert not broken_link.succeeded
    assert any("unknown source entity" in diagnostic for diagnostic in broken_link.diagnostics)


def test_save_reopen_preserves_semantic_identity_and_source_hash() -> None:
    revision = _revision()
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "revision.spec"
        revision.save(str(path))
        reopened = SpecRevision.load(str(path))
    assert reopened.source_revision_hash == revision.source_revision_hash
    assert [component.ref.entity_id for component in reopened.components] == [component.ref.entity_id for component in revision.components]
    assert [design.ref.entity_id for design in reopened.entry_designs()] == [design.ref.entity_id for design in revision.entry_designs()]


def test_direct_editor_transactions_create_entities_and_preserve_source_order() -> None:
    revision = _revision()
    original_ids = [item.entity_id for item in revision.manifest.documents]
    leaf = revision.by_vlnv("component", "spec2gds.example:demo:leaf:1.0")
    edited = SpecEditTransaction(
        revision.source_revision_hash,
        (
            SetDocumentTitle("Timing Subsystem"),
            SetHardwareMetadata(leaf.ref, "Leaf block", "Produces data", "Updated directly."),
            CreateHardware("component", "timer"),
            CreateHardware("design", "timer_top"),
        ),
    ).apply(revision)
    assert edited.succeeded, edited.diagnostics
    updated = edited.revision
    assert updated is not None
    assert updated.document_id == revision.document_id
    assert updated.narrative.title == "Timing Subsystem"
    assert [item.entity_id for item in updated.manifest.documents[:len(original_ids)]] == original_ids
    assert updated.by_vlnv("component", "spec2gds.local:work:timer:1.0")
    created_design = updated.by_vlnv("design", "spec2gds.local:work:timer_top:1.0")
    assert created_design.ref in [item.ref for item in updated.entry_designs()]

    empty_title = SpecEditTransaction(
        updated.source_revision_hash,
        (SetDocumentTitle("   "),),
    ).apply(updated)
    assert not empty_title.succeeded
    assert "name is required" in empty_title.diagnostics[0]

    duplicate = SpecEditTransaction(
        updated.source_revision_hash,
        (CreateHardware("component", "timer"),),
    ).apply(updated)
    assert not duplicate.succeeded
    assert "already exists" in duplicate.diagnostics[0]

    unsupported = SpecEditTransaction(
        updated.source_revision_hash,
        (SetHardwareMetadata(updated.bus_definitions[0].ref, "Bus", None, None),),
    ).apply(updated)
    assert not unsupported.succeeded
    assert "only components and designs" in unsupported.diagnostics[0]

    cleared = SpecEditTransaction(
        updated.source_revision_hash,
        (SetHardwareMetadata(leaf.ref, None, None, None),),
    ).apply(updated)
    assert cleared.succeeded, cleared.diagnostics
    cleared_package = cleared.revision.to_package() if cleared.revision else None
    assert cleared_package is not None
    leaf_entry = next(item for item in cleared_package.manifest.documents if item.entity_id == leaf.ref.entity_id)
    assert b"displayName" not in cleared_package.files[leaf_entry.path]
    assert b"shortDescription" not in cleared_package.files[leaf_entry.path]
    assert b"<ipxact:description>" not in cleared_package.files[leaf_entry.path]


def test_direct_editor_adds_and_updates_profiled_ports_but_blocks_composites() -> None:
    revision = _revision()
    sink = revision.by_vlnv("component", "spec2gds.example:demo:sink:1.0")
    added = SpecEditTransaction(
        revision.source_revision_hash,
        (AddComponentPort(sink.ref, "status", WirePortInput(
            direction="out",
            range="7:0",
            description="Status vector",
        )),),
    ).apply(revision)
    assert added.succeeded, added.diagnostics
    updated = added.revision
    assert updated is not None
    port = next(item for item in updated.by_vlnv("component", sink.vlnv).ports if item.name == "status")
    assert (port.style, port.direction, port.width) == ("wire", "out", "[7:0]")

    changed = SpecEditTransaction(
        updated.source_revision_hash,
        (UpdateComponentPort(sink.ref, "status", WirePortInput(
            direction="inout",
            range=None,
            description="Scalar status",
        )),),
    ).apply(updated)
    assert changed.succeeded, changed.diagnostics
    changed_port = next(
        item for item in changed.revision.by_vlnv("component", sink.vlnv).ports
        if item.name == "status"
    ) if changed.revision else None
    assert changed_port is not None
    assert (changed_port.direction, changed_port.width) == ("inout", 1)

    bad_bounds = SpecEditTransaction(
        updated.source_revision_hash,
        (AddComponentPort(sink.ref, "partial", WirePortInput(direction="in", range="3:")),),
    ).apply(updated)
    assert not bad_bounds.succeeded
    assert "both sides" in bad_bounds.diagnostics[0]

    bad_name = SpecEditTransaction(
        updated.source_revision_hash,
        (AddComponentPort(sink.ref, "bad name", WirePortInput(direction="in")),),
    ).apply(updated)
    assert not bad_name.succeeded
    assert "XML-compatible identifier" in bad_name.diagnostics[0]

    duplicate = SpecEditTransaction(
        updated.source_revision_hash,
        (AddComponentPort(sink.ref, "payload_in", WirePortInput(direction="in")),),
    ).apply(updated)
    assert not duplicate.succeeded
    assert "already has a port" in duplicate.diagnostics[0]

    missing = SpecEditTransaction(
        updated.source_revision_hash,
        (UpdateComponentPort(sink.ref, "missing", WirePortInput(direction="in")),),
    ).apply(updated)
    assert not missing.succeeded
    assert "Unknown component port" in missing.diagnostics[0]

    subsystem = revision.by_vlnv("component", "spec2gds.example:demo:subsystem:1.0")
    composite = SpecEditTransaction(
        revision.source_revision_hash,
        (AddComponentPort(subsystem.ref, "blocked", WirePortInput(direction="in")),),
    ).apply(revision)
    assert not composite.succeeded
    assert "internal designs" in composite.diagnostics[0]

    families = SpecEditTransaction(
        updated.source_revision_hash,
        (
            AddComponentPort(sink.ref, "service", TransactionalPortInput(
                initiative="requires",
                kind="custom",
                custom_kind="demo_rpc",
                bus_width="64",
                description="Submits work.",
            )),
            AddComponentPort(sink.ref, "response", StructuredPortInput(
                direction="out",
                description="Opaque packed result.",
            )),
            AddComponentPort(sink.ref, "indexed", WirePortInput(direction="in", range="0:0")),
        ),
    ).apply(updated)
    assert families.succeeded, families.diagnostics
    family_revision = families.revision
    assert family_revision is not None
    family_component = family_revision.by_vlnv("component", sink.vlnv)
    by_name = {port.name: port for port in family_component.ports}
    assert (by_name["service"].style, by_name["service"].initiative, by_name["service"].bus_width) == (
        "transactional", "requires", "64",
    )
    assert (
        by_name["service"].description,
        by_name["service"].kind,
        by_name["service"].custom_kind,
    ) == ("Submits work.", "custom", "demo_rpc")
    assert (by_name["response"].style, by_name["response"].direction) == ("structured", "out")
    assert by_name["response"].packed is True
    assert by_name["indexed"].width == "[0:0]"
    assert by_name["indexed"].range == "0"

    package = family_revision.to_package()
    sink_entry = next(item for item in package.manifest.documents if item.entity_id == sink.ref.entity_id)
    sink_xml = package.files[sink_entry.path]
    assert b'<ipxact:kind custom="demo_rpc">custom</ipxact:kind>' in sink_xml
    assert b'<ipxact:structured packed="true">' in sink_xml
    assert b"<ipxact:typeName>response_struct_t</ipxact:typeName>" in sink_xml

    family_change = SpecEditTransaction(
        family_revision.source_revision_hash,
        (UpdateComponentPort(sink.ref, "status", StructuredPortInput(direction="out")),),
    ).apply(family_revision)
    assert not family_change.succeeded
    assert "family cannot be changed" in family_change.diagnostics[0]
