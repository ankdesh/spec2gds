"""Check compatibility at terminology transitions that affect saved data or CLI use."""

import json

from spec2gds.service_registry import load_service_registry
from spec2gds.spec.activities.scratch_directory import LocalActivityScratchDirectory
from spec2gds.spec.api.__main__ import _parser
from spec2gds.spec.spec_format.spec_service_store import SpecServiceBindings


def test_service_environment_and_approval_aliases(monkeypatch):
    monkeypatch.setenv("AGENT_SPEC_HOST", "127.0.0.2")
    monkeypatch.setenv("AGENT_SPEC_PORT", "6020")
    assert _parser("server").parse_args([]).host is None
    monkeypatch.setenv("SPEC_SERVICE_HOST", "127.0.0.3")
    monkeypatch.setenv("SPEC_SERVICE_PORT", "6021")
    args = _parser("server").parse_args(["--require-designer-approval"])
    assert (args.host, args.port, args.require_designer_approval) == (None, None, True)
    assert _parser("server").parse_args(["--require-human-approval"]).require_designer_approval


def test_state_root_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv("SPEC_EDITOR_STATE_ROOT", str(tmp_path / "legacy"))
    SpecServiceBindings()
    assert (tmp_path / "legacy" / "bindings.sqlite3").exists()
    monkeypatch.setenv("SPEC_SERVICE_STATE_ROOT", str(tmp_path / "canonical"))
    SpecServiceBindings()
    assert (tmp_path / "canonical" / "bindings.sqlite3").exists()


def test_scratch_root_accepts_old_config_and_prefers_canonical(tmp_path):
    payload = json.loads(open("config/services.json").read())
    payload["activities"] = {"workspace_root": "old"}
    config = tmp_path / "services.json"
    config.write_text(json.dumps(payload))
    assert load_service_registry(config).activities.workspace_root == tmp_path / "old"
    payload["activities"]["scratch_root"] = "new"
    config.write_text(json.dumps(payload))
    assert load_service_registry(config).activities.workspace_root == tmp_path / "new"


def test_scratch_publication_replaces_legacy_manifest(tmp_path):
    scratch = LocalActivityScratchDirectory(tmp_path)
    legacy = json.dumps({"generator_id": "rtl.generate", "document_id": "spec", "design_id": "top"}).encode()
    canonical = json.dumps({"activity_id": "rtl.generate", "document_id": "spec", "design_id": "top"}).encode()
    options = dict(relative_path="rtl", activity_id="rtl.generate", document_id="spec", design_id="top")
    scratch.replace_directory(files={"generation-manifest.json": legacy}, **options)
    result = scratch.replace_directory(files={"generation-manifest.json": canonical}, **options)
    assert result.relative_path == "rtl"
    assert json.loads((tmp_path / "rtl" / "generation-manifest.json").read_text())["activity_id"] == "rtl.generate"


def test_section_index_accepts_legacy_parent_key():
    from spec2gds.spec.spec_format.sections import SectionIndexEntry

    data = dict(section_id="section_test", section_type="sv", type_version=1,
                owner={"document_id": "spec", "entity_kind": "component", "entity_id": "leaf"},
                path="annotations/entity-sections/sv/section_test.sv",
                media_type="text/x-systemverilog", sha256="sha256:" + "a" * 64)
    entry = SectionIndexEntry.model_validate(data)
    assert entry.parent.entity_id == "leaf"
    assert "parent" in entry.model_dump()
    assert "owner" not in entry.model_dump()


def test_plan_label_migration_preserves_saved_value(tmp_path):
    import sqlite3

    from testplan_service.api.routes_plans import CreatePlanRequest
    from testplan_service.domain.models import PlanHeader
    from testplan_service.storage.sqlite_repo import SqlitePlanRepository

    path = tmp_path / "plans.sqlite3"
    repository = SqlitePlanRepository(path)
    header = PlanHeader(id="plan", name="Test Plan", snapshot_id="snapshot", root_scope_id="root",
                        owner_label="designer", created_at="2026-10-06", updated_at="2026-10-06")
    repository.create_plan(header)
    with sqlite3.connect(path) as connection:
        connection.execute("ALTER TABLE plans RENAME COLUMN designer_label TO owner_label")
    migrated = SqlitePlanRepository(path)
    assert migrated.get_plan("plan").designer_label == "designer"
    with sqlite3.connect(path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(plans)")}
    assert "designer_label" in columns and "owner_label" not in columns
    assert CreatePlanRequest(name="Test Plan", snapshot_id="snapshot", root_scope_id="root",
                             owner_label="legacy designer").designer_label == "legacy designer"


def test_journal_keeps_existing_database_and_names_new_database(tmp_path):
    from spec2gds.spec.spec_format.spec_service_store import SpecServiceJournal

    journal = SpecServiceJournal(str(tmp_path / "new.spec"))
    assert journal.path.name == "spec_service.sqlite3"
    journal.path.rename(journal.path.with_name("owner.sqlite3"))
    reopened = SpecServiceJournal(str(tmp_path / "new.spec"))
    assert reopened.path.name == "owner.sqlite3"
