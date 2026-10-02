"""Managed local workspace output tests for deterministic Activities."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from spec2gds.agent_spec.activities import LocalActivityWorkspace
from spec2gds.agent_spec.activities import workspace as workspace_module


def files(content: str = "first") -> dict[str, bytes]:
    manifest = {
        "generator_id": "tests.generator",
        "document_id": "document_test",
        "design_id": "design_test",
    }
    return {
        "generation-manifest.json": (
            json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode(),
        "include/model.h": content.encode(),
    }


def publish(workspace: LocalActivityWorkspace, content: str = "first"):
    return workspace.replace_directory(
        relative_path="systemc-at/document_test/design_test",
        files=files(content),
        generator_id="tests.generator",
        document_id="document_test",
        design_id="design_test",
    )


def test_workspace_publishes_and_replaces_only_complete_managed_trees(tmp_path: Path) -> None:
    workspace = LocalActivityWorkspace(tmp_path)
    first = publish(workspace)
    target = tmp_path / first.relative_path
    (target / "stale.cpp").write_text("stale")

    second = publish(workspace, "second")

    assert first.relative_path == second.relative_path
    assert first.tree_sha256 != second.tree_sha256
    assert (target / "include/model.h").read_text() == "second"
    assert not (target / "stale.cpp").exists()
    assert [item.path for item in second.files] == [
        "generation-manifest.json",
        "include/model.h",
    ]


def test_workspace_rejects_unsafe_paths_and_unmanaged_targets(tmp_path: Path) -> None:
    workspace = LocalActivityWorkspace(tmp_path)
    with pytest.raises(ValueError, match="Unsafe package path"):
        workspace.replace_directory(
            relative_path="../escape",
            files=files(),
            generator_id="tests.generator",
            document_id="document_test",
            design_id="design_test",
        )

    target = tmp_path / "systemc-at/document_test/design_test"
    target.mkdir(parents=True)
    (target / "user.cpp").write_text("owned by user")
    with pytest.raises(ValueError, match="unmanaged"):
        publish(workspace)
    assert (target / "user.cpp").read_text() == "owned by user"


def test_workspace_rejects_symbolic_links_in_managed_target(tmp_path: Path) -> None:
    workspace = LocalActivityWorkspace(tmp_path)
    publish(workspace)
    target = tmp_path / "systemc-at/document_test/design_test"
    (target / "linked.h").symlink_to(target / "include/model.h")

    with pytest.raises(ValueError, match="symbolic links"):
        publish(workspace, "replacement")

    assert (target / "include/model.h").read_text() == "first"


def test_workspace_restores_previous_tree_when_atomic_commit_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = LocalActivityWorkspace(tmp_path)
    publish(workspace, "original")
    target = tmp_path / "systemc-at/document_test/design_test"
    real_replace = os.replace
    calls = 0

    def fail_new_tree(source: str | Path, destination: str | Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated commit failure")
        real_replace(source, destination)

    monkeypatch.setattr(workspace_module.os, "replace", fail_new_tree)
    with pytest.raises(OSError, match="simulated"):
        publish(workspace, "replacement")

    assert (target / "include/model.h").read_text() == "original"
    assert not list(target.parent.glob(".design_test.stage-*"))
    assert not list(target.parent.glob(".design_test.backup-*"))


def test_readable_collision_numbers_preserve_existing_ownership(tmp_path: Path) -> None:
    workspace = LocalActivityWorkspace(tmp_path)
    first = publish(workspace)
    other_files = files("other")
    manifest = json.loads(other_files["generation-manifest.json"])
    manifest["document_id"] = "another_document"
    other_files["generation-manifest.json"] = json.dumps(manifest).encode()
    second = workspace.replace_directory(relative_path=first.relative_path, files=other_files,
        generator_id="tests.generator", document_id="another_document", design_id="design_test")
    assert second.relative_path == first.relative_path + "-2"
    assert (tmp_path / first.relative_path / "include/model.h").read_text() == "first"
    assert workspace.replace_directory(relative_path=first.relative_path, files=other_files,
        generator_id="tests.generator", document_id="another_document", design_id="design_test").relative_path == second.relative_path


def test_public_migration_checks_ownership_and_never_replaces_a_destination(tmp_path: Path):
    workspace = LocalActivityWorkspace(tmp_path)
    original = publish(workspace)
    options = dict(generator_id="tests.generator", document_id="document_test", design_id="design_test")
    with pytest.raises(ValueError, match="another generation target"):
        workspace.move_owned_directory(original.relative_path, "named/project", **{**options, "document_id": "other"})
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    with pytest.raises(ValueError, match="already exists"):
        workspace.move_owned_directory(original.relative_path, "occupied", **options)
    workspace.move_owned_directory(original.relative_path, "named/project", **options)
    assert (tmp_path / "named/project/include/model.h").read_text() == "first"
    assert not (tmp_path / original.relative_path).exists()


def test_invalid_ownership_cannot_be_treated_as_a_filename_collision(tmp_path: Path):
    workspace = LocalActivityWorkspace(tmp_path)
    original = publish(workspace)
    (tmp_path / original.relative_path / "generation-manifest.json").write_text("{}")
    with pytest.raises(ValueError, match="invalid ownership"):
        publish(workspace, "replacement")
    assert not (tmp_path / (original.relative_path + "-2")).exists()
