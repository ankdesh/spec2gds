"""Command batch handler executing atomic operations with revision preconditions."""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any

from testplan_service.constants import (
    KEY_PREFIX_BCFG,
    KEY_PREFIX_BIND,
    KEY_PREFIX_DIM,
    KEY_PREFIX_INT,
    KEY_PREFIX_ISS,
    KEY_PREFIX_OBJ,
    KEY_PREFIX_POL,
    KEY_PREFIX_RCP,
    KEY_PREFIX_REQ,
    KEY_PREFIX_SEC,
    MAX_OPERATIONS_PER_BATCH,
)
from testplan_service.domain.enums import (
    AuthoringState,
    IntentOrigin,
    IssueSeverity,
    IssueState,
    Priority,
    RequirementDisposition,
    SourceAuditDisposition,
)
from testplan_service.domain.hash import canonical_json, sha256_digest
from testplan_service.domain.models import (
    Intent,
    Issue,
    Observation,
    PlanHeader,
    Requirement,
    Section,
    SourceAuditEntry,
    SourceLocator,
)
from testplan_service.domain.objectives import (
    BinStatus,
    CoverageBin,
    CoverageDimension,
    CoverageExclusion,
    CoverageFamily,
    CoverageObjective,
    DimensionType,
    ExclusionReason,
)
from testplan_service.domain.policies import IntentEvidencePolicy, PolicyBranch
from testplan_service.domain.recipes import (
    BackendConfiguration,
    EvidenceBinding,
    OracleProvenance,
    Recipe,
    RecipeKind,
    RecipeState,
    TargetBinding,
    TargetBindingSet,
)
from testplan_service.domain.test_ir import ClockDecl, ResetDecl, TestIR
from testplan_service.domain.validation import (
    check_intent_readiness,
    is_semantic_intent_change,
    validate_intent_dependencies,
    validate_section_hierarchy,
)
from testplan_service.exceptions import (
    DomainValidationError,
    InvalidOperationError,
    PreconditionRequiredError,
    RecordNotFoundError,
)
from testplan_service.integrations.snapshot_decoder import decode_snapshot_bytes
from testplan_service.storage.sqlite_repo import SqlitePlanRepository


class CommandHandler:
    """Executes validated atomic command batches against a plan."""

    def __init__(self, repo: SqlitePlanRepository) -> None:
        self.repo = repo

    def execute_batch(
        self,
        plan_id: str,
        base_edit_revision: int | None,
        request_id: str,
        operations: list[dict[str, Any]],
        preview_only: bool = False,
    ) -> dict[str, Any]:
        """Validate and apply a batch of operations transactionally."""
        if base_edit_revision is None:
            raise PreconditionRequiredError("Missing required 'base_edit_revision' in command batch.")

        if len(operations) > MAX_OPERATIONS_PER_BATCH:
            raise DomainValidationError(
                f"Batch operation count {len(operations)} exceeds maximum limit of {MAX_OPERATIONS_PER_BATCH}."
            )

        # Canonical payload hash for idempotency checking
        payload_hash = sha256_digest(canonical_json(operations))

        # Replay before checking a stale draft revision: an exact successful retry
        # must return its prior receipt after that command already advanced the plan.
        # The current replay hash covers operations, not the complete HTTP envelope.
        if not preview_only:
            cached_resp = self.repo.check_command_idempotency(plan_id, request_id, payload_hash)
            if cached_resp is not None:
                return cached_resp

        plan = self.repo.get_plan(plan_id)
        if not plan:
            raise RecordNotFoundError(plan_id, plan_id)

        if not preview_only and plan.edit_revision != base_edit_revision:
            from testplan_service.exceptions import RevisionConflictError

            raise RevisionConflictError(
                plan_id=plan_id,
                base_revision=base_edit_revision,
                current_revision=plan.edit_revision,
                request_id=request_id,
            )

        # Candidate maps let later operations refer to earlier creates in this batch.
        # Intermediate drafts need not be review-ready; final structural invariants
        # must pass before the repository transaction publishes any record changes.
        raw_records = self.repo.get_records(plan_id, include_archived=True)
        requirements: dict[str, Requirement] = {}
        sections: dict[str, Section] = {}
        intents: dict[str, Intent] = {}
        issues: dict[str, Issue] = {}
        dimensions: dict[str, CoverageDimension] = {}
        objectives: dict[str, CoverageObjective] = {}
        policies: dict[str, IntentEvidencePolicy] = {}
        exclusions: dict[str, CoverageExclusion] = {}
        binding_sets: dict[str, TargetBindingSet] = {}
        recipes: dict[str, Recipe] = {}
        backend_configurations: dict[str, BackendConfiguration] = {}

        for r in raw_records:
            rtype = r.get("record_type")
            rid = r.get("id")
            if rtype == "requirement":
                requirements[rid] = Requirement.model_validate(r)
            elif rtype == "section":
                sections[rid] = Section.model_validate(r)
            elif rtype == "intent":
                intents[rid] = Intent.model_validate(r)
            elif rtype == "issue":
                issues[rid] = Issue.model_validate(r)
            elif rtype == "dimension":
                dimensions[rid] = CoverageDimension.model_validate(r)
            elif rtype == "objective":
                objectives[rid] = CoverageObjective.model_validate(r)
            elif rtype == "policy":
                policies[rid] = IntentEvidencePolicy.model_validate(r)
            elif rtype == "exclusion":
                exclusions[rid] = CoverageExclusion.model_validate(r)
            elif rtype == "target_binding_set":
                binding_sets[rid] = TargetBindingSet.model_validate(r)
            elif rtype == "recipe":
                recipes[rid] = Recipe.model_validate(r)
            elif rtype == "backend_configuration":
                backend_configurations[rid] = BackendConfiguration.model_validate(r)

        source_audits: dict[str, SourceAuditEntry] = copy.deepcopy(plan.source_audit)
        header_changes: dict[str, Any] = {}
        deleted_record_ids: list[str] = []
        diagnostics: list[dict[str, Any]] = []
        changed_records_map: dict[str, dict[str, Any]] = {}

        now_iso = datetime.now(timezone.utc).isoformat()

        # Execute operations sequentially in memory
        for idx, raw_op in enumerate(operations):
            op_name = raw_op.get("op")
            if not op_name:
                raise InvalidOperationError("Operation missing 'op' field", "unknown")

            if op_name == "plan.update":
                changes = raw_op.get("changes", {})
                for k, v in changes.items():
                    if k in {"name", "description", "owner_label", "tags"}:
                        header_changes[k] = v
                header_changes["updated_at"] = now_iso

            elif op_name == "source_section.assess":
                sec_id = raw_op["section_id"]
                disp = SourceAuditDisposition(raw_op["disposition"])
                reason = raw_op.get("reason")
                req_ids = raw_op.get("requirement_ids", [])
                if disp in {SourceAuditDisposition.INFORMATIONAL, SourceAuditDisposition.OUT_OF_SCOPE} and not reason:
                    raise DomainValidationError(f"Source audit disposition '{disp}' requires a reason.")
                if disp == SourceAuditDisposition.REQUIREMENTS_CAPTURED and not req_ids:
                    raise DomainValidationError("Audit disposition 'requirements_captured' requires at least one linked requirement.")

                audit_entry = SourceAuditEntry(
                    section_id=sec_id,
                    disposition=disp,
                    reason=reason,
                    linked_requirement_ids=req_ids,
                    reviewer_label=raw_op.get("reviewer_label", "author"),
                    source_digest=raw_op.get("source_digest", ""),
                    updated_at=now_iso,
                )
                source_audits[sec_id] = audit_entry
                changed_records_map[f"audit:{sec_id}"] = audit_entry.model_dump()

            elif op_name == "requirement.create":
                req_id = raw_op.get("id") or str(uuid.uuid4())
                key = self.repo.allocate_key(plan_id, KEY_PREFIX_REQ) if not preview_only else f"{KEY_PREFIX_REQ}-preview"
                locators = [SourceLocator.model_validate(l) for l in raw_op.get("source_locators", [])]
                req = Requirement(
                    id=req_id,
                    key=key,
                    title=raw_op["title"],
                    statement=raw_op["statement"],
                    source_locators=locators,
                    interpretation_note=raw_op.get("interpretation_note"),
                    scope_id=raw_op["scope_id"],
                    disposition=RequirementDisposition(raw_op.get("disposition", RequirementDisposition.UNASSESSED)),
                    disposition_reason=raw_op.get("disposition_reason"),
                    issue_ids=raw_op.get("issue_ids", []),
                    copied_from=raw_op.get("copied_from"),
                    created_at=now_iso,
                    updated_at=now_iso,
                )
                requirements[req_id] = req
                changed_records_map[req_id] = req.model_dump() | {"record_type": "requirement"}

            elif op_name == "requirement.update":
                req_id = raw_op["id"]
                if req_id not in requirements or requirements[req_id].archived:
                    raise RecordNotFoundError(plan_id, req_id)
                current_req = requirements[req_id]
                changes = raw_op.get("changes", {})
                updated_req = current_req.model_copy(
                    update=changes
                    | {
                        "record_revision": current_req.record_revision + 1,
                        "updated_at": now_iso,
                    }
                )
                requirements[req_id] = updated_req
                changed_records_map[req_id] = updated_req.model_dump() | {"record_type": "requirement"}

            elif op_name == "section.create":
                sec_id = raw_op.get("id") or str(uuid.uuid4())
                key = self.repo.allocate_key(plan_id, KEY_PREFIX_SEC) if not preview_only else f"{KEY_PREFIX_SEC}-preview"
                parent_id = raw_op.get("parent_section_id")
                before_id = raw_op.get("before_id")

                sec = Section(
                    id=sec_id,
                    key=key,
                    title=raw_op["title"],
                    description=raw_op.get("description", ""),
                    scope_id=raw_op["scope_id"],
                    parent_section_id=parent_id,
                    default_priority=Priority(raw_op.get("default_priority", Priority.MEDIUM)),
                    tags=raw_op.get("tags", []),
                    copied_from=raw_op.get("copied_from"),
                    created_at=now_iso,
                    updated_at=now_iso,
                )
                sections[sec_id] = sec

                # Update parent's child_ids
                if parent_id and parent_id in sections:
                    parent_sec = sections[parent_id]
                    c_ids = list(parent_sec.child_ids)
                    if before_id and before_id in c_ids:
                        c_ids.insert(c_ids.index(before_id), sec_id)
                    else:
                        c_ids.append(sec_id)
                    sections[parent_id] = parent_sec.model_copy(update={"child_ids": c_ids, "updated_at": now_iso})
                    changed_records_map[parent_id] = sections[parent_id].model_dump() | {"record_type": "section"}

                changed_records_map[sec_id] = sec.model_dump() | {"record_type": "section"}

            elif op_name == "section.update":
                sec_id = raw_op["id"]
                if sec_id not in sections or sections[sec_id].archived:
                    raise RecordNotFoundError(plan_id, sec_id)
                current_sec = sections[sec_id]
                changes = raw_op.get("changes", {})
                updated_sec = current_sec.model_copy(
                    update=changes
                    | {
                        "record_revision": current_sec.record_revision + 1,
                        "updated_at": now_iso,
                    }
                )
                sections[sec_id] = updated_sec
                changed_records_map[sec_id] = updated_sec.model_dump() | {"record_type": "section"}

            elif op_name == "intent.create":
                intent_id = raw_op.get("id") or str(uuid.uuid4())
                key = self.repo.allocate_key(plan_id, KEY_PREFIX_INT) if not preview_only else f"{KEY_PREFIX_INT}-preview"
                parent_id = raw_op.get("parent_section_id")
                before_id = raw_op.get("before_id")

                obs_list = [Observation.model_validate(o) for o in raw_op.get("observations", [])]
                intent = Intent(
                    id=intent_id,
                    key=key,
                    title=raw_op["title"],
                    scope_id=raw_op["scope_id"],
                    parent_section_id=parent_id,
                    requirement_ids=raw_op.get("requirement_ids", []),
                    preconditions=raw_op.get("preconditions", ""),
                    trigger=raw_op.get("trigger", ""),
                    expected_behavior=raw_op.get("expected_behavior", ""),
                    observations=obs_list,
                    rationale=raw_op.get("rationale"),
                    origin=IntentOrigin(raw_op.get("origin", IntentOrigin.DIRECT_REQUIREMENT)),
                    priority_override=Priority(raw_op["priority_override"]) if raw_op.get("priority_override") else None,
                    tags=raw_op.get("tags", []),
                    participants=raw_op.get("participants", []),
                    dependency_ids=raw_op.get("dependency_ids", []),
                    issue_ids=raw_op.get("issue_ids", []),
                    authoring_state=AuthoringState(raw_op.get("authoring_state", AuthoringState.DRAFT)),
                    copied_from=raw_op.get("copied_from"),
                    created_at=now_iso,
                    updated_at=now_iso,
                )

                # Check readiness diagnostics (advisory for drafts)
                readiness_issues = check_intent_readiness(intent, requirements, issues)
                if intent.authoring_state == AuthoringState.READY and readiness_issues:
                    raise DomainValidationError(
                        f"Cannot create intent '{intent.title}' in ready state: {readiness_issues[0]['message']}",
                        readiness_issues,
                    )

                intents[intent_id] = intent

                # Add to parent section child_ids if parenting
                if parent_id and parent_id in sections:
                    parent_sec = sections[parent_id]
                    c_ids = list(parent_sec.child_ids)
                    if before_id and before_id in c_ids:
                        c_ids.insert(c_ids.index(before_id), intent_id)
                    else:
                        c_ids.append(intent_id)
                    sections[parent_id] = parent_sec.model_copy(update={"child_ids": c_ids, "updated_at": now_iso})
                    changed_records_map[parent_id] = sections[parent_id].model_dump() | {"record_type": "section"}

                changed_records_map[intent_id] = intent.model_dump() | {"record_type": "intent"}

            elif op_name == "intent.update":
                intent_id = raw_op["id"]
                if intent_id not in intents or intents[intent_id].archived:
                    raise RecordNotFoundError(plan_id, intent_id)
                current_intent = intents[intent_id]
                changes = raw_op.get("changes", {})

                # Check if semantic fields changed: resets READY to DRAFT!
                reset_to_draft = False
                if current_intent.authoring_state == AuthoringState.READY:
                    if is_semantic_intent_change(current_intent, changes):
                        reset_to_draft = True
                        changes["authoring_state"] = AuthoringState.DRAFT

                updated_intent = current_intent.model_copy(
                    update=changes
                    | {
                        "record_revision": current_intent.record_revision + 1,
                        "updated_at": now_iso,
                    }
                )
                intents[intent_id] = updated_intent
                changed_records_map[intent_id] = updated_intent.model_dump() | {"record_type": "intent"}
                if reset_to_draft:
                    diagnostics.append({
                        "code": "intent.reset_to_draft",
                        "severity": "info",
                        "record_id": intent_id,
                        "message": f"Semantic edits reset ready intent '{current_intent.title}' to draft.",
                    })

            elif op_name == "intent.set_state":
                intent_id = raw_op["id"]
                if intent_id not in intents or intents[intent_id].archived:
                    raise RecordNotFoundError(plan_id, intent_id)
                target_state = AuthoringState(raw_op["state"])
                current_intent = intents[intent_id]

                if target_state == AuthoringState.READY:
                    readiness_issues = check_intent_readiness(current_intent, requirements, issues)
                    if readiness_issues:
                        raise DomainValidationError(
                            f"Intent '{current_intent.title}' cannot be marked ready: {readiness_issues[0]['message']}",
                            readiness_issues,
                        )
                elif target_state == AuthoringState.BLOCKED:
                    blocking_issues = [
                        i_id
                        for i_id in current_intent.issue_ids
                        if i_id in issues and issues[i_id].severity == IssueSeverity.BLOCKING and issues[i_id].state == IssueState.OPEN
                    ]
                    if not blocking_issues:
                        raise DomainValidationError(
                            f"Intent '{current_intent.title}' cannot be set to blocked without an open blocking issue."
                        )

                updated_intent = current_intent.model_copy(
                    update={
                        "authoring_state": target_state,
                        "record_revision": current_intent.record_revision + 1,
                        "updated_at": now_iso,
                    }
                )
                intents[intent_id] = updated_intent
                changed_records_map[intent_id] = updated_intent.model_dump() | {"record_type": "intent"}

            elif op_name == "intent.link_requirement":
                intent_id = raw_op["intent_id"]
                req_id = raw_op["requirement_id"]
                if intent_id not in intents or req_id not in requirements:
                    raise RecordNotFoundError(plan_id, intent_id if intent_id not in intents else req_id)
                current_intent = intents[intent_id]
                if req_id not in current_intent.requirement_ids:
                    r_ids = list(current_intent.requirement_ids) + [req_id]
                    updated_intent = current_intent.model_copy(
                        update={"requirement_ids": r_ids, "updated_at": now_iso}
                    )
                    intents[intent_id] = updated_intent
                    changed_records_map[intent_id] = updated_intent.model_dump() | {"record_type": "intent"}

            elif op_name == "intent.unlink_requirement":
                intent_id = raw_op["intent_id"]
                req_id = raw_op["requirement_id"]
                if intent_id not in intents:
                    raise RecordNotFoundError(plan_id, intent_id)
                current_intent = intents[intent_id]
                if req_id in current_intent.requirement_ids:
                    r_ids = [r for r in current_intent.requirement_ids if r != req_id]
                    updated_state = current_intent.authoring_state
                    if current_intent.authoring_state == AuthoringState.READY:
                        updated_state = AuthoringState.DRAFT
                    updated_intent = current_intent.model_copy(
                        update={
                            "requirement_ids": r_ids,
                            "authoring_state": updated_state,
                            "updated_at": now_iso,
                        }
                    )
                    intents[intent_id] = updated_intent
                    changed_records_map[intent_id] = updated_intent.model_dump() | {"record_type": "intent"}

            elif op_name == "item.move":
                item_id = raw_op["id"]
                target_scope = raw_op["target_scope_id"]
                parent_sec_id = raw_op.get("parent_section_id")
                before_id = raw_op.get("before_id")

                if item_id in sections:
                    curr_sec = sections[item_id]
                    # Remove from old parent child_ids
                    if curr_sec.parent_section_id and curr_sec.parent_section_id in sections:
                        old_p = sections[curr_sec.parent_section_id]
                        c_ids = [c for c in old_p.child_ids if c != item_id]
                        sections[curr_sec.parent_section_id] = old_p.model_copy(update={"child_ids": c_ids})
                    # Add to new parent child_ids
                    if parent_sec_id and parent_sec_id in sections:
                        new_p = sections[parent_sec_id]
                        c_ids = list(new_p.child_ids)
                        if before_id and before_id in c_ids:
                            c_ids.insert(c_ids.index(before_id), item_id)
                        else:
                            c_ids.append(item_id)
                        sections[parent_sec_id] = new_p.model_copy(update={"child_ids": c_ids})

                    updated_sec = curr_sec.model_copy(
                        update={
                            "scope_id": target_scope,
                            "parent_section_id": parent_sec_id,
                            "record_revision": curr_sec.record_revision + 1,
                            "updated_at": now_iso,
                        }
                    )
                    sections[item_id] = updated_sec
                    changed_records_map[item_id] = updated_sec.model_dump() | {"record_type": "section"}

                elif item_id in intents:
                    curr_intent = intents[item_id]
                    # Remove from old parent child_ids
                    if curr_intent.parent_section_id and curr_intent.parent_section_id in sections:
                        old_p = sections[curr_intent.parent_section_id]
                        c_ids = [c for c in old_p.child_ids if c != item_id]
                        sections[curr_intent.parent_section_id] = old_p.model_copy(update={"child_ids": c_ids})
                    # Add to new parent child_ids
                    if parent_sec_id and parent_sec_id in sections:
                        new_p = sections[parent_sec_id]
                        c_ids = list(new_p.child_ids)
                        if before_id and before_id in c_ids:
                            c_ids.insert(c_ids.index(before_id), item_id)
                        else:
                            c_ids.append(item_id)
                        sections[parent_sec_id] = new_p.model_copy(update={"child_ids": c_ids})

                    # If moving to another scope, reset to draft
                    updated_state = curr_intent.authoring_state
                    if target_scope != curr_intent.scope_id and curr_intent.authoring_state == AuthoringState.READY:
                        updated_state = AuthoringState.DRAFT

                    updated_intent = curr_intent.model_copy(
                        update={
                            "scope_id": target_scope,
                            "parent_section_id": parent_sec_id,
                            "authoring_state": updated_state,
                            "record_revision": curr_intent.record_revision + 1,
                            "updated_at": now_iso,
                        }
                    )
                    intents[item_id] = updated_intent
                    changed_records_map[item_id] = updated_intent.model_dump() | {"record_type": "intent"}

            elif op_name == "section.copy":
                # Deliberate copy across scopes
                src_sec_id = raw_op["source_id"]
                target_scope = raw_op["target_scope_id"]
                if src_sec_id not in sections:
                    raise RecordNotFoundError(plan_id, src_sec_id)

                src_sec = sections[src_sec_id]
                new_sec_id = str(uuid.uuid4())
                new_sec_key = self.repo.allocate_key(plan_id, KEY_PREFIX_SEC) if not preview_only else f"{KEY_PREFIX_SEC}-preview"

                new_child_ids: list[str] = []
                # Copy child intents
                for cid in src_sec.child_ids:
                    if cid in intents and not intents[cid].archived:
                        c_intent = intents[cid]
                        new_int_id = str(uuid.uuid4())
                        new_int_key = self.repo.allocate_key(plan_id, KEY_PREFIX_INT) if not preview_only else f"{KEY_PREFIX_INT}-preview"
                        copied_intent = c_intent.model_copy(
                            update={
                                "id": new_int_id,
                                "key": new_int_key,
                                "scope_id": target_scope,
                                "parent_section_id": new_sec_id,
                                "authoring_state": AuthoringState.DRAFT,
                                "copied_from": c_intent.id,
                                "created_at": now_iso,
                                "updated_at": now_iso,
                            }
                        )
                        intents[new_int_id] = copied_intent
                        new_child_ids.append(new_int_id)
                        changed_records_map[new_int_id] = copied_intent.model_dump() | {"record_type": "intent"}

                copied_sec = src_sec.model_copy(
                    update={
                        "id": new_sec_id,
                        "key": new_sec_key,
                        "scope_id": target_scope,
                        "parent_section_id": None,
                        "child_ids": new_child_ids,
                        "copied_from": src_sec.id,
                        "created_at": now_iso,
                        "updated_at": now_iso,
                    }
                )
                sections[new_sec_id] = copied_sec
                changed_records_map[new_sec_id] = copied_sec.model_dump() | {"record_type": "section"}

            elif op_name == "record.archive":
                target_ids = [raw_op["id"]] + raw_op.get("descendant_ids", [])
                for rec_id in target_ids:
                    if rec_id in sections:
                        s = sections[rec_id].model_copy(update={"archived": True, "updated_at": now_iso})
                        sections[rec_id] = s
                        changed_records_map[rec_id] = s.model_dump() | {"record_type": "section"}
                    elif rec_id in intents:
                        i = intents[rec_id].model_copy(update={"archived": True, "updated_at": now_iso})
                        intents[rec_id] = i
                        changed_records_map[rec_id] = i.model_dump() | {"record_type": "intent"}
                    elif rec_id in requirements:
                        r = requirements[rec_id].model_copy(update={"archived": True, "updated_at": now_iso})
                        requirements[rec_id] = r
                        changed_records_map[rec_id] = r.model_dump() | {"record_type": "requirement"}
                    elif rec_id in issues:
                        iss = issues[rec_id].model_copy(update={"archived": True, "updated_at": now_iso})
                        issues[rec_id] = iss
                        changed_records_map[rec_id] = iss.model_dump() | {"record_type": "issue"}

            elif op_name == "record.restore":
                rec_id = raw_op["id"]
                dest_p = raw_op.get("destination_parent_id")
                if rec_id in sections:
                    s = sections[rec_id].model_copy(update={"archived": False, "parent_section_id": dest_p, "updated_at": now_iso})
                    sections[rec_id] = s
                    changed_records_map[rec_id] = s.model_dump() | {"record_type": "section"}
                elif rec_id in intents:
                    i = intents[rec_id].model_copy(update={"archived": False, "parent_section_id": dest_p, "authoring_state": AuthoringState.DRAFT, "updated_at": now_iso})
                    intents[rec_id] = i
                    changed_records_map[rec_id] = i.model_dump() | {"record_type": "intent"}
                elif rec_id in requirements:
                    r = requirements[rec_id].model_copy(update={"archived": False, "updated_at": now_iso})
                    requirements[rec_id] = r
                    changed_records_map[rec_id] = r.model_dump() | {"record_type": "requirement"}

            elif op_name == "record.delete_draft":
                rec_id = raw_op["id"]
                # Only never-reviewed unreferenced records can be hard deleted
                if rec_id in intents:
                    del intents[rec_id]
                    deleted_record_ids.append(rec_id)
                elif rec_id in sections:
                    del sections[rec_id]
                    deleted_record_ids.append(rec_id)
                elif rec_id in requirements:
                    del requirements[rec_id]
                    deleted_record_ids.append(rec_id)

            elif op_name == "source.update":
                staged_import_id = raw_op["staged_import_id"]
                locator_map = raw_op.get("locator_map", {})

                # Resolve snapshot view
                new_snap_view = None
                new_snap_id = staged_import_id
                if staged_import_id.startswith("sha256:"):
                    new_snap_view = self.repo.get_snapshot(staged_import_id)

                if not new_snap_view:
                    staging_path = self.repo.blob_store.staging_dir / f"{staged_import_id}.tmp"
                    blob_data = None
                    if staging_path.is_file():
                        blob_data = staging_path.read_bytes()
                    else:
                        blob_data = self.repo.blob_store.read_blob(staged_import_id.removeprefix("sha256:"))

                    if not blob_data:
                        raise RecordNotFoundError("source_snapshot", staged_import_id)

                    new_snap_view = decode_snapshot_bytes(blob_data)
                    new_snap_id = f"sha256:{sha256_digest(blob_data)}"
                    if not preview_only:
                        self.repo.save_snapshot(new_snap_id, new_snap_view)

                new_sec_map = {s.section_id: s for s in new_snap_view.source_sections}
                affected_req_ids = set()

                for req_id, req in list(requirements.items()):
                    if req.archived:
                        continue
                    req_changed = False
                    new_locators = []
                    for loc in req.source_locators:
                        mapped_sec_id = locator_map.get(loc.section_id, loc.section_id)
                        if mapped_sec_id in new_sec_map:
                            new_sec = new_sec_map[mapped_sec_id]
                            if new_sec.content_digest != loc.section_digest or (loc.quoted_text and loc.quoted_text not in new_sec.content):
                                req_changed = True
                            new_loc = loc.model_copy(
                                update={
                                    "snapshot_id": new_snap_id,
                                    "section_id": mapped_sec_id,
                                    "section_digest": new_sec.content_digest,
                                }
                            )
                            new_locators.append(new_loc)
                        else:
                            req_changed = True
                            new_locators.append(loc)

                    if req_changed:
                        affected_req_ids.add(req_id)
                        updated_req = req.model_copy(
                            update={
                                "source_locators": new_locators,
                                "record_revision": req.record_revision + 1,
                                "updated_at": now_iso,
                            }
                        )
                        requirements[req_id] = updated_req
                        changed_records_map[req_id] = updated_req.model_dump() | {"record_type": "requirement"}
                        diagnostics.append({
                            "code": "source.changed",
                            "severity": "warning",
                            "record_id": req_id,
                            "message": f"Requirement '{req.title}' ({req.key}) source quotation or digest changed in new snapshot.",
                        })

                # Reset linked intents to draft
                for int_id, intent in list(intents.items()):
                    if intent.archived:
                        continue
                    if any(r_id in affected_req_ids for r_id in intent.requirement_ids):
                        if intent.authoring_state == AuthoringState.READY:
                            updated_intent = intent.model_copy(
                                update={
                                    "authoring_state": AuthoringState.DRAFT,
                                    "record_revision": intent.record_revision + 1,
                                    "updated_at": now_iso,
                                }
                            )
                            intents[int_id] = updated_intent
                            changed_records_map[int_id] = updated_intent.model_dump() | {"record_type": "intent"}
                            diagnostics.append({
                                "code": "intent.source_changed",
                                "severity": "warning",
                                "record_id": int_id,
                                "message": f"Intent '{intent.title}' ({intent.key}) reset to draft because linked requirement source changed.",
                            })

                # Source audit updates
                for sec in new_snap_view.source_sections:
                    existing_audit = source_audits.get(sec.section_id)
                    if not existing_audit or existing_audit.source_digest != sec.content_digest:
                        updated_audit = SourceAuditEntry(
                            section_id=sec.section_id,
                            disposition=SourceAuditDisposition.UNREVIEWED,
                            reason=None,
                            linked_requirement_ids=existing_audit.linked_requirement_ids if existing_audit else [],
                            reviewer_label=plan.owner_label or "author",
                            source_digest=sec.content_digest,
                            updated_at=now_iso,
                        )
                        source_audits[sec.section_id] = updated_audit
                        changed_records_map[f"audit:{sec.section_id}"] = updated_audit.model_dump()

                if not preview_only:
                    header_changes["snapshot_id"] = new_snap_id

            elif op_name == "issue.create":
                iss_id = raw_op.get("id") or str(uuid.uuid4())
                key = self.repo.allocate_key(plan_id, KEY_PREFIX_ISS) if not preview_only else f"{KEY_PREFIX_ISS}-preview"
                issue = Issue(
                    id=iss_id,
                    key=key,
                    title=raw_op["title"],
                    kind=raw_op["kind"],
                    description=raw_op["description"],
                    linked_record_ids=raw_op.get("linked_record_ids", []),
                    severity=IssueSeverity(raw_op["severity"]),
                    state=IssueState.OPEN,
                    created_at=now_iso,
                    updated_at=now_iso,
                )
                issues[iss_id] = issue
                changed_records_map[iss_id] = issue.model_dump() | {"record_type": "issue"}

            elif op_name == "issue.resolve":
                iss_id = raw_op["id"]
                if iss_id not in issues:
                    raise RecordNotFoundError(plan_id, iss_id)
                issue = issues[iss_id].model_copy(
                    update={
                        "state": IssueState.RESOLVED,
                        "resolution_text": raw_op["resolution_text"],
                        "resolver_label": raw_op.get("resolver_label", "author"),
                        "resolved_at": now_iso,
                        "updated_at": now_iso,
                    }
                )
                issues[iss_id] = issue
                changed_records_map[iss_id] = issue.model_dump() | {"record_type": "issue"}

            elif op_name == "issue.reopen":
                iss_id = raw_op["id"]
                if iss_id not in issues:
                    raise RecordNotFoundError(plan_id, iss_id)
                issue = issues[iss_id].model_copy(
                    update={
                        "state": IssueState.OPEN,
                        "resolved_at": None,
                        "updated_at": now_iso,
                    }
                )
                issues[iss_id] = issue
                changed_records_map[iss_id] = issue.model_dump() | {"record_type": "issue"}

            elif op_name == "dimension.create":
                dim_id = raw_op.get("id") or str(uuid.uuid4())
                key = self.repo.allocate_key(plan_id, KEY_PREFIX_DIM) if not preview_only else f"{KEY_PREFIX_DIM}-preview"
                dim = CoverageDimension(
                    id=dim_id,
                    key=key,
                    title=raw_op["title"],
                    semantic_description=raw_op.get("semantic_description", ""),
                    scope_id=raw_op["scope_id"],
                    dimension_type=DimensionType(raw_op["dimension_type"]),
                    unit=raw_op.get("unit"),
                    value_classes=raw_op.get("value_classes", []),
                    allow_overlap=raw_op.get("allow_overlap", False),
                    rationale=raw_op.get("rationale"),
                    created_at=now_iso,
                    updated_at=now_iso,
                )
                dimensions[dim_id] = dim
                changed_records_map[dim_id] = dim.model_dump() | {"record_type": "dimension"}

            elif op_name == "dimension.update":
                dim_id = raw_op["id"]
                if dim_id not in dimensions:
                    raise RecordNotFoundError(plan_id, dim_id)
                dim = dimensions[dim_id].model_copy(
                    update=raw_op.get("changes", {}) | {
                        "record_revision": dimensions[dim_id].record_revision + 1,
                        "updated_at": now_iso,
                    }
                )
                dimensions[dim_id] = dim
                changed_records_map[dim_id] = dim.model_dump() | {"record_type": "dimension"}

            elif op_name == "dimension.archive":
                dim_id = raw_op["id"]
                if dim_id not in dimensions:
                    raise RecordNotFoundError(plan_id, dim_id)
                dim = dimensions[dim_id].model_copy(update={"archived": True, "updated_at": now_iso})
                dimensions[dim_id] = dim
                changed_records_map[dim_id] = dim.model_dump() | {"record_type": "dimension"}

            elif op_name == "objective.create":
                obj_id = raw_op.get("id") or str(uuid.uuid4())
                key = self.repo.allocate_key(plan_id, KEY_PREFIX_OBJ) if not preview_only else f"{KEY_PREFIX_OBJ}-preview"
                raw_bins = raw_op.get("bins", [])
                bins = [CoverageBin.model_validate(b) for b in raw_bins]
                family = CoverageFamily(raw_op["family"])
                state = AuthoringState(raw_op.get("authoring_state", AuthoringState.DRAFT))
                obj = CoverageObjective(
                    id=obj_id,
                    key=key,
                    title=raw_op["title"],
                    description=raw_op.get("description", ""),
                    scope_id=raw_op["scope_id"],
                    participant_scope_ids=raw_op.get("participant_scope_ids", []),
                    family=family,
                    semantic_definition=raw_op.get("semantic_definition", ""),
                    dimension_ids=raw_op.get("dimension_ids", []),
                    bins=bins,
                    acceptance=raw_op.get("acceptance", {}),
                    rationale=raw_op.get("rationale"),
                    authoring_state=state,
                    supplemental=raw_op.get("supplemental", False),
                    created_at=now_iso,
                    updated_at=now_iso,
                )
                objectives[obj_id] = obj
                changed_records_map[obj_id] = obj.model_dump() | {"record_type": "objective"}

            elif op_name == "objective.update":
                obj_id = raw_op["id"]
                if obj_id not in objectives:
                    raise RecordNotFoundError(plan_id, obj_id)
                existing_obj = objectives[obj_id]
                changes = dict(raw_op.get("changes", {}))
                semantic_fields = {"family", "semantic_definition", "dimension_ids", "bins", "acceptance", "scope_id", "participant_scope_ids"}
                if any(k in changes for k in semantic_fields) and "authoring_state" not in changes:
                    changes["authoring_state"] = AuthoringState.DRAFT
                if "bins" in changes:
                    changes["bins"] = [CoverageBin.model_validate(b) for b in changes["bins"]]
                if "family" in changes:
                    changes["family"] = CoverageFamily(changes["family"])
                changes["record_revision"] = existing_obj.record_revision + 1
                changes["updated_at"] = now_iso
                updated_obj = existing_obj.model_copy(update=changes)
                objectives[obj_id] = updated_obj
                changed_records_map[obj_id] = updated_obj.model_dump() | {"record_type": "objective"}

            elif op_name == "objective.archive":
                obj_id = raw_op["id"]
                if obj_id not in objectives:
                    raise RecordNotFoundError(plan_id, obj_id)
                obj = objectives[obj_id].model_copy(update={"archived": True, "updated_at": now_iso})
                objectives[obj_id] = obj
                changed_records_map[obj_id] = obj.model_dump() | {"record_type": "objective"}

            elif op_name == "bin.add":
                obj_id = raw_op["objective_id"]
                if obj_id not in objectives:
                    raise RecordNotFoundError(plan_id, obj_id)
                obj = objectives[obj_id]
                new_bin = CoverageBin.model_validate(raw_op["bin"])
                updated_bins = list(obj.bins) + [new_bin]
                updated_obj = obj.model_copy(
                    update={
                        "bins": updated_bins,
                        "authoring_state": AuthoringState.DRAFT,
                        "record_revision": obj.record_revision + 1,
                        "updated_at": now_iso,
                    }
                )
                objectives[obj_id] = updated_obj
                changed_records_map[obj_id] = updated_obj.model_dump() | {"record_type": "objective"}

            elif op_name == "bin.update":
                obj_id = raw_op["objective_id"]
                bin_id = raw_op["bin_id"]
                if obj_id not in objectives:
                    raise RecordNotFoundError(plan_id, obj_id)
                obj = objectives[obj_id]
                updated_bins = []
                found_bin = False
                for b in obj.bins:
                    if b.id == bin_id:
                        found_bin = True
                        updated_bins.append(b.model_copy(update=raw_op.get("changes", {})))
                    else:
                        updated_bins.append(b)
                if not found_bin:
                    raise RecordNotFoundError(plan_id, bin_id)
                updated_obj = obj.model_copy(
                    update={
                        "bins": updated_bins,
                        "record_revision": obj.record_revision + 1,
                        "updated_at": now_iso,
                    }
                )
                objectives[obj_id] = updated_obj
                changed_records_map[obj_id] = updated_obj.model_dump() | {"record_type": "objective"}

            elif op_name == "bin.remove":
                obj_id = raw_op["objective_id"]
                bin_id = raw_op["bin_id"]
                if obj_id not in objectives:
                    raise RecordNotFoundError(plan_id, obj_id)
                obj = objectives[obj_id]
                updated_bins = [b for b in obj.bins if b.id != bin_id]
                updated_obj = obj.model_copy(
                    update={
                        "bins": updated_bins,
                        "authoring_state": AuthoringState.DRAFT,
                        "record_revision": obj.record_revision + 1,
                        "updated_at": now_iso,
                    }
                )
                objectives[obj_id] = updated_obj
                changed_records_map[obj_id] = updated_obj.model_dump() | {"record_type": "objective"}

            elif op_name == "policy.set":
                intent_id = raw_op["intent_id"]
                if intent_id not in intents:
                    raise RecordNotFoundError(plan_id, intent_id)
                raw_branches = raw_op.get("branches", [])
                branches = []
                for b in raw_branches:
                    branch_obj = PolicyBranch.model_validate(b)
                    if len(branch_obj.objective_ids) != len(set(branch_obj.objective_ids)):
                        raise DomainValidationError(f"Duplicate objectives in policy branch '{branch_obj.title}'.")
                    branches.append(branch_obj)

                pol_id = f"pol-{intent_id}"
                existing_pol = policies.get(intent_id) or policies.get(pol_id)
                rev = (existing_pol.record_revision + 1) if existing_pol else 1
                policy = IntentEvidencePolicy(
                    id=pol_id,
                    record_revision=rev,
                    intent_id=intent_id,
                    intent_hash=sha256_digest(canonical_json(intents[intent_id].model_dump())),
                    branches=branches,
                    supplemental_objective_ids=raw_op.get("supplemental_objective_ids", []),
                    rationale=raw_op.get("rationale"),
                    created_at=existing_pol.created_at if existing_pol else now_iso,
                    updated_at=now_iso,
                )
                policies[intent_id] = policy
                policies[pol_id] = policy
                changed_records_map[pol_id] = policy.model_dump() | {"record_type": "policy"}

            elif op_name in {"exclusion.propose", "exclusion.create"}:
                ex_id = raw_op.get("id") or str(uuid.uuid4())
                reason_kind_val = raw_op.get("reason_kind") or "unreachable"
                if reason_kind_val == "unreachable_hardware":
                    reason_kind_val = "unreachable"
                try:
                    reason_enum = ExclusionReason(reason_kind_val)
                except ValueError:
                    reason_enum = ExclusionReason.UNREACHABLE
                rationale_val = raw_op.get("rationale") or raw_op.get("reason", "Excluded bin")
                exclusion = CoverageExclusion(
                    id=ex_id,
                    objective_id=raw_op["objective_id"],
                    bin_id=raw_op.get("bin_id"),
                    reason_kind=reason_enum,
                    rationale=rationale_val,
                    supporting_evidence_ids=raw_op.get("supporting_evidence_ids", []),
                    created_at=now_iso,
                    updated_at=now_iso,
                )
                exclusions[ex_id] = exclusion
                changed_records_map[ex_id] = exclusion.model_dump() | {"record_type": "exclusion"}

            elif op_name == "exclusion.update":
                ex_id = raw_op["id"]
                if ex_id not in exclusions:
                    raise RecordNotFoundError(plan_id, ex_id)
                ex = exclusions[ex_id].model_copy(
                    update=raw_op.get("changes", {}) | {
                        "record_revision": exclusions[ex_id].record_revision + 1,
                        "updated_at": now_iso,
                    }
                )
                exclusions[ex_id] = ex
                changed_records_map[ex_id] = ex.model_dump() | {"record_type": "exclusion"}

            elif op_name == "coverage.rebase":
                target_cp_id = raw_op["target_plan_checkpoint_id"]
                target_cp = self.repo.get_checkpoint(plan_id, target_cp_id)
                if not target_cp:
                    raise RecordNotFoundError(plan_id, target_cp_id)

            elif op_name == "binding_set.create":
                bnd_id = raw_op.get("id") or str(uuid.uuid4())
                key = self.repo.allocate_key(plan_id, KEY_PREFIX_BIND) if not preview_only else f"{KEY_PREFIX_BIND}-preview"
                raw_bindings = raw_op.get("bindings", [])
                bindings_list = [TargetBinding.model_validate(b) for b in raw_bindings]
                raw_clocks = raw_op.get("clocks", [])
                clocks_list = [ClockDecl.model_validate(c) for c in raw_clocks]
                raw_resets = raw_op.get("resets", [])
                resets_list = [ResetDecl.model_validate(r) for r in raw_resets]
                bnd_set = TargetBindingSet(
                    id=bnd_id,
                    key=key,
                    title=raw_op.get("title") or raw_op["top_module"],
                    plan_id=plan_id,
                    source_snapshot_id=raw_op["source_snapshot_id"],
                    root_scope_id=raw_op["root_scope_id"],
                    dut_language=raw_op.get("dut_language", "verilog"),
                    top_module=raw_op["top_module"],
                    dut_manifest_digest=raw_op.get("dut_manifest_digest"),
                    resolved_parameters=raw_op.get("resolved_parameters", {}),
                    clocks=clocks_list,
                    resets=resets_list,
                    bindings=bindings_list,
                    authoring_state=AuthoringState(raw_op.get("authoring_state", AuthoringState.DRAFT)),
                    created_at=now_iso,
                    updated_at=now_iso,
                )
                binding_sets[bnd_id] = bnd_set
                changed_records_map[bnd_id] = bnd_set.model_dump() | {"record_type": "target_binding_set"}

            elif op_name == "binding_set.update":
                bnd_id = raw_op["id"]
                if bnd_id not in binding_sets:
                    raise RecordNotFoundError(plan_id, bnd_id)
                changes = dict(raw_op.get("changes", {}))
                if "bindings" in changes:
                    changes["bindings"] = [TargetBinding.model_validate(b) for b in changes["bindings"]]
                if "clocks" in changes:
                    changes["clocks"] = [ClockDecl.model_validate(c) for c in changes["clocks"]]
                if "resets" in changes:
                    changes["resets"] = [ResetDecl.model_validate(r) for r in changes["resets"]]
                changes["record_revision"] = binding_sets[bnd_id].record_revision + 1
                changes["updated_at"] = now_iso
                updated_bnd = binding_sets[bnd_id].model_copy(update=changes)
                binding_sets[bnd_id] = updated_bnd
                changed_records_map[bnd_id] = updated_bnd.model_dump() | {"record_type": "target_binding_set"}

            elif op_name == "binding_set.archive":
                bnd_id = raw_op["id"]
                if bnd_id not in binding_sets:
                    raise RecordNotFoundError(plan_id, bnd_id)
                updated_bnd = binding_sets[bnd_id].model_copy(update={"archived": True, "updated_at": now_iso})
                binding_sets[bnd_id] = updated_bnd
                changed_records_map[bnd_id] = updated_bnd.model_dump() | {"record_type": "target_binding_set"}

            elif op_name == "recipe.create":
                rec_id = raw_op.get("id") or str(uuid.uuid4())
                key = self.repo.allocate_key(plan_id, KEY_PREFIX_RCP) if not preview_only else f"{KEY_PREFIX_RCP}-preview"
                kind_val = RecipeKind(raw_op.get("kind", RecipeKind.SCENARIO))
                raw_ir = raw_op.get("test_ir")
                parsed_ir = TestIR.model_validate(raw_ir) if raw_ir else None
                raw_eb = raw_op.get("evidence_bindings", [])
                eb_list = [EvidenceBinding.model_validate(e) for e in raw_eb]
                raw_prov = raw_op.get("oracle_provenance")
                prov = OracleProvenance.model_validate(raw_prov) if raw_prov else OracleProvenance()
                state_val = RecipeState(raw_op.get("authoring_state", RecipeState.DRAFT))
                recipe = Recipe(
                    id=rec_id,
                    key=key,
                    plan_id=plan_id,
                    title=raw_op["title"],
                    description=raw_op.get("description", ""),
                    kind=kind_val,
                    coverage_checkpoint_id=raw_op["coverage_checkpoint_id"],
                    intent_ids=raw_op.get("intent_ids", []),
                    objective_ids=raw_op.get("objective_ids", []),
                    target_binding_set_id=raw_op.get("target_binding_set_id"),
                    test_ir=parsed_ir,
                    backend_configuration_id=raw_op.get("backend_configuration_id"),
                    evidence_bindings=eb_list,
                    oracle_provenance=prov,
                    authoring_state=state_val,
                    created_at=now_iso,
                    updated_at=now_iso,
                )
                recipes[rec_id] = recipe
                changed_records_map[rec_id] = recipe.model_dump() | {"record_type": "recipe"}

            elif op_name == "recipe.update":
                rec_id = raw_op["id"]
                if rec_id not in recipes:
                    raise RecordNotFoundError(plan_id, rec_id)
                existing_rec = recipes[rec_id]
                changes = dict(raw_op.get("changes", {}))
                if "test_ir" in changes and changes["test_ir"] is not None:
                    changes["test_ir"] = TestIR.model_validate(changes["test_ir"])
                if "evidence_bindings" in changes:
                    changes["evidence_bindings"] = [EvidenceBinding.model_validate(e) for e in changes["evidence_bindings"]]
                if "oracle_provenance" in changes:
                    changes["oracle_provenance"] = OracleProvenance.model_validate(changes["oracle_provenance"])
                if "kind" in changes:
                    changes["kind"] = RecipeKind(changes["kind"])
                if "authoring_state" in changes:
                    changes["authoring_state"] = RecipeState(changes["authoring_state"])
                changes["record_revision"] = existing_rec.record_revision + 1
                changes["updated_at"] = now_iso
                updated_rec = existing_rec.model_copy(update=changes)
                recipes[rec_id] = updated_rec
                changed_records_map[rec_id] = updated_rec.model_dump() | {"record_type": "recipe"}

            elif op_name == "recipe.set_state":
                rec_id = raw_op["id"]
                if rec_id not in recipes:
                    raise RecordNotFoundError(plan_id, rec_id)
                new_state = RecipeState(raw_op["state"])
                updated_rec = recipes[rec_id].model_copy(
                    update={
                        "authoring_state": new_state,
                        "record_revision": recipes[rec_id].record_revision + 1,
                        "updated_at": now_iso,
                    }
                )
                recipes[rec_id] = updated_rec
                changed_records_map[rec_id] = updated_rec.model_dump() | {"record_type": "recipe"}

            elif op_name == "recipe.bind_evidence":
                rec_id = raw_op["id"]
                if rec_id not in recipes:
                    raise RecordNotFoundError(plan_id, rec_id)
                eb_list = [EvidenceBinding.model_validate(e) for e in raw_op["evidence_bindings"]]
                updated_rec = recipes[rec_id].model_copy(
                    update={
                        "evidence_bindings": eb_list,
                        "record_revision": recipes[rec_id].record_revision + 1,
                        "updated_at": now_iso,
                    }
                )
                recipes[rec_id] = updated_rec
                changed_records_map[rec_id] = updated_rec.model_dump() | {"record_type": "recipe"}

            elif op_name == "recipe.archive":
                rec_id = raw_op["id"]
                if rec_id not in recipes:
                    raise RecordNotFoundError(plan_id, rec_id)
                updated_rec = recipes[rec_id].model_copy(update={"archived": True, "updated_at": now_iso})
                recipes[rec_id] = updated_rec
                changed_records_map[rec_id] = updated_rec.model_dump() | {"record_type": "recipe"}

            elif op_name == "backend_configuration.create":
                cfg_id = raw_op.get("id") or str(uuid.uuid4())
                key = self.repo.allocate_key(plan_id, KEY_PREFIX_BCFG) if not preview_only else f"{KEY_PREFIX_BCFG}-preview"
                plugin_id = raw_op["plugin_id"]
                plugin_version = raw_op["plugin_version"]
                pkg_digest = raw_op.get("package_digest") or sha256_digest(f"{plugin_id}:{plugin_version}".encode("utf-8"))
                config_json = raw_op.get("config_json", {})
                cfg_digest = sha256_digest(canonical_json(config_json))
                bcfg = BackendConfiguration(
                    id=cfg_id,
                    key=key,
                    title=raw_op.get("title") or raw_op.get("toolchain_identifier", "Reference backend"),
                    plan_id=plan_id,
                    plugin_id=plugin_id,
                    plugin_version=plugin_version,
                    package_digest=pkg_digest,
                    toolchain_identifier=raw_op.get("toolchain_identifier", "reference"),
                    version_constraints=raw_op.get("version_constraints", ">=1.0"),
                    config_json=config_json,
                    capability_snapshot=raw_op.get("capability_snapshot", {}),
                    configuration_digest=cfg_digest,
                    created_at=now_iso,
                )
                backend_configurations[cfg_id] = bcfg
                changed_records_map[cfg_id] = bcfg.model_dump() | {"record_type": "backend_configuration"}

            elif op_name == "external_implementation.register":
                rec_id = raw_op.get("id") or str(uuid.uuid4())
                key = self.repo.allocate_key(plan_id, KEY_PREFIX_RCP) if not preview_only else f"{KEY_PREFIX_RCP}-preview"
                raw_eb = raw_op.get("evidence_bindings", [])
                eb_list = [EvidenceBinding.model_validate(e) for e in raw_eb]
                raw_prov = raw_op.get("oracle_provenance")
                prov = OracleProvenance.model_validate(raw_prov) if raw_prov else OracleProvenance(
                    description=f"External realization via {raw_op.get('toolchain_identifier', 'external')}",
                    independently_authored=False,
                )
                recipe = Recipe(
                    id=rec_id,
                    key=key,
                    plan_id=plan_id,
                    title=raw_op["title"],
                    description=raw_op.get("description", "Registered external implementation"),
                    kind=RecipeKind.EXTERNAL,
                    coverage_checkpoint_id=raw_op["coverage_checkpoint_id"],
                    intent_ids=raw_op.get("intent_ids", []),
                    objective_ids=raw_op.get("objective_ids", []),
                    evidence_bindings=eb_list,
                    oracle_provenance=prov,
                    authoring_state=RecipeState.READY if eb_list else RecipeState.DRAFT,
                    created_at=now_iso,
                    updated_at=now_iso,
                )
                recipes[rec_id] = recipe
                changed_records_map[rec_id] = recipe.model_dump() | {"record_type": "recipe"}

            elif op_name == "implementation.rebase":
                target_cov_id = raw_op["target_coverage_checkpoint_id"]
                target_cp = self.repo.get_checkpoint(plan_id, target_cov_id)
                if not target_cp or target_cp.layer != "coverage":
                    raise RecordNotFoundError(plan_id, target_cov_id)

        # Validate whole final state invariants:
        validate_section_hierarchy(sections)
        validate_intent_dependencies(intents)

        # Prepare response
        changed_records = [rec for k, rec in changed_records_map.items() if not k.startswith("audit:")]
        new_rev = plan.edit_revision if preview_only else plan.edit_revision + 1

        response_data = {
            "edit_revision": new_rev,
            "changed_records": changed_records,
            "diagnostics": diagnostics,
            "request_id": request_id,
            "created_at": now_iso,
        }

        if preview_only:
            return response_data

        # The repository rechecks base_edit_revision at the actual write boundary.
        # Records, draft revision, replay response and event must advance together.
        # Human-readable key allocation happens earlier and may leave gaps on failure.
        event_data = {
            "event_id": str(uuid.uuid4()),
            "kind": "plan.changed",
            "changed_ids": [r["id"] for r in changed_records],
            "created_at": now_iso,
        }

        self.repo.execute_command_transaction(
            plan_id=plan_id,
            request_id=request_id,
            base_edit_revision=base_edit_revision,
            payload_hash=payload_hash,
            header_updates=header_changes if header_changes else None,
            audit_updates=list(source_audits.values()),
            saved_records=changed_records,
            deleted_record_ids=deleted_record_ids,
            response_data=response_data,
            event_data=event_data,
        )

        return response_data
