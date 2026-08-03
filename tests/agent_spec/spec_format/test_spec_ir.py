"""V1.2 semantic graph and atomic transaction acceptance tests."""

from pathlib import Path
import tempfile

from spec2gds.agent_spec.spec_format.ir import (
    ConnectionIR,
    InstanceIR,
    PortEndpointIR,
    SpecRevision,
)
from spec2gds.agent_spec.spec_format.models import EntityRef
from spec2gds.agent_spec.spec_format.testing import build_test_package
from spec2gds.agent_spec.spec_format.transactions import (
    AddComponentPort,
    ClearInternalDesign,
    CreateEntity,
    ReorderInstances,
    SetInternalDesign,
    SetEntityMetadata,
    SetNarrativeEntityLinks,
    SpecEditTransaction,
    UpsertConnection,
    UpsertDocumentXml,
    UpsertInstance,
    UpdateComponentPort,
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
            SetNarrativeEntityLinks(
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
            SetEntityMetadata(leaf.ref, "Leaf block", "Produces data", "Updated directly."),
            CreateEntity("component", "timer"),
            CreateEntity("design", "timer_top"),
        ),
    ).apply(revision)
    assert edited.succeeded, edited.diagnostics
    updated = edited.revision
    assert updated is not None
    assert [item.entity_id for item in updated.manifest.documents[:len(original_ids)]] == original_ids
    assert updated.by_vlnv("component", "spec2gds.local:work:timer:1.0")
    created_design = updated.by_vlnv("design", "spec2gds.local:work:timer_top:1.0")
    assert created_design.ref in [item.ref for item in updated.entry_designs()]

    duplicate = SpecEditTransaction(
        updated.source_revision_hash,
        (CreateEntity("component", "timer"),),
    ).apply(updated)
    assert not duplicate.succeeded
    assert "already exists" in duplicate.diagnostics[0]

    unsupported = SpecEditTransaction(
        updated.source_revision_hash,
        (SetEntityMetadata(updated.bus_definitions[0].ref, "Bus", None, None),),
    ).apply(updated)
    assert not unsupported.succeeded
    assert "only components and designs" in unsupported.diagnostics[0]

    cleared = SpecEditTransaction(
        updated.source_revision_hash,
        (SetEntityMetadata(leaf.ref, None, None, None),),
    ).apply(updated)
    assert cleared.succeeded, cleared.diagnostics
    cleared_package = cleared.revision.to_package() if cleared.revision else None
    assert cleared_package is not None
    leaf_entry = next(item for item in cleared_package.manifest.documents if item.entity_id == leaf.ref.entity_id)
    assert b"displayName" not in cleared_package.files[leaf_entry.path]
    assert b"shortDescription" not in cleared_package.files[leaf_entry.path]
    assert b"<ipxact:description>" not in cleared_package.files[leaf_entry.path]


def test_direct_editor_adds_and_updates_wire_ports_but_blocks_composites() -> None:
    revision = _revision()
    sink = revision.by_vlnv("component", "spec2gds.example:demo:sink:1.0")
    added = SpecEditTransaction(
        revision.source_revision_hash,
        (AddComponentPort(sink.ref, "status", "out", "7", "0", "Status vector"),),
    ).apply(revision)
    assert added.succeeded, added.diagnostics
    updated = added.revision
    assert updated is not None
    port = next(item for item in updated.by_vlnv("component", sink.vlnv).ports if item.name == "status")
    assert (port.style, port.direction, port.width) == ("wire", "out", "[7:0]")

    changed = SpecEditTransaction(
        updated.source_revision_hash,
        (UpdateComponentPort(sink.ref, "status", "inout", None, None, "Scalar status"),),
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
        (AddComponentPort(sink.ref, "partial", "in", "3", None),),
    ).apply(updated)
    assert not bad_bounds.succeeded
    assert "both left and right" in bad_bounds.diagnostics[0]

    duplicate = SpecEditTransaction(
        updated.source_revision_hash,
        (AddComponentPort(sink.ref, "payload_in", "in"),),
    ).apply(updated)
    assert not duplicate.succeeded
    assert "already has a port" in duplicate.diagnostics[0]

    missing = SpecEditTransaction(
        updated.source_revision_hash,
        (UpdateComponentPort(sink.ref, "missing", "in"),),
    ).apply(updated)
    assert not missing.succeeded
    assert "Unknown component port" in missing.diagnostics[0]

    subsystem = revision.by_vlnv("component", "spec2gds.example:demo:subsystem:1.0")
    composite = SpecEditTransaction(
        revision.source_revision_hash,
        (AddComponentPort(subsystem.ref, "blocked", "in"),),
    ).apply(revision)
    assert not composite.succeeded
    assert "internal designs" in composite.diagnostics[0]

    transactional_ref = EntityRef(
        document_id=revision.document_id,
        entity_id="component_transactional",
        entity_kind="component",
    )
    transactional_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<ipxact:component xmlns:ipxact="http://www.accellera.org/XMLSchema/IPXACT/1685-2022" xml:id="component_transactional">
  <ipxact:vendor>spec2gds.example</ipxact:vendor><ipxact:library>demo</ipxact:library>
  <ipxact:name>transactional</ipxact:name><ipxact:version>1.0</ipxact:version>
  <ipxact:model><ipxact:ports><ipxact:port><ipxact:name>service</ipxact:name>
    <ipxact:transactional><ipxact:initiative>requires</ipxact:initiative></ipxact:transactional>
  </ipxact:port></ipxact:ports></ipxact:model>
</ipxact:component>"""
    transactional = SpecEditTransaction(
        revision.source_revision_hash,
        (
            UpsertDocumentXml("component", transactional_xml),
            UpdateComponentPort(transactional_ref, "service", "in"),
        ),
    ).apply(revision)
    assert not transactional.succeeded
    assert "Transactional component ports are read-only" in transactional.diagnostics[0]
