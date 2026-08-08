"""Acceptance tests for the V1.1 deterministic source-package foundation."""

import json
import tempfile
import zipfile
from pathlib import Path

import pytest

from spec2gds.agent_spec.spec_format.archive import SpecPackage, SpecValidationError
from spec2gds.agent_spec.spec_format.cli import main
from spec2gds.agent_spec.spec_format.ipxact import validate_ipxact_document
from spec2gds.agent_spec.spec_format.testing import _xml, build_test_package


def test_package_factory_covers_the_v1_source_shape() -> None:
    """Keep the test package broad enough to cover every persisted source kind."""
    package = build_test_package()
    assert {entry.kind for entry in package.manifest.documents} == {
        "component",
        "design",
        "bus_definition",
        "abstraction_definition",
    }
    assert len(package.manifest.entry_designs) == 2
    assert len(package.manifest.component_compositions) == 1
    assert package.manifest.component_compositions[0].internal_design.entity_id == "design_subsystem_internal"
    blocks = []
    pending = list(package.narrative.blocks)
    while pending:
        block = pending.pop()
        blocks.append(block)
        pending.extend(block.children)
    assert {block.type for block in blocks} >= {
        "section",
        "paragraph",
        "list",
        "table",
        "image",
        "entity_link",
        "live_view",
    }
    assert package.manifest.assets[0].media_type == "image/svg+xml"
    assert b"V1 SOURCE ARCHITECTURE" in package.files[package.manifest.assets[0].path]
    assert package.diagnostics() == []


def test_save_load_and_repack_are_byte_deterministic() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        first = root / "first.spec"
        second = root / "second.spec"
        original = build_test_package()
        original.save(str(first))
        loaded = SpecPackage.load(str(first))
        loaded.save(str(second))

        assert first.read_bytes() == second.read_bytes()
        assert loaded.source_hash() == original.source_hash()
        with zipfile.ZipFile(first) as archive:
            entries = archive.infolist()
            assert entries[0].filename == "mimetype"
            assert entries[0].compress_type == zipfile.ZIP_STORED
        assert all(entry.date_time == (1980, 1, 1, 0, 0, 0) for entry in entries)


def test_in_memory_package_round_trip_is_byte_deterministic() -> None:
    package = build_test_package()
    encoded = package.to_bytes()
    restored = SpecPackage.from_bytes(encoded)
    assert restored.to_bytes() == encoded
    assert restored.source_hash() == package.source_hash()


def test_activity_is_excluded_from_source_hash_but_not_from_package_validation() -> None:
    package = build_test_package()
    source_hash = package.source_hash()
    package.files["activity/2026-07-18/run.json"] = b'{"status":"complete"}'
    assert package.diagnostics() == []
    assert package.source_hash() == source_hash


def test_invalid_document_hash_and_missing_asset_are_rejected() -> None:
    package = build_test_package()
    document_path = package.manifest.documents[0].path
    package.files[document_path] += b"\n"
    package.files.pop(package.manifest.assets[0].path)
    diagnostics = package.diagnostics()
    assert any("Document hash mismatch" in diagnostic for diagnostic in diagnostics)
    assert any("Manifest asset entries do not match" in diagnostic for diagnostic in diagnostics)
    with pytest.raises(SpecValidationError):
        package.require_valid()


def test_profile_rejects_implementation_views() -> None:
    component = b'''<?xml version="1.0" encoding="UTF-8"?>
<ipxact:component xmlns:ipxact="http://www.accellera.org/XMLSchema/IPXACT/1685-2022" xml:id="component_bad">
  <ipxact:vendor>spec2gds.example</ipxact:vendor><ipxact:library>demo</ipxact:library>
  <ipxact:name>bad</ipxact:name><ipxact:version>1.0</ipxact:version>
  <ipxact:model><ipxact:views><ipxact:view><ipxact:name>rtl</ipxact:name></ipxact:view></ipxact:views></ipxact:model>
</ipxact:component>'''
    with pytest.raises(ValueError, match="does not support IP-XACT element views"):
        validate_ipxact_document(component, "component")


@pytest.mark.parametrize(("port_xml", "message"), [
    ("""<ipxact:port><ipxact:name>wide</ipxact:name><ipxact:wire>
      <ipxact:direction>out</ipxact:direction><ipxact:vectors>
        <ipxact:vector><ipxact:left>7</ipxact:left><ipxact:right>0</ipxact:right></ipxact:vector>
        <ipxact:vector><ipxact:left>3</ipxact:left><ipxact:right>0</ipxact:right></ipxact:vector>
      </ipxact:vectors></ipxact:wire></ipxact:port>""", "at most one vector range"),
    ("""<ipxact:port><ipxact:name>clock</ipxact:name><ipxact:wire>
      <ipxact:direction>in</ipxact:direction><ipxact:qualifier><ipxact:isClock>true</ipxact:isClock></ipxact:qualifier>
    </ipxact:wire></ipxact:port>""", "uses unsupported fields: qualifier"),
    ("""<ipxact:port><ipxact:name>logical</ipxact:name><ipxact:wire allLogicalDirectionsAllowed="true">
      <ipxact:direction>in</ipxact:direction>
    </ipxact:wire></ipxact:port>""", "uses unsupported attributes: allLogicalDirectionsAllowed"),
    ("""<ipxact:port><ipxact:name>service</ipxact:name><ipxact:transactional>
      <ipxact:initiative>requires</ipxact:initiative><ipxact:protocol><ipxact:protocolType>tlm</ipxact:protocolType></ipxact:protocol>
    </ipxact:transactional></ipxact:port>""", "uses unsupported fields: protocol"),
    ("""<ipxact:port><ipxact:name>bundle</ipxact:name><ipxact:structured packed="false">
      <ipxact:union direction="out"/><ipxact:structPortTypeDefs><ipxact:structPortTypeDef>
        <ipxact:typeName>bundle_struct_t</ipxact:typeName>
      </ipxact:structPortTypeDef></ipxact:structPortTypeDefs>
    </ipxact:structured></ipxact:port>""", "must be packed"),
])
def test_profile_rejects_unsupported_port_constructs(port_xml: str, message: str) -> None:
    component = _xml(
        "component",
        "component_bad_port",
        "bad_port",
        f"<ipxact:model><ipxact:ports>{port_xml}</ipxact:ports></ipxact:model>",
    )

    with pytest.raises(ValueError, match=message):
        validate_ipxact_document(component, "component")


def test_xml_namespace_prefixes_are_normalized_deterministically() -> None:
    document = b'''<x:design xmlns:x="http://www.accellera.org/XMLSchema/IPXACT/1685-2022" xml:id="design_prefix">
      <x:vendor>spec2gds.example</x:vendor><x:library>demo</x:library><x:name>prefix</x:name><x:version>1.0</x:version>
    </x:design>'''
    normalized, _, _ = validate_ipxact_document(document, "design")
    assert b"<ipxact:design" in normalized
    assert b"xmlns:ipxact=" in normalized
    assert b"<x:design" not in normalized


def test_unsupported_package_mimetype_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        unsupported = Path(temporary) / "unsupported.spec"
        with zipfile.ZipFile(unsupported, "w") as archive:
            archive.writestr("mimetype", "application/vnd.oasis.opendocument.text")
            archive.writestr("content.xml", "<document-content/>")
        with pytest.raises(SpecValidationError, match="Unsupported package mimetype"):
            SpecPackage.load(str(unsupported))


def test_cli_create_validate_inspect_unpack_and_pack(capsys: pytest.CaptureFixture[str]) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        source = root / "new.spec"
        unpacked = root / "unpacked"
        repacked = root / "repacked.spec"
        assert main(["create", "--output", str(source), "--document-id", "spec_cli"]) == 0
        assert main(["validate", "--container", str(source)]) == 0
        capsys.readouterr()
        assert main(["inspect", "--container", str(source), "--format", "json"]) == 0
        report = json.loads(capsys.readouterr().out)
        assert report["manifest"]["document_id"] == "spec_cli"
        assert main(["unpack", "--container", str(source), "--output", str(unpacked)]) == 0
        assert main(["pack", "--input", str(unpacked), "--output", str(repacked)]) == 0
        assert source.read_bytes() == repacked.read_bytes()
