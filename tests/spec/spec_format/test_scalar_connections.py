"""Saved scalar selections must generate valid RTL and keep lint target-local."""

import shutil
from unittest.mock import patch

import pytest

from spec2gds.spec.activities.rtl.codegen import generate_project
from spec2gds.spec.activities.view import SpecAccess
from spec2gds.spec.spec_format.archive import SpecPackage
from spec2gds.spec.spec_format.component_verification import verify_target
from spec2gds.spec.spec_format.document import build_document_projection
from spec2gds.spec.spec_format.ir import SpecRevision
from spec2gds.spec.spec_format.models import ComponentComposition, EntityRef
from spec2gds.spec.spec_format.sections import upsert_systemverilog_section
from spec2gds.spec.spec_format.sv_validation import cached_revision_sections, validate_revision_sections, _run_project
from spec2gds.spec.spec_format.testing import _xml


def _port(name, direction, bounds):
    vector = "" if bounds is None else f"<ipxact:vectors><ipxact:vector><ipxact:left>{bounds[0]}</ipxact:left><ipxact:right>{bounds[1]}</ipxact:right></ipxact:vector></ipxact:vectors>"
    return f"<ipxact:port><ipxact:name>{name}</ipxact:name><ipxact:wire><ipxact:direction>{direction}</ipxact:direction>{vector}</ipxact:wire></ipxact:port>"


def _select(bit):
    return f"<ipxact:partSelect><ipxact:range><ipxact:left>{bit}</ipxact:left><ipxact:right>{bit}</ipxact:right></ipxact:range></ipxact:partSelect>"


def scalar_revision(input_bounds=None, leaf_bounds=None, output_bounds=None, *, invalid=False):
    package = SpecPackage.create("scalar_connections")
    for name, bounds in [("leaf", leaf_bounds), ("top", input_bounds)]:
        ports = _port("a", "in", bounds) + _port("y", "out", leaf_bounds if name == "leaf" else output_bounds)
        package.add_document("component", _xml("component", f"component_{name}", name, f"<ipxact:model><ipxact:ports>{ports}</ipxact:ports></ipxact:model>"))
    bit = leaf_bounds[1] if leaf_bounds else 0
    input_bit = input_bounds[0] if input_bounds else 0
    output_bit = output_bounds[0] if output_bounds else 0
    def internal(instance, port, index=bit):
        return f'<ipxact:internalPortReference componentInstanceRef="{instance}" portRef="{port}">{_select(index)}</ipxact:internalPortReference>'
    def external(port, index):
        return f'<ipxact:externalPortReference portRef="{port}">{_select(index)}</ipxact:externalPortReference>'
    nets = [
        ("input", internal("first", "a", 1 if invalid else bit) + internal("third", "a") + external("a", input_bit)),
        ("chain", internal("first", "y") + internal("second", "a")),
        ("output", internal("second", "y") + external("y", output_bit)),
    ]
    instances = "".join(f'<ipxact:componentInstance><ipxact:instanceName>{name}</ipxact:instanceName><ipxact:componentRef vendor="spec2gds.example" library="demo" name="leaf" version="1.0"/></ipxact:componentInstance>' for name in ["first", "second", "third"])
    connections = "".join(f"<ipxact:adHocConnection><ipxact:name>{name}</ipxact:name><ipxact:portReferences>{refs}</ipxact:portReferences></ipxact:adHocConnection>" for name, refs in nets)
    package.add_document("design", _xml("design", "design_top", "top_design", f"<ipxact:componentInstances>{instances}</ipxact:componentInstances><ipxact:adHocConnections>{connections}</ipxact:adHocConnections>"))
    def ref(kind, identity):
        return EntityRef(document_id=package.manifest.document_id, entity_id=identity, entity_kind=kind)
    package.manifest = package.manifest.model_copy(update={"component_compositions": [ComponentComposition(component=ref("component", "component_top"), internal_design=ref("design", "design_top"))]})
    upsert_systemverilog_section(package, ref("component", "component_leaf"), "assign y = a;")
    return SpecRevision.from_package(package)


@pytest.mark.parametrize("input_bounds,leaf_bounds,output_bounds", [
    (None, None, None), ((64, 0), None, None),
    (None, (0, 0), (5, 5)), (None, (5, 5), (0, 0)),
])
def test_saved_scalar_and_packed_selections_generate(input_bounds, leaf_bounds, output_bounds):
    revision = scalar_revision(input_bounds, leaf_bounds, output_bounds)
    top = revision.by_vlnv("component", "spec2gds.example:demo:top:1.0").ref
    before = revision.source_revision_hash
    project = generate_project(SpecAccess(revision, top), top)
    source = "\n".join(data.decode() for path, data in project.files.items() if path.endswith(".sv"))
    if leaf_bounds is None:
        assert "_bits[0]" not in source
    else:
        assert f"_bits[{leaf_bounds[1]}]" in source
    if input_bounds == (64, 0):
        assert "a[64]" in source
    if output_bounds is None:
        assert "y[0]" not in source
    else:
        assert f"y[{output_bounds[0]}]" in source
    assert revision.source_revision_hash == before
    assert generate_project(SpecAccess(revision, top), top).files == project.files
    if shutil.which("verilator"):
        diagnostics = _run_project(project.files, project.top_module, shutil.which("verilator"), None)
        assert not any(item.blocking for item in diagnostics), [item.as_json() for item in diagnostics]


def test_invalid_scalar_selection_still_fails_bounds_checks():
    revision = scalar_revision(invalid=True)
    top = revision.by_vlnv("component", "spec2gds.example:demo:top:1.0").ref
    with pytest.raises(ValueError, match="outside|range|bounds"):
        generate_project(SpecAccess(revision, top), top)


@pytest.mark.skipif(not shutil.which("verilator"), reason="Verilator is required for explicit lint")
def test_parent_failure_does_not_poison_leaf_or_section_cache():
    revision = scalar_revision()
    top = revision.by_vlnv("component", "spec2gds.example:demo:top:1.0").ref
    leaf = revision.by_vlnv("component", "spec2gds.example:demo:leaf:1.0").ref
    section, = revision.entity_sections_for(leaf, "sv")
    def reject_parent(spec, target):
        if target.entity_id != leaf.entity_id:
            raise ValueError("Broken parent wiring")
        return generate_project(spec, target)
    with patch("spec2gds.spec.activities.rtl.codegen.generate_project", side_effect=reject_parent):
        # Strict API checks keep their containing-Design behavior and own cache.
        strict, = validate_revision_sections(revision)
        assert strict.status == "unverified"
        checked = verify_target(revision, leaf)
        assert checked["status"] == "passed", checked
        parent = verify_target(revision, top)
        assert parent["status"] == "failed"
        assert parent["section_validation"][0]["status"] == "verified"
        assert any(item["code"] == "TARGET_HIERARCHY_INVALID" for item in parent["diagnostics"])
    assert cached_revision_sections(revision)[0].status == "verified"
    # A real leaf failure has a body location, not a generated parent line.
    package = revision.to_package()
    upsert_systemverilog_section(package, leaf, "assign y = ;")
    broken = SpecRevision.from_package(package)
    result = verify_target(broken, leaf)
    diagnostic = next(item for item in result["diagnostics"] if item.get("line"))
    assert diagnostic["source_kind"] == "section"
    assert diagnostic["file_path"] == section.source_path
    assert diagnostic["line"] == 1
    projection = build_document_projection(broken)
    assert any(item.file_path == section.source_path and item.source_kind == "section" and item.line == 1
               for parent in projection.sections for content in parent.content_sections for item in content.diagnostics)


@pytest.mark.skipif(not shutil.which("verilator"), reason="Verilator is required for explicit lint")
def test_generated_diagnostics_keep_their_file_and_do_not_mark_leaf_sections(monkeypatch):
    revision = scalar_revision()
    top = revision.by_vlnv("component", "spec2gds.example:demo:top:1.0").ref
    def check(files, module, executable, section):
        if section is None:
            files = {"rtl/broken.sv": b"module broken(input logic a, output logic y);\nassign y = a[0];\nendmodule\n", "rtl/files.f": b"broken.sv\n"}
            module = "broken"
        return _run_project(files, module, executable, section)
    monkeypatch.setattr("spec2gds.spec.spec_format.sv_validation._run_project", check)
    result = verify_target(revision, top)
    assert result["status"] == "failed"
    assert result["section_validation"][0]["status"] == "verified"
    error = next(item for item in result["diagnostics"] if item.get("line"))
    assert error["source_kind"] == "generated"
    assert error["file_path"] == "broken.sv"
    assert error["line"] == 2
    assert cached_revision_sections(revision)[0].status == "verified"
