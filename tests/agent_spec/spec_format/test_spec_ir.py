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
from spec2gds.agent_spec.spec_format.samples import build_v1_sample
from spec2gds.agent_spec.spec_format.transactions import (
    ClearInternalDesign,
    ReorderInstances,
    SetInternalDesign,
    SetNarrativeEntityLinks,
    SpecEditTransaction,
    UpsertConnection,
    UpsertInstance,
)


def _revision() -> SpecRevision:
    return SpecRevision.from_package(build_v1_sample())


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
