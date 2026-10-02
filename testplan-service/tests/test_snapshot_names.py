"""Readable snapshot projections retain exact source and occurrence identities."""

from copy import deepcopy

from lxml import etree
from testplan_service.integrations.snapshot_decoder import decode_snapshot_bytes

from spec2gds.agent_spec.activities import ActivitySnapshot
from spec2gds.agent_spec.spec_format import ipxact
from spec2gds.agent_spec.spec_format.ir import SpecRevision
from spec2gds.agent_spec.spec_format.models import NarrativeBlock
from spec2gds.agent_spec.spec_format.naming import normalize_package_names
from spec2gds.agent_spec.spec_format.testing import build_test_package
from spec2gds.agent_spec.spec_format.transactions import SetEntityMetadata, SpecEditTransaction


def test_snapshot_uses_source_names_and_qualified_nested_headings():
    package = build_test_package()
    package.narrative = package.narrative.model_copy(update={
        "title": "Timer controller",
        "blocks": [NarrativeBlock(block_id="operation", type="section", text="Operation", children=[
            NarrativeBlock(block_id="cycle", type="section", text="Cycle timing <review> & reset"),
        ])],
    })
    normalize_package_names(package)
    revision = SpecRevision.from_package(package)
    target = revision.components[0].ref
    result = SpecEditTransaction(revision.source_revision_hash, (
        SetEntityMetadata(target, display_name="Countdown timer", short_description=None, description=None),
    )).apply(revision)
    assert result.succeeded
    snapshot = ActivitySnapshot.create(result.revision, target)
    view = decode_snapshot_bytes(snapshot.to_bytes())
    assert view.source_name == "Timer controller"
    entity = next(item for item in view.entities if item.entity_ref["entity_id"] == target.entity_id)
    assert entity.name == "Countdown timer"
    assert entity.qualified_name == "Timer controller › Countdown timer"
    assert entity.vlnv == revision.resolve(target).vlnv
    assert view.occurrences[0].occurrence_id == target.entity_id
    assert view.occurrences[0].name == "Countdown timer"
    section = next(item for item in view.source_sections if item.section_id == "cycle")
    assert section.qualified_name == "Timer controller › Operation › Cycle timing <review> & reset"
    assert section.locator["section_id"] == "cycle"


def test_repeated_composites_have_distinct_qualified_occurrences():
    package = build_test_package()
    entry = next(item for item in package.manifest.documents if item.entity_id == "design_top_a")
    root = ipxact.parse_xml(package.files[entry.path])
    instances = root.xpath("./*[local-name()='componentInstances']")[0]
    second = deepcopy(instances[0])
    second.xpath("./*[local-name()='instanceName']")[0].text = "subsystem1"
    instances.append(second)
    package.add_document("design", etree.tostring(root))
    normalize_package_names(package)
    revision = SpecRevision.from_package(package)
    target = next(item.ref for item in revision.designs if item.ref.entity_id == "design_top_a")
    view = decode_snapshot_bytes(ActivitySnapshot.create(revision, target).to_bytes())
    leaves = [item for item in view.occurrences if item.name == "leaf0"]
    assert len(leaves) == 2
    assert leaves[0].occurrence_id != leaves[1].occurrence_id
    assert leaves[0].component_ref == leaves[1].component_ref
    assert {item.instance_chain[-2] for item in leaves} == {"subsystem0", "subsystem1"}
    assert len({item.qualified_name for item in leaves}) == 2
    assert all("/leaf0" in item.path for item in leaves)
