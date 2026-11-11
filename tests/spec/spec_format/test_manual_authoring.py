"""Manual authoring must remain atomic and must not invoke lint on reads or saves."""

from spec2gds.spec.spec_format.testing import direct_api_endpoints
from unittest.mock import patch

import fastapi
import pytest

from spec2gds.spec.spec_format.archive import SpecPackage
from spec2gds.spec.spec_format.document import build_a2ui_batch, build_document_projection
from spec2gds.spec.spec_format.ir import SpecRevision
from spec2gds.spec.spec_format.transactions import CreateHardware, SpecEditTransaction, UpsertSection
from spec2gds.spec.spec_format.v1_api import ActivityExecutionRequest, CreateDocumentRequest, TransactionRequest, create_app


def endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("SPEC_EDITOR_STATE_ROOT", str(tmp_path / "state"))
    return direct_api_endpoints(create_app())


def test_authoring_saves_invalid_body_without_compiler_and_reads_stay_cached(tmp_path, monkeypatch):
    api = endpoints(tmp_path, monkeypatch)
    snapshot = api["create_document"](CreateDocumentRequest(path=str(tmp_path / "manual.spec"), title="Manual authoring"))
    def commit(ops):
        nonlocal snapshot
        snapshot = api["transaction"](TransactionRequest(expected_source_revision_hash=snapshot["source_revision_hash"], operations=ops, validation_mode="authoring"))["snapshot"]
        return snapshot
    with patch("subprocess.run", side_effect=AssertionError("Implicit compiler invocation")):
        commit([{"type": "create_entity", "kind": "component", "name": "32-bit readable adder"}])
        ref = snapshot["components"][0]["ref"]
        commit([{"type": "upsert_entity_section", "parent": ref, "section_type": "sv", "type_version": 1, "payload": {"content": "assign missing = ;"}}])
        view = api["document_view"]()
        parent = next(item for item in view["a2ui"]["messages"][1]["updateComponents"]["components"] if item.get("section", {}).get("entity_ref") == ref and item.get("component") == "SpecSection")
        assert parent["section"]["implementation_kind"] == "sv"
        assert parent["section"]["content_sections"] == []
        assert snapshot["section_validation"][0]["status"] == "unverified"
        assert "assign missing = ;" in snapshot["entity_sections"][0]["content"]
    checked = api["verify_component"]("component", ref["entity_id"], ActivityExecutionRequest(expected_source_revision_hash=snapshot["source_revision_hash"]))
    assert checked["status"] != "passed"
    with patch("shutil.which", return_value=None):
        unavailable = api["verify_component"]("component", ref["entity_id"], ActivityExecutionRequest(expected_source_revision_hash=snapshot["source_revision_hash"]))
    assert unavailable["status"] == "unverified"
    assert unavailable["tool_version"] == "Unavailable"
    assert "assign missing = ;" in api["document_snapshot"]()["entity_sections"][0]["content"]
    old = snapshot["source_revision_hash"]
    commit([{"type": "set_document_title", "title": "Changed source"}])
    assert snapshot["verifications"][0]["status"] == "stale"
    with pytest.raises(fastapi.HTTPException) as stale:
        api["verify_component"]("component", ref["entity_id"], ActivityExecutionRequest(expected_source_revision_hash=old))
    assert stale.value.status_code == 409


def test_parameters_and_atomic_port_batch(tmp_path, monkeypatch):
    api = endpoints(tmp_path, monkeypatch)
    snapshot = api["create_document"](CreateDocumentRequest(path=str(tmp_path / "params.spec"), title="Parameters"))
    def commit(ops):
        nonlocal snapshot
        snapshot = api["transaction"](TransactionRequest(expected_source_revision_hash=snapshot["source_revision_hash"], operations=ops, validation_mode="authoring"))["snapshot"]
    commit([{"type": "create_entity", "kind": "component", "name": "Parameterized pass-through"}])
    ref = snapshot["components"][0]["ref"]
    commit([{"type": "update_parameter", "component": ref, "parameter": {"name": "N", "rtl_type": "int unsigned", "value": "13", "description": "Bus width"}},
            {"type": "add_component_port", "component": ref, "port": {"name": "a", "family": "wire", "direction": "in", "range": "N-1:0"}}])
    assert snapshot["components"][0]["parameters"][0]["rtl_type"] == "int unsigned"
    before = snapshot["source_revision_hash"]
    with pytest.raises(fastapi.HTTPException):
        commit([{"type": "add_component_port", "component": ref, "port": {"name": name, "family": "wire", "direction": "out", "range": "0:0"}} for name in ["y", "a"]])
    assert api["document_snapshot"]()["source_revision_hash"] == before
    commit([{"type": "delete_component_port", "component": ref, "name": "a"}, {"type": "delete_parameter", "component": ref, "name": "N"}])
    assert snapshot["components"][0]["parameters"] == []


def test_explicit_verification_resolves_parameters_and_retains_revision(tmp_path, monkeypatch):
    import shutil
    if not shutil.which("verilator"):
        pytest.skip("Explicit symbolic interface verification requires Verilator")
    api = endpoints(tmp_path, monkeypatch)
    snapshot = api["create_document"](CreateDocumentRequest(path=str(tmp_path / "symbolic.spec"), title="Symbolic"))
    def commit(ops):
        nonlocal snapshot
        snapshot = api["transaction"](TransactionRequest(expected_source_revision_hash=snapshot["source_revision_hash"], operations=ops, validation_mode="authoring"))["snapshot"]
    commit([{"type": "create_entity", "kind": "component", "name": "Pass-through"}])
    ref = snapshot["components"][0]["ref"]
    commit([{"type": "add_component_port", "component": ref, "port": {"name": name, "family": "wire", "direction": direction, "range": "N-1:0"}} for name, direction in [("a", "in"), ("y", "out")]] + [
        {"type": "update_parameter", "component": ref, "parameter": {"name": "N", "rtl_type": "int unsigned", "value": "13"}},
        {"type": "upsert_entity_section", "parent": ref, "section_type": "sv", "type_version": 1, "payload": {"content": "assign y = a;"}},
    ])
    for value in [13, 5]:
        if value == 5:
            commit([{"type": "update_parameter", "component": ref, "parameter": {"name": "N", "rtl_type": "int unsigned", "value": "5", "description": "Bus width"}}])
            assert snapshot["verifications"][0]["status"] == "stale"
        with patch("subprocess.run", side_effect=AssertionError("Activity menu must not run a compiler")):
            assert api["entity_activities"]("component", ref["entity_id"])["activities"]
        result = api["verify_component"]("component", ref["entity_id"], ActivityExecutionRequest(expected_source_revision_hash=snapshot["source_revision_hash"]))
        assert result["status"] == "passed", result["diagnostics"]
        assert [port["width"] for port in result["interfaces"][0]["ports"]] == [value, value]
        assert all(port["range"] == "N-1:0" for port in result["interfaces"][0]["ports"])
        assert result["source_revision_hash"] == snapshot["source_revision_hash"]
        assert result["functional_simulation"] == "unverified"
    # A cached passing leaf Section cannot waive a rejected selected root.
    def reject_root(spec, target):
        assert target.model_dump(mode="json") == ref
        raise ValueError("Invalid selected root boundary")
    monkeypatch.setattr("spec2gds.spec.activities.rtl.codegen.generate_project", reject_root)
    result = api["verify_component"]("component", ref["entity_id"], ActivityExecutionRequest(expected_source_revision_hash=snapshot["source_revision_hash"]))
    assert result["status"] == "failed"
    assert any(item["code"] == "TARGET_HIERARCHY_INVALID" for item in result["diagnostics"])


def test_strict_transactions_still_reject_invalid_systemverilog():
    revision = SpecRevision.from_package(SpecPackage.create(title="Strict"))
    revision = SpecEditTransaction(revision.source_revision_hash, (CreateHardware("component", "Strict body"),)).apply(revision).revision
    assert revision is not None
    result = SpecEditTransaction(revision.source_revision_hash, (UpsertSection(revision.components[0].ref, "sv", {"content": "assign broken = ;"}),)).apply(revision)
    # A missing compiler remains explicitly unverified; with Verilator a bad body cannot commit.
    import shutil
    if shutil.which("verilator"):
        assert not result.succeeded


def test_circuit_launch_and_commit_keep_the_exact_package_after_another_spec_opens(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import spec2gds.spec.spec_format.v1_api as module
    from spec2gds.spec.spec_format.testing import write_test_package
    from spec2gds.spec.spec_format.v1_api import CircuitLaunchRequest, CircuitSourceSyncRequest, OpenDocumentRequest
    api = endpoints(tmp_path, monkeypatch)
    original = tmp_path / "original.spec"
    other = tmp_path / "other.spec"
    write_test_package(original)
    first = api["open_document"](OpenDocumentRequest(path=str(original)))
    second = api["create_document"](CreateDocumentRequest(path=str(other), title="Other open Spec"))
    other_bytes = other.read_bytes()
    published, registrations = [], []
    def publish(document, **kwargs):
        published.append(document)
        return SimpleNamespace(document_id=document["document_id"], editor_url="http://localhost/circuit", reused_session=False)
    monkeypatch.setattr(module, "publish_circuit_document", publish)
    monkeypatch.setattr(module, "register_circuit_source_binding", lambda *args, **kwargs: registrations.append(kwargs))
    launched = api["launch_circuit"](CircuitLaunchRequest(entity_kind="design", entity_id="design_subsystem_internal"), owner_document_key=first["owner_document_key"])
    assert launched["source_binding"]["source_owner_document_key"] == first["owner_document_key"]
    request = CircuitSourceSyncRequest(request_id="bound_layout", base_source_revision_hash=first["source_revision_hash"], candidate_document=published[0])
    with patch("subprocess.run", side_effect=AssertionError("Implicit compiler invocation")):
        saved = api["commit_circuit_source"](request, authorization=f"Bearer {registrations[0]['token']}")
    assert saved["accepted"] is True
    assert api["document_snapshot"](owner_document_key=first["owner_document_key"])["source_revision_hash"] == saved["source_revision_hash"]
    assert api["document_snapshot"]()["owner_document_key"] == second["owner_document_key"]
    assert other.read_bytes() == other_bytes


def test_circuit_relaunch_refreshes_through_the_source_protocol(monkeypatch):
    import io
    import json
    import urllib.request
    from spec2gds.spec.spec_format.circuit_adapter import publish_circuit_document, register_circuit_source_binding
    calls = []
    def respond(request, **kwargs):
        method = "GET" if isinstance(request, str) else request.get_method()
        url = request if isinstance(request, str) else request.full_url
        calls.append((method, url))
        if method == "GET":
            payload = {"revision": "1", "document": {"document_id": "circuit", "label": "Old title"}}
        else:
            assert url.endswith(("source-binding", "source/reload")), "Do not bypass the source write guard."
            payload = {"accepted": True}
        return io.BytesIO(json.dumps(payload).encode())
    monkeypatch.setattr(urllib.request, "urlopen", respond)
    launch = publish_circuit_document({"document_id": "circuit", "label": "Current title"}, service_url="http://localhost/api", editor_url="http://localhost/ui", refresh_existing=False)
    assert launch.reused_session
    register_circuit_source_binding("circuit", {}, service_url="http://localhost/api", callback_url="http://localhost/source", token="test-token", reload_source=True)
    assert [method for method, _ in calls] == ["GET", "PUT", "POST"]
    assert calls[-1][1].endswith("/source/reload")


def test_circuit_draft_conflict_has_an_actionable_message(monkeypatch):
    import io
    import urllib.error
    import urllib.request
    from spec2gds.spec.spec_format.circuit_adapter import CircuitDesignerConnectionError, register_circuit_source_binding
    message = "Cancel or save the active draft before reopening its source binding."
    def reject(request, **kwargs):
        raise urllib.error.HTTPError(request.full_url, 423, "Locked", {}, io.BytesIO(
            ('{"code":"lock_conflict","message":"' + message + '"}').encode()))
    monkeypatch.setattr(urllib.request, "urlopen", reject)
    with pytest.raises(CircuitDesignerConnectionError) as result:
        register_circuit_source_binding("circuit", {}, service_url="http://localhost/api", callback_url="http://localhost/source", token="test-token")
    assert str(result.value) == message
    assert result.value.status_code == 423


def test_circuit_launch_preserves_structured_lock_recovery_details(tmp_path, monkeypatch):
    from spec2gds.spec.spec_format.circuit_adapter import CircuitDesignerConnectionError
    from spec2gds.spec.spec_format.v1_api import CircuitLaunchRequest
    api = endpoints(tmp_path, monkeypatch)
    snapshot = api["create_document"](CreateDocumentRequest(path=str(tmp_path / "locked.spec"), title="Locked Circuit"))
    snapshot = api["transaction"](TransactionRequest(
        expected_source_revision_hash=snapshot["source_revision_hash"],
        operations=[{"type": "create_entity", "kind": "design", "name": "top"}],
    ))["snapshot"]
    request = CircuitLaunchRequest(entity_kind="design", entity_id=snapshot["designs"][0]["ref"]["entity_id"])
    with patch("spec2gds.spec.spec_format.v1_api.publish_circuit_document") as publish, patch(
        "spec2gds.spec.spec_format.v1_api.register_circuit_source_binding",
        side_effect=CircuitDesignerConnectionError("An active draft exists", status_code=423,
            details={"document_id": "circuit", "lease": {"lease_id": "old", "expires_at": "2026-10-20T12:00:00Z"}}),
    ):
        publish.return_value.document_id = "circuit"
        publish.return_value.editor_url = "http://localhost:7022/?document_id=circuit"
        publish.return_value.reused_session = True
        with pytest.raises(fastapi.HTTPException) as caught:
            api["launch_circuit"](request)
    assert caught.value.status_code == 423
    assert caught.value.detail["code"] == "lock_conflict"
    assert caught.value.detail["lease"]["lease_id"] == "old"
    assert caught.value.detail["editor_url"].endswith("document_id=circuit")


def test_recovery_binding_uses_one_conditional_registration_without_reload(monkeypatch):
    import io
    import json
    from spec2gds.spec.spec_format.circuit_adapter import register_circuit_source_binding
    requests = []
    def respond(request, **kwargs):
        requests.append(request)
        return io.BytesIO(json.dumps({"lease": {"lease_id": "new"}, "snapshot": {}}).encode())
    monkeypatch.setattr("urllib.request.urlopen", respond)
    recovery = {"expected_lease_id": "old", "owner_id": "new-tab"}
    result = register_circuit_source_binding("circuit", {}, service_url="http://localhost/api",
        callback_url="http://localhost/source", token="private-token", recovery=recovery, reload_source=True)
    assert len(requests) == 1
    assert json.loads(requests[0].data)["recovery"] == recovery
    assert result["lease"]["lease_id"] == "new"


@pytest.mark.parametrize("bad_range", ["15-0", "15", "WIDTH-1", "15:", ":0", "15:0:1", "[]", "([WIDTH)]:0"])
def test_port_format_rejection_is_atomic_without_compiler(tmp_path, monkeypatch, bad_range):
    api = endpoints(tmp_path, monkeypatch)
    path = tmp_path / "ranges.spec"
    snapshot = api["create_document"](CreateDocumentRequest(path=str(path), title="Ranges"))
    def commit(ops):
        nonlocal snapshot
        snapshot = api["transaction"](TransactionRequest(expected_source_revision_hash=snapshot["source_revision_hash"], operations=ops, validation_mode="authoring"))["snapshot"]
    with patch("subprocess.run", side_effect=AssertionError("Implicit compiler invocation")):
        commit([{"type": "create_entity", "kind": "component", "name": "Ranges"}])
        ref = snapshot["components"][0]["ref"]
        base = {"family": "wire", "direction": "in", "range": "15:0"}
        commit([{"type": "add_component_port", "component": ref, "port": {**base, "name": "a"}}])
        before, revision = path.read_bytes(), snapshot["source_revision_hash"]
        for operations in [
            [{"type": "add_component_port", "component": ref, "port": {**base, "name": "bad", "range": bad_range}}],
            [{"type": "update_component_port", "component": ref, "name": "a", "port": {**base, "range": bad_range}}],
            [{"type": "add_component_port", "component": ref, "port": {**base, "name": name, "range": value}} for name, value in [("ok", "7:0"), ("bad", bad_range)]],
        ]:
            with pytest.raises(fastapi.HTTPException) as error:
                commit(operations)
            assert error.value.status_code == 422
            assert path.read_bytes() == before
            assert api["document_snapshot"]()["source_revision_hash"] == revision


def test_explicit_range_format_preserves_legacy_readers_and_equal_bounds():
    from spec2gds.spec.spec_format.source_edits import parse_wire_range, format_wire_range
    from spec2gds.spec.spec_format.rtl_interface import split_range
    for source, expected in [("", (None, None)), ("15:0", ("15", "0")), ("[15:0]", ("15", "0")),
                             ("0:15", ("0", "15")), ("-1:-4", ("-1", "-4")), ("WIDTH-1:0", ("WIDTH-1", "0")),
                             ("pkg::WIDTH-1:0", ("pkg::WIDTH-1", "0")), ("VALUE[3:0]:0", ("VALUE[3:0]", "0")),
                             ("(USE ? WIDTH:4)-1:0", ("(USE ? WIDTH:4)-1", "0"))]:
        assert parse_wire_range(source) == expected
    assert split_range("15-0") == ("15-0", "15-0")
    assert format_wire_range("15", "15") == "15:15"
    assert format_wire_range("15-0", "15-0") == "15-0:15-0"


def test_legacy_identical_expression_bounds_open_and_survive_unrelated_edits(tmp_path, monkeypatch):
    from spec2gds.spec.spec_format.testing import _xml
    from spec2gds.spec.spec_format.v1_api import OpenDocumentRequest
    package = SpecPackage.create("legacy_ranges")
    body = '<ipxact:model><ipxact:ports><ipxact:port><ipxact:name>a</ipxact:name><ipxact:wire><ipxact:direction>in</ipxact:direction><ipxact:vectors><ipxact:vector><ipxact:left>15-0</ipxact:left><ipxact:right>15-0</ipxact:right></ipxact:vector></ipxact:vectors></ipxact:wire></ipxact:port></ipxact:ports></ipxact:model>'
    package.add_document("component", _xml("component", "component_legacy", "legacy", body))
    path = tmp_path / "legacy.spec"
    package.save(str(path))
    api = endpoints(tmp_path, monkeypatch)
    with patch("subprocess.run", side_effect=AssertionError("Implicit compiler invocation")):
        saved = api["open_document"](OpenDocumentRequest(path=str(path)))
        component_bytes = next(value for name, value in SpecPackage.load(str(path)).files.items() if name.startswith("ipxact/components/"))
        view = api["document_view"]()
        assert "15-0:15-0" in str(view["a2ui"])
        api["transaction"](TransactionRequest(expected_source_revision_hash=saved["source_revision_hash"], operations=[{"type": "set_document_title", "title": "Legacy retained"}], validation_mode="authoring"))
        assert next(value for name, value in SpecPackage.load(str(path)).files.items() if name.startswith("ipxact/components/")) == component_bytes
