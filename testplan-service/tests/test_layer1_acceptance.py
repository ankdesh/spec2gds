"""Acceptance test suite for Verification Planner Layer 1 (Test Plan).

Implements L1-01 through L1-15 test scenarios per docs/verification-planner.md.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from testplan_service.api.app import create_app
from testplan_service.domain.enums import (
    AuthoringState,
    Priority,
    RequirementDisposition,
    SourceAuditDisposition,
)
from testplan_service.fixtures.fifo_snapshot import (
    get_fifo_snapshot_bytes,
    get_modified_fifo_snapshot_bytes,
)
from testplan_service.fixtures.two_fifo_snapshot import (
    get_renamed_two_fifo_snapshot_bytes,
    get_two_fifo_snapshot_bytes,
)


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(storage_dir=tmp_path / "verification_data")
    return TestClient(app)


def test_l1_01_empty_intent_plan_on_snapshot_import(client: TestClient) -> None:
    """L1-01: Import valid FIFO snapshot; no authoring calls.

    Expected: Empty intent plan with browsable source; no generated requirements.
    """
    snapshot_bytes = get_fifo_snapshot_bytes()
    imp_res = client.post("/api/verification/v1/source-imports", content=snapshot_bytes)
    assert imp_res.status_code == 201
    snap_data = imp_res.json()
    snapshot_id = snap_data["snapshot_id"]
    assert snapshot_id.startswith("sha256:")
    assert snap_data["source_sections_count"] == 8

    # Create plan
    plan_res = client.post(
        "/api/verification/v1/plans",
        json={
            "name": "FIFO Verification Plan",
            "snapshot_id": snapshot_id,
            "root_scope_id": "sync_fifo",
            "description": "Verification plan for synchronous FIFO component",
        },
    )
    assert plan_res.status_code == 201
    plan_id = plan_res.json()["id"]

    # Read records: must be empty (no automatic requirement extraction)
    recs_res = client.get(f"/api/verification/v1/plans/{plan_id}/records")
    assert recs_res.status_code == 200
    assert len(recs_res.json()) == 0

    # Source sections must be browsable
    sec_res = client.get(f"/api/verification/v1/plans/{plan_id}/source-sections")
    assert sec_res.status_code == 200
    sections = sec_res.json()
    assert len(sections) == 8
    for s in sections:
        assert s["audit"]["disposition"] == "unreviewed"


def test_l1_02_create_section_and_draft_intent_diagnostics(client: TestClient) -> None:
    """L1-02: Create section and incomplete intent via API.

    Expected: Save succeeds as draft; exact missing fields appear.
    """
    snap_res = client.post("/api/verification/v1/source-imports", content=get_fifo_snapshot_bytes())
    snap_id = snap_res.json()["snapshot_id"]

    plan_res = client.post(
        "/api/verification/v1/plans",
        json={"name": "Draft Plan", "snapshot_id": snap_id, "root_scope_id": "sync_fifo"},
    )
    plan_id = plan_res.json()["id"]

    # Create section and incomplete draft intent
    cmd_res = client.post(
        f"/api/verification/v1/plans/{plan_id}/commands",
        json={
            "base_edit_revision": 1,
            "request_id": "req-l1-02",
            "operations": [
                {
                    "op": "section.create",
                    "id": "sec-reset",
                    "title": "Reset",
                    "scope_id": "sync_fifo",
                },
                {
                    "op": "intent.create",
                    "id": "int-draft-1",
                    "title": "Incomplete Reset Intent",
                    "scope_id": "sync_fifo",
                    "parent_section_id": "sec-reset",
                    "authoring_state": "draft",
                    # Given/When/Then and observations deliberately omitted
                },
            ],
        },
    )
    assert cmd_res.status_code == 200
    resp_data = cmd_res.json()
    assert resp_data["edit_revision"] == 2
    assert len(resp_data["changed_records"]) == 2

    # Intent is draft
    intent = client.get(f"/api/verification/v1/plans/{plan_id}/records/int-draft-1").json()
    assert intent["authoring_state"] == "draft"

    # Attempting to mark ready directly fails with exact missing field diagnostics
    ready_cmd_res = client.post(
        f"/api/verification/v1/plans/{plan_id}/commands",
        json={
            "base_edit_revision": 2,
            "request_id": "req-l1-02-ready",
            "operations": [
                {"op": "intent.set_state", "id": "int-draft-1", "state": "ready"}
            ],
        },
    )
    assert ready_cmd_res.status_code == 422
    err_body = ready_cmd_res.json()
    diagnostics = err_body["details"]["diagnostics"]
    error_codes = {d["code"] for d in diagnostics}
    assert "intent.missing_preconditions" in error_codes
    assert "intent.missing_trigger" in error_codes
    assert "intent.missing_expected_behavior" in error_codes
    assert "intent.missing_observations" in error_codes
    assert "intent.no_verifiable_requirement" in error_codes


def test_l1_03_and_l1_05_fifo_complete_fixture_and_checkpoint(client: TestClient) -> None:
    """L1-03 & L1-05: Author 8 requirements and 12 intents for Synchronous FIFO, and create P1 checkpoint."""
    snap_res = client.post("/api/verification/v1/source-imports", content=get_fifo_snapshot_bytes())
    snap_id = snap_res.json()["snapshot_id"]
    plan_res = client.post(
        "/api/verification/v1/plans",
        json={"name": "FIFO Golden Plan", "snapshot_id": snap_id, "root_scope_id": "sync_fifo"},
    )
    plan_id = plan_res.json()["id"]

    # 1. Author 8 requirements
    req_specs = [
        ("req-reset", "REQ-reset", "Reset behavior", "Reset clears queue and sets flags", "sec-reset"),
        ("req-write", "REQ-write", "Accepted write", "Write appends one word when space available", "sec-write"),
        ("req-read", "REQ-read", "Accepted read", "Read returns oldest word when data available", "sec-read"),
        ("req-full", "REQ-full", "Full write rejection", "Full write preserves occupancy and data", "sec-full"),
        ("req-empty", "REQ-empty", "Empty read rejection", "Empty read preserves queue and output", "sec-empty"),
        ("req-both", "REQ-both", "Simultaneous requests", "Mid-occupancy accepts both; full read only; empty write only", "sec-both"),
        ("req-order", "REQ-order", "Sequence retention", "Ordering survives wrap-around without data loss", "sec-order"),
        ("req-flags", "REQ-flags", "Flag consistency", "Full and empty agree with occupancy count", "sec-flags"),
    ]

    req_ops = [
        {
            "op": "requirement.create",
            "id": r_id,
            "title": title,
            "statement": stmt,
            "scope_id": "sync_fifo",
            "disposition": "verify",
            "source_locators": [
                {
                    "snapshot_id": snap_id,
                    "entity_ref": {"document_id": "fifo_spec", "entity_kind": "component", "entity_id": "sync_fifo"},
                    "section_id": sec_id,
                    "text_range": [0, len(stmt)],
                    "quoted_text": stmt,
                    "section_digest": "digest",
                }
            ],
        }
        for r_id, key, title, stmt, sec_id in req_specs
    ]

    # Audit all 8 sections
    audit_ops = [
        {
            "op": "source_section.assess",
            "section_id": sec_id,
            "disposition": "requirements_captured",
            "requirement_ids": [r_id],
        }
        for r_id, key, title, stmt, sec_id in req_specs
    ]

    res = client.post(
        f"/api/verification/v1/plans/{plan_id}/commands",
        json={"base_edit_revision": 1, "request_id": "req-batch-1", "operations": req_ops + audit_ops},
    )
    assert res.status_code == 200

    # 2. Author 6 sections
    sec_specs = [
        ("sec-reset", "Reset"),
        ("sec-normal", "Normal operation"),
        ("sec-boundaries", "Boundaries"),
        ("sec-simultaneous", "Simultaneous requests"),
        ("sec-ordering", "Ordering"),
        ("sec-status", "Status"),
    ]
    sec_ops = [
        {"op": "section.create", "id": s_id, "title": s_title, "scope_id": "sync_fifo"}
        for s_id, s_title in sec_specs
    ]

    res = client.post(
        f"/api/verification/v1/plans/{plan_id}/commands",
        json={"base_edit_revision": 2, "request_id": "req-batch-2", "operations": sec_ops},
    )
    assert res.status_code == 200

    # 3. Author 12 intents
    intent_specs = [
        # Reset (2)
        ("int-rst-1", "sec-reset", "Reset clears queue", ["req-reset"]),
        ("int-rst-2", "sec-reset", "Reset overrides simultaneous requests", ["req-reset"]),
        # Normal (2)
        ("int-wr-1", "sec-normal", "Write appends one word when space available", ["req-write"]),
        ("int-rd-1", "sec-normal", "Read returns oldest word when data available", ["req-read"]),
        # Boundaries (3)
        ("int-full-1", "sec-boundaries", "Full write preserves occupancy", ["req-full"]),
        ("int-full-2", "sec-boundaries", "Full write preserves queued data", ["req-full"]),
        ("int-empty-1", "sec-boundaries", "Empty read preserves queue and output", ["req-empty"]),
        # Simultaneous (3)
        ("int-both-1", "sec-simultaneous", "Mid-occupancy accepts both read and write", ["req-both"]),
        ("int-both-2", "sec-simultaneous", "Full accepts read only", ["req-both"]),
        ("int-both-3", "sec-simultaneous", "Empty accepts write only", ["req-both"]),
        # Ordering (1)
        ("int-order-1", "sec-ordering", "Ordering survives wrap-around", ["req-order"]),
        # Status (1)
        ("int-flags-1", "sec-status", "Full and empty agree with occupancy", ["req-flags"]),
    ]

    intent_ops = [
        {
            "op": "intent.create",
            "id": i_id,
            "title": title,
            "scope_id": "sync_fifo",
            "parent_section_id": sec_id,
            "requirement_ids": r_ids,
            "preconditions": "Reset is inactive; initial state configured.",
            "trigger": "Input signals evaluated on rising clock edge.",
            "expected_behavior": "Outputs and internal count update according to spec.",
            "observations": [{"name": "Queue Output", "description": "dout and status flags."}],
            "authoring_state": "ready",
        }
        for i_id, sec_id, title, r_ids in intent_specs
    ]

    res = client.post(
        f"/api/verification/v1/plans/{plan_id}/commands",
        json={"base_edit_revision": 3, "request_id": "req-batch-3", "operations": intent_ops},
    )
    assert res.status_code == 200

    # Preview checkpoint: 0 blockers!
    preview_res = client.post(f"/api/verification/v1/plans/{plan_id}/checkpoints/preview")
    assert preview_res.status_code == 200
    preview = preview_res.json()
    assert len(preview["blockers"]) == 0
    assert preview["checklist"]["intents_total"] == 12
    assert preview["checklist"]["intents_ready"] == 12
    assert preview["checklist"]["verifiable_requirements"] == 8

    # Create P1 Checkpoint
    chk_res = client.post(
        f"/api/verification/v1/plans/{plan_id}/checkpoints",
        json={
            "reviewer_label": "lead_verifier",
            "comment": "Complete Synchronous FIFO plan reviewed.",
            "expected_digest": preview["candidate_digest"],
            "acknowledged_warnings": [],
        },
    )
    assert chk_res.status_code == 201
    chk = chk_res.json()
    assert chk["key"] == "P-1" or chk["key"].startswith("P")
    assert chk["layer"] == "plan"


def test_l1_04_review_blocked_by_unmapped_requirement_or_unreviewed_section(client: TestClient) -> None:
    """L1-04: Review with one unmapped requirement or unreviewed source section is blocked."""
    snap_res = client.post("/api/verification/v1/source-imports", content=get_fifo_snapshot_bytes())
    snap_id = snap_res.json()["snapshot_id"]
    plan_res = client.post(
        "/api/verification/v1/plans",
        json={"name": "Incomplete Review Plan", "snapshot_id": snap_id, "root_scope_id": "sync_fifo"},
    )
    plan_id = plan_res.json()["id"]

    # Preview with unreviewed sections
    preview_res = client.post(f"/api/verification/v1/plans/{plan_id}/checkpoints/preview")
    assert preview_res.status_code == 200
    preview = preview_res.json()
    assert len(preview["blockers"]) > 0

    # Attempting to commit checkpoint raises 422
    chk_res = client.post(
        f"/api/verification/v1/plans/{plan_id}/checkpoints",
        json={"reviewer_label": "verifier", "comment": "premature review"},
    )
    assert chk_res.status_code == 422
    assert "unresolved blockers exist" in chk_res.json()["message"]


def test_l1_06_many_to_many_requirement_intent_linking(client: TestClient) -> None:
    """L1-06: Link one intent to two requirements and one requirement to two intents."""
    snap_res = client.post("/api/verification/v1/source-imports", content=get_fifo_snapshot_bytes())
    snap_id = snap_res.json()["snapshot_id"]
    plan_res = client.post(
        "/api/verification/v1/plans",
        json={"name": "M-to-N Plan", "snapshot_id": snap_id, "root_scope_id": "sync_fifo"},
    )
    plan_id = plan_res.json()["id"]

    cmd_res = client.post(
        f"/api/verification/v1/plans/{plan_id}/commands",
        json={
            "base_edit_revision": 1,
            "request_id": "m-to-n-req",
            "operations": [
                {
                    "op": "requirement.create",
                    "id": "req-1",
                    "title": "Req 1",
                    "statement": "Statement 1",
                    "scope_id": "sync_fifo",
                    "source_locators": [
                        {
                            "snapshot_id": snap_id,
                            "entity_ref": {"document_id": "fifo_spec", "entity_kind": "component", "entity_id": "sync_fifo"},
                            "section_id": "sec-reset",
                            "text_range": [0, 10],
                            "quoted_text": "text",
                            "section_digest": "digest",
                        }
                    ],
                },
                {
                    "op": "requirement.create",
                    "id": "req-2",
                    "title": "Req 2",
                    "statement": "Statement 2",
                    "scope_id": "sync_fifo",
                    "source_locators": [
                        {
                            "snapshot_id": snap_id,
                            "entity_ref": {"document_id": "fifo_spec", "entity_kind": "component", "entity_id": "sync_fifo"},
                            "section_id": "sec-write",
                            "text_range": [0, 10],
                            "quoted_text": "text",
                            "section_digest": "digest",
                        }
                    ],
                },
                {
                    "op": "intent.create",
                    "id": "int-1",
                    "title": "Intent 1",
                    "scope_id": "sync_fifo",
                    "requirement_ids": ["req-1", "req-2"],  # Intent 1 links to Req 1 and Req 2
                },
                {
                    "op": "intent.create",
                    "id": "int-2",
                    "title": "Intent 2",
                    "scope_id": "sync_fifo",
                    "requirement_ids": ["req-1"],  # Req 1 also links to Intent 2
                },
            ],
        },
    )
    assert cmd_res.status_code == 200

    # Verify requirements endpoint shows mapped intent counts
    reqs_res = client.get(f"/api/verification/v1/plans/{plan_id}/requirements")
    assert reqs_res.status_code == 200
    req_map = {r["id"]: r for r in reqs_res.json()}
    assert req_map["req-1"]["linked_intent_count"] == 2
    assert req_map["req-2"]["linked_intent_count"] == 1


def test_l1_07_cycle_rejection_no_revision_increment(client: TestClient) -> None:
    """L1-07: Attempt section/dependency cycle; atomic rejection with field diagnostics and no revision increment."""
    snap_res = client.post("/api/verification/v1/source-imports", content=get_fifo_snapshot_bytes())
    snap_id = snap_res.json()["snapshot_id"]
    plan_res = client.post(
        "/api/verification/v1/plans",
        json={"name": "Cycle Test Plan", "snapshot_id": snap_id, "root_scope_id": "sync_fifo"},
    )
    plan_id = plan_res.json()["id"]

    # 1. Create sections A and B
    client.post(
        f"/api/verification/v1/plans/{plan_id}/commands",
        json={
            "base_edit_revision": 1,
            "request_id": "setup-sections",
            "operations": [
                {"op": "section.create", "id": "sec-a", "title": "Section A", "scope_id": "sync_fifo"},
                {"op": "section.create", "id": "sec-b", "title": "Section B", "scope_id": "sync_fifo", "parent_section_id": "sec-a"},
            ],
        },
    )

    # 2. Attempt to move sec-a under sec-b (creating cycle)
    cycle_res = client.post(
        f"/api/verification/v1/plans/{plan_id}/commands",
        json={
            "base_edit_revision": 2,
            "request_id": "cycle-attempt",
            "operations": [
                {"op": "item.move", "id": "sec-a", "target_scope_id": "sync_fifo", "parent_section_id": "sec-b"}
            ],
        },
    )
    assert cycle_res.status_code == 422
    assert "cycle_detected" in cycle_res.text

    # Plan revision remains at 2 (no increment on failure!)
    plan = client.get(f"/api/verification/v1/plans/{plan_id}").json()["plan"]
    assert plan["edit_revision"] == 2


def test_l1_08_copy_section_to_another_occurrence(client: TestClient) -> None:
    """L1-08: Copy section to another occurrence. New identities and draft states; no evidence copied."""
    snap_res = client.post("/api/verification/v1/source-imports", content=get_two_fifo_snapshot_bytes())
    snap_id = snap_res.json()["snapshot_id"]
    plan_res = client.post(
        "/api/verification/v1/plans",
        json={"name": "Pipeline Copy Plan", "snapshot_id": snap_id, "root_scope_id": "fifo_pipeline"},
    )
    plan_id = plan_res.json()["id"]

    # Create section and intent under ingress
    client.post(
        f"/api/verification/v1/plans/{plan_id}/commands",
        json={
            "base_edit_revision": 1,
            "request_id": "create-ingress-sec",
            "operations": [
                {"op": "section.create", "id": "sec-ingress-reset", "title": "Ingress Reset", "scope_id": "ingress"},
                {
                    "op": "intent.create",
                    "id": "int-ingress-reset-1",
                    "title": "Reset clears ingress queue",
                    "scope_id": "ingress",
                    "parent_section_id": "sec-ingress-reset",
                },
            ],
        },
    )

    # Copy section to egress occurrence
    copy_res = client.post(
        f"/api/verification/v1/plans/{plan_id}/commands",
        json={
            "base_edit_revision": 2,
            "request_id": "copy-to-egress",
            "operations": [
                {"op": "section.copy", "source_id": "sec-ingress-reset", "target_scope_id": "egress"}
            ],
        },
    )
    assert copy_res.status_code == 200
    changed = copy_res.json()["changed_records"]
    copied_sec = next(r for r in changed if r["record_type"] == "section")
    copied_int = next(r for r in changed if r["record_type"] == "intent")

    assert copied_sec["id"] != "sec-ingress-reset"
    assert copied_sec["scope_id"] == "egress"
    assert copied_sec["copied_from"] == "sec-ingress-reset"

    assert copied_int["id"] != "int-ingress-reset-1"
    assert copied_int["scope_id"] == "egress"
    assert copied_int["authoring_state"] == "draft"


def test_l1_09_two_fifo_design_28_intents_fixture(client: TestClient) -> None:
    """L1-09: Create two-FIFO fixture: exactly 28 intents (24 component + 4 composition at design root)."""
    snap_res = client.post("/api/verification/v1/source-imports", content=get_two_fifo_snapshot_bytes())
    snap_id = snap_res.json()["snapshot_id"]
    plan_res = client.post(
        "/api/verification/v1/plans",
        json={"name": "Two-FIFO System Plan", "snapshot_id": snap_id, "root_scope_id": "fifo_pipeline"},
    )
    plan_id = plan_res.json()["id"]

    # 12 component intents in ingress
    ingress_intents = [
        {
            "op": "intent.create",
            "id": f"int-ing-{i}",
            "title": f"Ingress Intent {i}",
            "scope_id": "ingress",
        }
        for i in range(1, 13)
    ]

    # 12 component intents in egress
    egress_intents = [
        {
            "op": "intent.create",
            "id": f"int-egr-{i}",
            "title": f"Egress Intent {i}",
            "scope_id": "egress",
        }
        for i in range(1, 13)
    ]

    # 4 design composition intents
    composition_intents = [
        {
            "op": "intent.create",
            "id": "int-comp-1",
            "title": "End-to-end ordering across both FIFOs",
            "scope_id": "fifo_pipeline",
            "participants": ["ingress", "egress"],
        },
        {
            "op": "intent.create",
            "id": "int-comp-2",
            "title": "Stalled egress preserves held bridge word",
            "scope_id": "fifo_pipeline",
            "participants": ["ingress", "egress"],
        },
        {
            "op": "intent.create",
            "id": "int-comp-3",
            "title": "Bridge never reads ingress while holding data",
            "scope_id": "fifo_pipeline",
            "participants": ["ingress", "egress"],
        },
        {
            "op": "intent.create",
            "id": "int-comp-4",
            "title": "Reset clears all pending data in bridge and queues",
            "scope_id": "fifo_pipeline",
            "participants": ["ingress", "egress"],
        },
    ]

    res = client.post(
        f"/api/verification/v1/plans/{plan_id}/commands",
        json={
            "base_edit_revision": 1,
            "request_id": "two-fifo-all-intents",
            "operations": ingress_intents + egress_intents + composition_intents,
        },
    )
    assert res.status_code == 200

    # Total intents must be exactly 28!
    records = client.get(f"/api/verification/v1/plans/{plan_id}/records?record_type=intent").json()
    assert len(records) == 28

    # Filter by scope
    ingress_recs = client.get(f"/api/verification/v1/plans/{plan_id}/records?record_type=intent&scope_id=ingress").json()
    assert len(ingress_recs) == 12

    comp_recs = client.get(f"/api/verification/v1/plans/{plan_id}/records?record_type=intent&scope_id=fifo_pipeline").json()
    assert len(comp_recs) == 4


def test_l1_10_source_change_preview_and_p1_preservation(client: TestClient) -> None:
    """L1-10: Change source quote with same section ID, then preview update.

    Expected: Affected requirements/intents marked for review; old P1 and source remain readable.
    """
    # 1. Setup plan with initial FIFO snapshot S1
    s1_bytes = get_fifo_snapshot_bytes()
    s1_res = client.post("/api/verification/v1/source-imports", content=s1_bytes)
    s1_id = s1_res.json()["snapshot_id"]

    plan_res = client.post(
        "/api/verification/v1/plans",
        json={"name": "Source Update Plan", "snapshot_id": s1_id, "root_scope_id": "sync_fifo"},
    )
    plan_id = plan_res.json()["id"]

    # 2. Create requirement citing sec-reset and ready intent linking to it
    client.post(
        f"/api/verification/v1/plans/{plan_id}/commands",
        json={
            "base_edit_revision": 1,
            "request_id": "setup-s1-plan",
            "operations": [
                {
                    "op": "requirement.create",
                    "id": "req-reset",
                    "title": "Reset Behavior",
                    "statement": "Reset clears queue",
                    "scope_id": "sync_fifo",
                    "disposition": "verify",
                    "source_locators": [
                        {
                            "snapshot_id": s1_id,
                            "entity_ref": {"document_id": "fifo_spec", "entity_kind": "component", "entity_id": "sync_fifo"},
                            "section_id": "sec-reset",
                            "text_range": [0, 10],
                            "quoted_text": "Reset: Reset clears",
                            "section_digest": "dummy",
                        }
                    ],
                },
                {
                    "op": "section.create",
                    "id": "sec-reset-cat",
                    "title": "Reset Category",
                    "scope_id": "sync_fifo",
                },
                {
                    "op": "intent.create",
                    "id": "int-reset",
                    "title": "Reset clears FIFO",
                    "scope_id": "sync_fifo",
                    "parent_section_id": "sec-reset-cat",
                    "requirement_ids": ["req-reset"],
                    "preconditions": "FIFO has data; reset asserted.",
                    "trigger": "Rising clock edge.",
                    "expected_behavior": "Queue empty; count=0.",
                    "observations": [{"name": "Count", "description": "Count is zero."}],
                    "authoring_state": "ready",
                },
            ],
        },
    )

    # 3. Assess all source sections and create checkpoint P1
    sec_res = client.get(f"/api/verification/v1/plans/{plan_id}/source-sections").json()
    assess_ops = []
    for s in sec_res:
        assess_ops.append({
            "op": "source_section.assess",
            "section_id": s["section_id"],
            "disposition": "requirements_captured" if s["section_id"] == "sec-reset" else "informational",
            "requirement_ids": ["req-reset"] if s["section_id"] == "sec-reset" else [],
            "reason": "Reviewed",
        })
    client.post(
        f"/api/verification/v1/plans/{plan_id}/commands",
        json={"base_edit_revision": 2, "request_id": "audit-sections", "operations": assess_ops},
    )

    p1_res = client.post(f"/api/verification/v1/plans/{plan_id}/checkpoints", json={"reviewer_label": "lead"})
    assert p1_res.status_code == 201
    p1 = p1_res.json()
    p1_id = p1["id"]
    assert p1["snapshot_id"] == s1_id

    # 4. Upload modified snapshot S2 (updated reset narrative text)
    s2_bytes = get_modified_fifo_snapshot_bytes()
    s2_res = client.post("/api/verification/v1/source-imports", content=s2_bytes)
    assert s2_res.status_code == 201
    s2_id = s2_res.json()["snapshot_id"]
    assert s2_id != s1_id

    # 5. Preview source update: verify affected requirements and intents diagnostics
    preview_res = client.post(
        f"/api/verification/v1/plans/{plan_id}/commands?preview=true",
        json={
            "base_edit_revision": 3,
            "request_id": "preview-source-update",
            "operations": [{"op": "source.update", "staged_import_id": s2_id}],
        },
    )
    assert preview_res.status_code == 200
    p_data = preview_res.json()
    assert p_data["edit_revision"] == 3  # not committed yet
    diagnostics = p_data["diagnostics"]
    diag_codes = [d["code"] for d in diagnostics]
    assert "source.changed" in diag_codes
    assert "intent.source_changed" in diag_codes

    # 6. Execute source update
    commit_res = client.post(
        f"/api/verification/v1/plans/{plan_id}/commands",
        json={
            "base_edit_revision": 3,
            "request_id": "commit-source-update",
            "operations": [{"op": "source.update", "staged_import_id": s2_id}],
        },
    )
    assert commit_res.status_code == 200
    assert commit_res.json()["edit_revision"] == 4

    # The working intent has been reset to draft because its cited source changed!
    curr_intent = client.get(f"/api/verification/v1/plans/{plan_id}/records/int-reset").json()
    assert curr_intent["authoring_state"] == "draft"

    # 7. Old P1 checkpoint and old snapshot remain readable and preserved
    old_p1_res = client.get(f"/api/verification/v1/plans/{plan_id}/checkpoints/{p1_id}")
    assert old_p1_res.status_code == 200
    old_p1_data = old_p1_res.json()
    assert old_p1_data["snapshot_id"] == s1_id
    # Intent in old checkpoint remains ready
    frozen_int = next(r for r in old_p1_data["payload"]["intents"] if r["id"] == "int-reset")
    assert frozen_int["authoring_state"] == "ready"

    # Old source sections from checkpoint snapshot remain accessible
    chk_sec_res = client.get(f"/api/verification/v1/plans/{plan_id}/checkpoints/{p1_id}/source-sections")
    assert chk_sec_res.status_code == 200
    assert len(chk_sec_res.json()) == 8


def test_l1_11_rename_occurrence_with_stable_ids(client: TestClient) -> None:
    """L1-11: Rename occurrence with stable IDs.

    Expected: Link survives; display path changes; no name-based rematching.
    """
    # 1. Upload Two-FIFO snapshot T1
    t1_bytes = get_two_fifo_snapshot_bytes()
    t1_res = client.post("/api/verification/v1/source-imports", content=t1_bytes)
    t1_id = t1_res.json()["snapshot_id"]

    plan_res = client.post(
        "/api/verification/v1/plans",
        json={"name": "Rename Occurrence Plan", "snapshot_id": t1_id, "root_scope_id": "fifo_pipeline"},
    )
    plan_id = plan_res.json()["id"]

    # 2. Create section and intent under scope "ingress" (stable occurrence ID)
    client.post(
        f"/api/verification/v1/plans/{plan_id}/commands",
        json={
            "base_edit_revision": 1,
            "request_id": "add-ingress-intent",
            "operations": [
                {"op": "section.create", "id": "sec-ing", "title": "Ingress Section", "scope_id": "ingress"},
                {"op": "intent.create", "id": "int-ing", "title": "Ingress Intent", "scope_id": "ingress", "parent_section_id": "sec-ing"},
            ],
        },
    )

    # In T1, ingress occurrence path is "fifo_pipeline/ingress"
    hier_1 = client.get(f"/api/verification/v1/plans/{plan_id}/hierarchy?scope_id=ingress").json()
    assert hier_1[0]["id"] == "ingress"
    assert hier_1[0]["path"] == "fifo pipeline/ingress"

    # 3. Upload renamed snapshot T2 (same occurrence_id='ingress', but path='fifo_pipeline/ingress_renamed')
    t2_bytes = get_renamed_two_fifo_snapshot_bytes()
    t2_res = client.post("/api/verification/v1/source-imports", content=t2_bytes)
    t2_id = t2_res.json()["snapshot_id"]

    # 4. Update source
    client.post(
        f"/api/verification/v1/plans/{plan_id}/commands",
        json={
            "base_edit_revision": 2,
            "request_id": "update-source-t2",
            "operations": [{"op": "source.update", "staged_import_id": t2_id}],
        },
    )

    # 5. Check hierarchy: occurrence ID is still "ingress", but path and name reflect the rename!
    hier_2 = client.get(f"/api/verification/v1/plans/{plan_id}/hierarchy?scope_id=ingress").json()
    assert hier_2[0]["id"] == "ingress"
    assert hier_2[0]["path"] == "fifo pipeline/ingress_renamed"
    assert hier_2[0]["name"] == "ingress_renamed"

    # The intent still cleanly belongs to scope "ingress"
    intent_rec = client.get(f"/api/verification/v1/plans/{plan_id}/records/int-ing").json()
    assert intent_rec["scope_id"] == "ingress"


def test_l1_12_archive_section_preserves_history_and_reports_missing_active_intent(client: TestClient) -> None:
    """L1-12: Archive section referenced by coverage.

    Expected: Historic trace works; new review reports missing active intent; evidence retained.
    """
    snap_res = client.post("/api/verification/v1/source-imports", content=get_fifo_snapshot_bytes())
    snap_id = snap_res.json()["snapshot_id"]

    plan_res = client.post(
        "/api/verification/v1/plans",
        json={"name": "Archive Test Plan", "snapshot_id": snap_id, "root_scope_id": "sync_fifo"},
    )
    plan_id = plan_res.json()["id"]

    # Create requirement, section, ready intent
    client.post(
        f"/api/verification/v1/plans/{plan_id}/commands",
        json={
            "base_edit_revision": 1,
            "request_id": "setup-archive-plan",
            "operations": [
                {
                    "op": "requirement.create",
                    "id": "req-1",
                    "title": "Verifiable Req",
                    "statement": "Statement",
                    "scope_id": "sync_fifo",
                    "disposition": "verify",
                    "source_locators": [
                        {
                            "snapshot_id": snap_id,
                            "entity_ref": {"document_id": "fifo_spec", "entity_kind": "component", "entity_id": "sync_fifo"},
                            "section_id": "sec-reset",
                            "text_range": [0, 5],
                            "quoted_text": "Reset",
                            "section_digest": "dummy",
                        }
                    ],
                },
                {"op": "section.create", "id": "sec-1", "title": "Active Section", "scope_id": "sync_fifo"},
                {
                    "op": "intent.create",
                    "id": "int-1",
                    "title": "Active Intent",
                    "scope_id": "sync_fifo",
                    "parent_section_id": "sec-1",
                    "requirement_ids": ["req-1"],
                    "preconditions": "Reset done.",
                    "trigger": "Clock edge.",
                    "expected_behavior": "State advances.",
                    "observations": [{"name": "Out", "description": "Valid output."}],
                    "authoring_state": "ready",
                },
            ],
        },
    )

    # Assess sections and create checkpoint P1
    sec_res = client.get(f"/api/verification/v1/plans/{plan_id}/source-sections").json()
    assess_ops = []
    for s in sec_res:
        assess_ops.append({
            "op": "source_section.assess",
            "section_id": s["section_id"],
            "disposition": "requirements_captured" if s["section_id"] == "sec-reset" else "informational",
            "requirement_ids": ["req-1"] if s["section_id"] == "sec-reset" else [],
            "reason": "Audited",
        })
    client.post(
        f"/api/verification/v1/plans/{plan_id}/commands",
        json={"base_edit_revision": 2, "request_id": "audit-ops", "operations": assess_ops},
    )

    p1_res = client.post(f"/api/verification/v1/plans/{plan_id}/checkpoints", json={"reviewer_label": "lead"})
    assert p1_res.status_code == 201
    p1_id = p1_res.json()["id"]

    # Archive sec-1 and its descendant int-1
    arc_res = client.post(
        f"/api/verification/v1/plans/{plan_id}/commands",
        json={
            "base_edit_revision": 3,
            "request_id": "archive-sec-1",
            "operations": [{"op": "record.archive", "id": "sec-1", "descendant_ids": ["int-1"]}],
        },
    )
    assert arc_res.status_code == 200

    # Active records exclude sec-1 and int-1
    active_records = client.get(f"/api/verification/v1/plans/{plan_id}/records").json()
    active_ids = [r["id"] for r in active_records]
    assert "sec-1" not in active_ids
    assert "int-1" not in active_ids
    assert "req-1" in active_ids

    # Query with include_archived=true shows int-1 marked archived
    all_records = client.get(f"/api/verification/v1/plans/{plan_id}/records?include_archived=true").json()
    archived_int = next(r for r in all_records if r["id"] == "int-1")
    assert archived_int["archived"] is True

    # Checkpoint P1 retains the unarchived historic record
    frozen_p1 = client.get(f"/api/verification/v1/plans/{plan_id}/checkpoints/{p1_id}").json()
    frozen_int = next(r for r in frozen_p1["payload"]["intents"] if r["id"] == "int-1")
    assert frozen_int["archived"] is False

    # Attempting to create a new checkpoint now fails because req-1 has no active linked intent!
    new_chk_res = client.post(f"/api/verification/v1/plans/{plan_id}/checkpoints", json={"reviewer_label": "lead"})
    assert new_chk_res.status_code == 422
    blockers = new_chk_res.json()["error"]["blockers"]
    assert any("has no active linked intent" in b for b in blockers)


def test_l1_13_semantic_field_edit_resets_ready_intent_to_draft(client: TestClient) -> None:
    """L1-13: Invalid or semantic field edit on ready intent resets it to draft with diagnostics."""
    snap_res = client.post("/api/verification/v1/source-imports", content=get_fifo_snapshot_bytes())
    snap_id = snap_res.json()["snapshot_id"]
    plan_res = client.post(
        "/api/verification/v1/plans",
        json={"name": "Semantic Edit Plan", "snapshot_id": snap_id, "root_scope_id": "sync_fifo"},
    )
    plan_id = plan_res.json()["id"]

    # Create requirement and ready intent
    client.post(
        f"/api/verification/v1/plans/{plan_id}/commands",
        json={
            "base_edit_revision": 1,
            "request_id": "setup-ready",
            "operations": [
                {
                    "op": "requirement.create",
                    "id": "req-1",
                    "title": "Req 1",
                    "statement": "Statement 1",
                    "scope_id": "sync_fifo",
                    "disposition": "verify",
                    "source_locators": [
                        {
                            "snapshot_id": snap_id,
                            "entity_ref": {"document_id": "fifo_spec", "entity_kind": "component", "entity_id": "sync_fifo"},
                            "section_id": "sec-reset",
                            "text_range": [0, 5],
                            "quoted_text": "text",
                            "section_digest": "digest",
                        }
                    ],
                },
                {
                    "op": "intent.create",
                    "id": "int-1",
                    "title": "Ready Intent",
                    "scope_id": "sync_fifo",
                    "requirement_ids": ["req-1"],
                    "preconditions": "Initial reset inactive.",
                    "trigger": "Rising clock edge.",
                    "expected_behavior": "Outputs updated.",
                    "observations": [{"name": "Out", "description": "Output valid."}],
                    "authoring_state": "ready",
                },
            ],
        },
    )

    intent = client.get(f"/api/verification/v1/plans/{plan_id}/records/int-1").json()
    assert intent["authoring_state"] == "ready"

    # Edit semantic field: preconditions
    edit_res = client.post(
        f"/api/verification/v1/plans/{plan_id}/commands",
        json={
            "base_edit_revision": 2,
            "request_id": "edit-preconditions",
            "operations": [
                {"op": "intent.update", "id": "int-1", "changes": {"preconditions": "New modified preconditions."}}
            ],
        },
    )
    assert edit_res.status_code == 200

    # Ready state is automatically reset to draft!
    updated_intent = client.get(f"/api/verification/v1/plans/{plan_id}/records/int-1").json()
    assert updated_intent["authoring_state"] == "draft"


def test_l1_14_bundle_round_trip_and_exports(client: TestClient, tmp_path: Path) -> None:
    """L1-14: Export Markdown, CSV, and .vplan bundle, restart/reimport preserved."""
    snap_res = client.post("/api/verification/v1/source-imports", content=get_fifo_snapshot_bytes())
    snap_id = snap_res.json()["snapshot_id"]
    plan_res = client.post(
        "/api/verification/v1/plans",
        json={"name": "Exportable Plan", "snapshot_id": snap_id, "root_scope_id": "sync_fifo"},
    )
    plan_id = plan_res.json()["id"]

    # Add a section and intent
    client.post(
        f"/api/verification/v1/plans/{plan_id}/commands",
        json={
            "base_edit_revision": 1,
            "request_id": "add-data",
            "operations": [
                {"op": "section.create", "id": "sec-1", "title": "Core Section", "scope_id": "sync_fifo"},
                {"op": "intent.create", "id": "int-1", "title": "Core Intent", "scope_id": "sync_fifo", "parent_section_id": "sec-1"},
            ],
        },
    )

    # 1. Export Markdown
    md_res = client.post(f"/api/verification/v1/plans/{plan_id}/exports", json={"format": "markdown"})
    assert md_res.status_code == 200
    assert "Verification Plan: Exportable Plan" in md_res.text
    assert "Core Intent" in md_res.text

    # 2. Export CSV
    csv_res = client.post(f"/api/verification/v1/plans/{plan_id}/exports", json={"format": "csv"})
    assert csv_res.status_code == 200
    assert "Intent Key,Title,Scope,Section,Priority" in csv_res.text

    # 3. Export .vplan bundle
    bundle_res = client.post(f"/api/verification/v1/plans/{plan_id}/exports", json={"format": "bundle"})
    assert bundle_res.status_code == 200
    bundle_bytes = bundle_res.content

    # 4. Import bundle into new service instance
    new_app = create_app(storage_dir=tmp_path / "second_service_data")
    new_client = TestClient(new_app)

    imp_upload_res = new_client.post("/api/verification/v1/bundle-imports", content=bundle_bytes)
    assert imp_upload_res.status_code == 201
    staging_id = imp_upload_res.json()["staging_id"]

    commit_res = new_client.post(f"/api/verification/v1/bundle-imports/{staging_id}/commit", json={"resolution": "create"})
    assert commit_res.status_code == 201
    new_plan_id = commit_res.json()["plan_id"]
    assert new_plan_id == plan_id

    # Verify restored records
    new_records = new_client.get(f"/api/verification/v1/plans/{new_plan_id}/records").json()
    assert len(new_records) == 2


def test_l1_15_api_idempotent_retry_and_conflicting_edit(client: TestClient) -> None:
    """L1-15: API idempotent retry and two-client conflicting edit (409)."""
    snap_res = client.post("/api/verification/v1/source-imports", content=get_fifo_snapshot_bytes())
    snap_id = snap_res.json()["snapshot_id"]
    plan_res = client.post(
        "/api/verification/v1/plans",
        json={"name": "Concurrency Plan", "snapshot_id": snap_id, "root_scope_id": "sync_fifo"},
    )
    plan_id = plan_res.json()["id"]

    cmd_payload = {
        "base_edit_revision": 1,
        "request_id": "client-1-first-edit",
        "operations": [
            {"op": "section.create", "id": "sec-c1", "title": "Client 1 Section", "scope_id": "sync_fifo"}
        ],
    }

    # First client succeeds
    res1 = client.post(f"/api/verification/v1/plans/{plan_id}/commands", json=cmd_payload)
    assert res1.status_code == 200
    assert res1.json()["edit_revision"] == 2

    # Retry exact same request: idempotent replay!
    res1_retry = client.post(f"/api/verification/v1/plans/{plan_id}/commands", json=cmd_payload)
    assert res1_retry.status_code == 200
    assert res1_retry.json()["edit_revision"] == 2

    # Different client attempts edit with stale revision 1 -> 409 conflict!
    stale_cmd_payload = {
        "base_edit_revision": 1,
        "request_id": "client-2-stale-edit",
        "operations": [
            {"op": "section.create", "id": "sec-c2", "title": "Client 2 Stale Section", "scope_id": "sync_fifo"}
        ],
    }
    res2 = client.post(f"/api/verification/v1/plans/{plan_id}/commands", json=stale_cmd_payload)
    assert res2.status_code == 409
    err = res2.json()
    assert err["error"]["code"] == "revision_conflict"
    assert err["error"]["current_revision"] == 2


@pytest.mark.parametrize("sample", ["fifo", "two_fifo"])
def test_builtin_sample_uses_real_snapshot_import_identity(client, sample):
    response = client.get(f"/api/verification/v1/source-samples/{sample}")
    assert response.status_code == 200
    imported = client.post("/api/verification/v1/source-imports", content=response.content)
    assert imported.status_code == 201, imported.text
    source = imported.json()
    created = client.post("/api/verification/v1/plans", json={
        "name": f"Imported {sample}", "snapshot_id": source["snapshot_id"],
        "root_scope_id": source["occurrences"][0]["occurrence_id"],
    })
    assert created.status_code == 201, created.text
    assert created.json()["snapshot_id"] == source["snapshot_id"]
    assert client.get("/api/verification/v1/source-samples/missing").status_code == 404
