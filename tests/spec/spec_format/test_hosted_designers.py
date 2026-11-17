"""Real HTTP checks for shared hosting, edit participation and root boundaries."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from spec2gds.spec.spec_format.archive import SpecPackage
from spec2gds.spec.spec_format.edit_access import EditAccessError, SpecEditAccess
from spec2gds.spec.spec_format.hosted_files import SpecFilesystem
from spec2gds.spec.spec_format.spec_service_store import SpecServiceBindings
from spec2gds.spec.spec_format.v1_api import create_app


@pytest.fixture
def hosted(tmp_path, monkeypatch):
    root = tmp_path / "specs"
    root.mkdir()
    monkeypatch.setenv("SPEC_EDITOR_STATE_ROOT", str(tmp_path / "state"))
    with TestClient(create_app(spec_root=root)) as client:
        yield client, root


def selection(snapshot):
    access = snapshot["edit_access"]
    return {"owner_document_key": snapshot["owner_document_key"],
            "edit_context_id": access.get("context_id", ""),
            "edit_participant_id": access.get("participant_id", "")}


def create(client, path, title="Counter", **extra):
    response = client.post("/documents/create", json={"path": path, "title": title, **extra})
    assert response.status_code == 200, response.text
    return response.json()


def rename(client, snapshot, title):
    return client.post("/transactions", params=selection(snapshot), json={
        "expected_source_revision_hash": snapshot["source_revision_hash"],
        "operations": [{"type": "set_document_title", "title": title}],
    })


def test_independent_selections_names_and_explicit_binding(hosted):
    client, root = hosted
    (root / "alice").mkdir(); (root / "bob").mkdir()
    first = create(client, "alice/counter.spec")
    second = create(client, "bob/counter.spec")
    assert first["narrative"]["title"] == second["narrative"]["title"] == "Counter"
    assert client.get("/documents/snapshot").status_code == 400
    assert client.get("/components").status_code == 400
    before = (root / "bob/counter.spec").read_bytes()
    response = rename(client, first, "Alice counter")
    assert response.status_code == 200, response.text
    assert (root / "bob/counter.spec").read_bytes() == before
    assert client.get("/documents/snapshot", params=selection(second)).json()["narrative"]["title"] == "Counter"
    assert {item["relative_path"] for item in client.get("/documents").json()["documents"]} == {"alice/counter.spec", "bob/counter.spec"}


def test_busy_file_is_read_only_and_copy_has_separate_saved_content(hosted):
    client, root = hosted
    first = create(client, "source.spec")
    original = (root / "source.spec").read_bytes()
    second = client.post("/documents/open", json={"path": "source.spec"}).json()
    assert second["edit_access"] == {"mode": "read_only"}
    assert rename(client, second, "Forbidden").status_code == 423
    assert (root / "source.spec").read_bytes() == original
    values = {"source_key": first["owner_document_key"], "expected_source_revision_hash": first["source_revision_hash"],
              "path": "copied.spec", "title": "Counter copy", "request_id": str(uuid4())}
    copied = client.post("/documents/copy", json=values)
    assert copied.status_code == 200, copied.text
    copied = copied.json()
    assert copied["document_id"] == first["document_id"]
    assert copied["owner_document_key"] != first["owner_document_key"]
    assert rename(client, copied, "Independent").status_code == 200
    assert (root / "source.spec").read_bytes() == original
    # Replay survives a later edit to the source and returns the same destination.
    assert rename(client, first, "Changed source").status_code == 200
    replay = client.post("/documents/copy", json=values)
    assert replay.status_code == 200, replay.text
    assert replay.json()["owner_document_key"] == copied["owner_document_key"]
    assert not any(path.startswith("activity/") for path in SpecPackage.load(str(root / "copied.spec")).files)


def test_creation_replay_does_not_replace_a_file_or_lose_access(hosted):
    client, root = hosted
    request_id = str(uuid4())
    first = create(client, "one.spec", request_id=request_id)
    before = (root / "one.spec").read_bytes()
    replay = create(client, "one.spec", request_id=request_id)
    assert replay["edit_access"] == first["edit_access"] or replay["edit_access"]["context_id"] == first["edit_access"]["context_id"]
    assert (root / "one.spec").read_bytes() == before
    assert client.post("/documents/create", json={"path": "one.spec", "title": "Replacement"}).status_code == 422


def test_copy_suggestion_uses_available_directory_name(hosted):
    client, root = hosted
    source = create(client, "counter.spec")
    create(client, "counter-copy.spec", title="Counter copy")
    suggestion = client.get("/documents/copy-suggestion", params=selection(source))
    assert suggestion.status_code == 200, suggestion.text
    values = suggestion.json()
    assert Path(values["path"]) == root / "counter-copy-2.spec"
    assert values["title"] != "Counter copy"
    response = client.post("/documents/copy", json={
        **values, "source_key": source["owner_document_key"],
        "expected_source_revision_hash": source["source_revision_hash"], "request_id": str(uuid4()),
    })
    assert response.status_code == 200, response.text


def test_unopened_file_reserves_its_directory_name(hosted):
    client, root = hosted
    SpecPackage.create(title="Existing name").save(str(root / "unopened.spec"))
    response = client.post("/documents/create", json={"path": "new.spec", "title": "Existing name"})
    assert response.status_code == 422
    assert not (root / "new.spec").exists()


def test_picker_and_direct_requests_cannot_escape_root(hosted, tmp_path):
    client, root = hosted
    listing = client.get("/filesystem/directories").json()
    assert listing["parent"] is None and listing["roots"] == [str(root)] and listing["home"] == str(root)
    outside = tmp_path / "outside"; outside.mkdir()
    SpecPackage.create(title="Outside").save(str(outside / "secret.spec"))
    (root / "link").symlink_to(outside, target_is_directory=True)
    (root / "alias.spec").symlink_to(outside / "secret.spec")
    (root / "directory.spec").mkdir()
    assert client.get("/filesystem/directories", params={"path": "link"}).status_code == 422
    assert "link" not in [item["name"] for item in client.get("/filesystem/directories").json()["directories"]]
    for path in ["../outside/secret.spec", str(outside / "secret.spec"), "link/secret.spec", "alias.spec", "directory.spec"]:
        assert client.post("/documents/open", json={"path": path}).status_code == 422
    for parent in [str(outside), "../outside", "link"]:
        assert client.post("/filesystem/directories", json={"parent": parent, "name": "new"}).status_code == 422
    assert not (outside / "new").exists()
    response = client.post("/documents/create", json={"path": "bad.spec", "title": "Bad", "sidecar_root": str(outside)})
    assert response.status_code == 422 and not (root / "bad.spec").exists()


def test_stored_binding_and_changed_parent_link_cannot_bypass_root(hosted, tmp_path):
    client, root = hosted
    (root / "child").mkdir()
    opened = create(client, "child/work.spec")
    outside = tmp_path / "elsewhere"; outside.mkdir()
    (root / "child").rename(root / "old-child")
    (root / "child").symlink_to(outside, target_is_directory=True)
    assert client.get("/documents/view", params=selection(opened)).status_code in {404, 409}
    assert rename(client, opened, "Changed").status_code in {404, 409}
    assert list(outside.iterdir()) == []


def test_ten_clients_keep_files_and_edit_contexts_separate(hosted):
    client, root = hosted
    def edit(index):
        (root / f"designer-{index}").mkdir()
        snapshot = create(client, f"designer-{index}/work.spec")
        response = rename(client, snapshot, f"Design {index}")
        assert response.status_code == 200, response.text
        return snapshot["owner_document_key"], snapshot["edit_access"]["context_id"]
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(edit, range(10)))
    assert len({key for key, _ in results}) == len({context for _, context in results}) == 10
    for index in range(10):
        assert SpecPackage.load(str(root / f"designer-{index}/work.spec")).narrative.title == f"Design {index}"


def test_lease_participation_expiry_fencing_and_restart(tmp_path):
    clock = [100.0]
    access = SpecEditAccess(tmp_path / "access.db", now=lambda: clock[0])
    first = access.acquire("file")
    linked = access.acquire("file", first["context_id"], "circuit")
    access.release("file", first["context_id"], first["participant_id"])
    assert access.acquire("file")["mode"] == "read_only"
    clock[0] += 250
    access.renew("file", linked["context_id"], "circuit")
    restarted = SpecEditAccess(tmp_path / "access.db", now=lambda: clock[0])
    assert restarted.acquire("file")["mode"] == "read_only"
    clock[0] += 301
    successor = restarted.acquire("file")
    assert successor["context_id"] != first["context_id"]
    with pytest.raises(EditAccessError):
        restarted.renew("file", first["context_id"], "circuit")
    with pytest.raises(EditAccessError):
        with restarted.guard("file", first["context_id"], "circuit"):
            pytest.fail("Stale context entered a write")


def test_file_publication_is_exclusive_and_directory_names_are_local(tmp_path):
    filesystem = SpecFilesystem(tmp_path)
    package = SpecPackage.create(title="Counter")
    filesystem.publish("one.spec", package.to_bytes())
    with pytest.raises(FileExistsError):
        filesystem.publish("one.spec", package.to_bytes())
    (tmp_path / "a").mkdir(); (tmp_path / "b").mkdir()
    bindings = SpecServiceBindings(tmp_path / "state")
    for directory in ("a", "b"):
        path = str(tmp_path / directory / "work.spec")
        with bindings.reserve_name(path, directory, "Counter"):
            filesystem.publish(path, SpecPackage.create(directory, title="Counter").to_bytes())
    with pytest.raises(ValueError):
        with bindings.reserve_name(str(tmp_path / "a/other.spec"), "other", "Counter"):
            pass


def test_end_session_releases_all_applications_and_fences_late_requests(hosted):
    client, root = hosted
    saved = client.post("/documents/create", json={"path": str(root / "handoff.spec"), "title": "Handoff"}).json()
    key = saved["owner_document_key"]
    query = {"owner_document_key": key}
    first = saved["edit_access"]
    child = client.post("/documents/edit-access/acquire", params=query, json={"context_id": first["context_id"], "participant_id": "circuit:linked"}).json()
    source = (root / "handoff.spec").read_bytes()
    closed = client.post("/documents/edit-access/end-session", params=query, json=first)
    assert closed.status_code == 200
    for participant in (first, child):
        assert client.post("/documents/edit-access/renew", params=query, json=participant).status_code == 423
        headers = {"X-Spec-Edit-Context": participant["context_id"], "X-Spec-Participant": participant["participant_id"]}
        assert client.post("/transactions", params=query, headers=headers, json={"expected_source_revision_hash": saved["source_revision_hash"], "operations": [{"type": "set_document_title", "title": "Late linked write"}]}).status_code == 423
    next_access = client.post("/documents/edit-access/acquire", params=query, json={}).json()
    assert next_access["mode"] == "edit"
    assert next_access["context_id"] != first["context_id"]
    assert client.post("/documents/edit-access/end-session", params=query, json=first).status_code == 200
    assert client.post("/documents/edit-access/renew", params=query, json=next_access).status_code == 200
    assert client.post("/documents/edit-access/acquire", params=query, json=child).json()["mode"] == "read_only"
    headers = {"X-Spec-Edit-Context": first["context_id"], "X-Spec-Participant": first["participant_id"]}
    assert client.post("/transactions", params=query, headers=headers, json={"expected_source_revision_hash": saved["source_revision_hash"], "operations": [{"type": "set_document_title", "title": "Late write"}]}).status_code == 423
    assert (root / "handoff.spec").read_bytes() == source


def test_read_only_close_cannot_revoke_an_editing_context(hosted):
    client, root = hosted
    saved = client.post("/documents/create", json={"path": str(root / "read_only.spec"), "title": "Read only close"}).json()
    query = {"owner_document_key": saved["owner_document_key"]}
    grant = saved["edit_access"]
    assert client.post("/documents/edit-access/acquire", params=query, json={}).json()["mode"] == "read_only"
    assert client.post("/documents/edit-access/end-session", params=query, json={}).status_code == 423
    assert client.post("/documents/edit-access/renew", params=query, json=grant).status_code == 200
