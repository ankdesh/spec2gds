"""Published source, evidence, and explicit hierarchy parameter contracts."""

import json
from pathlib import Path

import pytest
from spec_catalog_service.catalog.authoring import build_component_spec
from spec_catalog_service.catalog.components import ALL_COMPONENTS_BY_ID
from spec_catalog_service.catalog.schemas import compute_sha256

from spec2gds.spec.spec_format.ir import SpecRevision

CATALOG = Path(__file__).resolve().parents[1] / "catalog"
PACKAGES = sorted(CATALOG.rglob("*.spec"))


def assert_source_contract(revision):
    internal = {mapping.internal_design.entity_id for mapping in revision.manifest.component_compositions}
    assert not internal & {ref.entity_id for ref in revision.manifest.entry_designs}
    for component in revision.components:
        design = revision.internal_design(component)
        if design is None:
            continue
        assert all(section.usage == "reference" for section in revision.entity_sections_for(component.ref, "sv"))
        parent_parameters = {parameter.name for parameter in component.parameters}
        for instance in design.instances:
            child = next(item for item in revision.components if item.vlnv == instance.component_vlnv)
            expected = {parameter.name: parameter.name for parameter in child.parameters}
            assert set(expected) <= parent_parameters
            assert dict(instance.parameter_values) == expected


@pytest.mark.parametrize("path", PACKAGES, ids=lambda path: path.stem)
def test_published_source_and_evidence_agree(path):
    revision = SpecRevision.load(path)
    assert_source_contract(revision)
    evidence = json.loads(path.with_name("evidence.json").read_text())
    assert evidence["source_revision_hash"] == revision.source_revision_hash
    assert evidence["package_sha256"] == compute_sha256(path.read_bytes())
    assert all(check["status"] == "pass" for check in evidence["checks"])
    inventory = json.loads((CATALOG / "inventory.json").read_text())
    release = next(release for entry in inventory["entries"] for release in entry["releases"]
                   if release["path"] == path.relative_to(CATALOG).as_posix())
    assert release["package_sha256"] == evidence["package_sha256"]
    assert release["evidence_sha256"] == compute_sha256(path.with_name("evidence.json").read_bytes())


@pytest.mark.parametrize("name", ["multiplier_pipeline", "crc_serial", "cordic_rotate"])
def test_composite_authoring_keeps_roles_and_explicit_parameter_mappings(name):
    revision = SpecRevision.from_package(build_component_spec(ALL_COMPONENTS_BY_ID[name]))
    assert not revision.entry_designs()
    assert_source_contract(revision)
