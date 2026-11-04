"""Check tutorial navigation, safe preparation, and real consumable source starts."""

from __future__ import annotations

import json
import os
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit
from uuid import uuid4

import pytest

from scripts import build_tutorials
from scripts.prepare_tutorials import ROOT, prepare
from spec2gds.spec.activities import ActivitySnapshot, SpecAccess
from spec2gds.spec.spec_format.archive import SpecPackage
from spec2gds.spec.spec_format.ir import SpecRevision


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []
        self.ids = set()
        self.images = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        if tag in {"a", "img", "script", "link"}:
            target = values.get("href") or values.get("src")
            if target:
                self.targets.append(target)
        if tag == "img":
            assert values.get("alt"), "A tutorial screenshot needs descriptive alternative text."
            self.images.append(values["src"])


def test_tutorial_html_is_current_and_local_navigation_resolves():
    directory = ROOT / "docs/tutorials"
    for name, expected in build_tutorials.pages().items():
        path = directory / name
        assert path.read_text() == expected + "\n", f"Rebuild {name}"
        page = Links()
        page.feed(path.read_text())
        for target in page.targets:
            parts = urlsplit(target)
            if parts.scheme or parts.netloc:
                continue
            destination = (path.parent / unquote(parts.path)).resolve() if parts.path else path
            assert destination.exists(), f"{name}: missing {target}"
            if parts.fragment and destination.suffix == ".html":
                linked = Links()
                linked.feed(destination.read_text())
                assert parts.fragment in linked.ids, f"{name}: missing fragment {target}"
        if name not in {"index.html", "setup.html", "example.html", "validation.html"}:
            assert 2 <= len(page.images) <= 4
            assert {"before", "actions", "check", "practice", "recovery", "continue"} <= page.ids


def test_preparation_refuses_source_directories_and_existing_outputs():
    with pytest.raises(ValueError, match="TEMP_"):
        prepare(ROOT / "docs/tutorials/not-an-output")
    existing = ROOT / "temp" / "TEMP_tutorials" / f"existing-{uuid4().hex}"
    existing.mkdir(parents=True)
    with pytest.raises(FileExistsError, match="refusing to replace"):
        prepare(existing)
    with pytest.raises(ValueError):
        prepare(ROOT.parent / "TEMP_outside_repo")


@pytest.fixture(scope="module")
def tutorial_run():
    directory = ROOT / "temp" / "TEMP_tutorials" / f"test-{uuid4().hex}"
    before = (ROOT / "config/services.json").read_bytes()
    previous = os.environ.get("SPEC2GDS_SERVICE_CONFIG")
    result = prepare(directory)
    assert (ROOT / "config/services.json").read_bytes() == before
    assert os.environ.get("SPEC2GDS_SERVICE_CONFIG") == previous
    return directory, result


def test_prepared_starts_reopen_with_the_required_progression(tutorial_run):
    directory, manifest = tutorial_run
    for name, stage in [("02", 0), ("03", 1), ("04", 2), ("05", 3), ("06", 4), ("07", 5)]:
        revision = SpecRevision.from_package(SpecPackage.load(str(directory / f"{name}-start.spec")))
        assert revision.source_revision_hash == manifest["starts"][name]["source_revision_hash"]
        assert len(revision.components) == (0 if stage == 0 else 1 if stage < 3 else 3)
        assert len(revision.designs) == (1 if stage >= 4 else 0)
        if stage >= 4:
            design = revision.designs[0]
            assert {item.name for item in design.instances} == {"u_add", "u_reg"}
            assert len(design.connections) == (7 if stage == 5 else 0)
        if stage in {1, 2}:
            assert {port.name for port in revision.components[0].ports} == {"a", "b", "y"}
    snapshot = ActivitySnapshot.read(directory / "registered-adder.snapshot")
    assert snapshot.manifest.snapshot_id == manifest["snapshot_id"]
    assert snapshot.target.entity_id == "registered_adder"


def test_starts_are_accepted_by_rtl_tlm_and_verification_consumers(tutorial_run):
    from fastapi.testclient import TestClient
    from testplan_service.api.app import create_app

    from spec2gds.spec.activities.rtl.codegen import generate_project as rtl_project
    from spec2gds.spec.activities.systemc_at.codegen import generate_project as tlm_project

    directory, manifest = tutorial_run
    snapshot = ActivitySnapshot.read(directory / "registered-adder.snapshot")
    design = snapshot.revision.designs[0].ref
    generated = rtl_project(SpecAccess(snapshot.revision), design)
    assert any(b"assign y = a + b;" in data for data in generated.files.values())
    assert any(b"always_ff" in data for data in generated.files.values())
    tlm_source = SpecRevision.from_package(SpecPackage.load(str(directory / "tlm-start.spec")))
    tlm = tlm_project(SpecAccess(tlm_source), tlm_source.designs[0].ref)
    assert tlm.connection_count == 1
    assert any(b".bind(" in data for data in tlm.files.values())

    with TestClient(create_app(storage_dir=directory / "verification/planner-data")) as client:
        base = "/api/verification/v1"
        starts = manifest["verification"]["starts"]
        for name, count in [("plan", 0), ("coverage", 1), ("evidence", 2), ("implementation", 2)]:
            plan = starts[name]["plan_id"]
            response = client.get(f"{base}/plans/{plan}/checkpoints")
            assert response.is_success
            assert len(response.json()) == count
        plan = starts["implementation"]
        preview = client.post(f"{base}/plans/{plan['plan_id']}/checkpoints/preview", json={
            "layer": "implementation", "upstream_checkpoint_id": plan["c1"],
        })
        assert preview.is_success
        assert preview.json()["blockers"] == []
        synthetic = json.loads((directory / "verification/synthetic-results.json").read_text())
        assert synthetic["producer"]["tool_name"].startswith("synthetic")
        assert synthetic["producer"]["synthetic"] is True
