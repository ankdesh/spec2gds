"""Validation logic for structural invariants and intent readiness."""

from __future__ import annotations

from typing import Any

from testplan_service.constants import MAX_HIERARCHY_DEPTH
from testplan_service.domain.enums import (
    AuthoringState,
    IntentOrigin,
    IssueSeverity,
    IssueState,
    RequirementDisposition,
)
from testplan_service.domain.models import Intent, Issue, Requirement, Section
from testplan_service.exceptions import CycleDetectedError, MaxDepthExceededError


def validate_section_hierarchy(sections: dict[str, Section]) -> None:
    """Verify that section parenting forms valid trees without cycles or depth overflow."""
    for section_id, section in sections.items():
        if section.archived:
            continue
        visited = set()
        curr_id: str | None = section_id
        depth = 1
        while curr_id is not None:
            if curr_id in visited:
                raise CycleDetectedError(f"Cycle detected in section hierarchy containing '{section_id}'.")
            visited.add(curr_id)
            parent_sec = sections.get(curr_id)
            if not parent_sec:
                break
            curr_id = parent_sec.parent_section_id
            if curr_id:
                depth += 1
                if depth > MAX_HIERARCHY_DEPTH:
                    raise MaxDepthExceededError(depth, MAX_HIERARCHY_DEPTH)


def validate_intent_dependencies(intents: dict[str, Intent]) -> None:
    """Verify that intent dependency graph has no cycles."""
    visited: set[str] = set()
    visiting: set[str] = set()

    def dfs(node_id: str) -> None:
        if node_id in visiting:
            raise CycleDetectedError(f"Cycle detected in intent dependencies involving '{node_id}'.")
        if node_id in visited:
            return
        visiting.add(node_id)
        intent = intents.get(node_id)
        if intent and not intent.archived:
            for dep_id in intent.dependency_ids:
                if dep_id in intents:
                    dfs(dep_id)
        visiting.remove(node_id)
        visited.add(node_id)

    for i_id in intents:
        if i_id not in visited:
            dfs(i_id)


def check_intent_readiness(
    intent: Intent,
    requirements: dict[str, Requirement],
    issues: dict[str, Issue],
) -> list[dict[str, Any]]:
    """Return diagnostic errors blocking readiness for this intent."""
    diagnostics: list[dict[str, Any]] = []

    if not intent.preconditions.strip():
        diagnostics.append({
            "code": "intent.missing_preconditions",
            "field": "preconditions",
            "message": "Preconditions ('Given') must be specified.",
            "severity": "error",
        })

    if not intent.trigger.strip():
        diagnostics.append({
            "code": "intent.missing_trigger",
            "field": "trigger",
            "message": "Trigger event ('When') must be specified.",
            "severity": "error",
        })

    if not intent.expected_behavior.strip():
        diagnostics.append({
            "code": "intent.missing_expected_behavior",
            "field": "expected_behavior",
            "message": "Expected behavior ('Then') must be specified.",
            "severity": "error",
        })

    if not intent.observations:
        diagnostics.append({
            "code": "intent.missing_observations",
            "field": "observations",
            "message": "At least one observable semantic output must be listed.",
            "severity": "error",
        })
    else:
        for idx, obs in enumerate(intent.observations):
            if not obs.name.strip() or not obs.description.strip():
                diagnostics.append({
                    "code": "intent.incomplete_observation",
                    "field": f"observations[{idx}]",
                    "message": "Observation must have non-empty name and description.",
                    "severity": "error",
                })

    # Requirement linkage
    verifiable_reqs = [
        req_id
        for req_id in intent.requirement_ids
        if req_id in requirements
        and not requirements[req_id].archived
        and requirements[req_id].disposition == RequirementDisposition.VERIFY
    ]
    if not verifiable_reqs:
        diagnostics.append({
            "code": "intent.no_verifiable_requirement",
            "field": "requirement_ids",
            "message": "Intent must link to at least one active requirement with 'verify' disposition.",
            "severity": "error",
        })

    # Rationale check if derived
    if intent.origin == IntentOrigin.DERIVED_INTERPRETATION:
        if not intent.rationale or not intent.rationale.strip():
            diagnostics.append({
                "code": "intent.missing_rationale",
                "field": "rationale",
                "message": "Derived interpretation intent requires an explicit rationale citing source.",
                "severity": "error",
            })

    # Blocking issues check
    blocking_issues = [
        iss_id
        for iss_id in intent.issue_ids
        if iss_id in issues
        and not issues[iss_id].archived
        and issues[iss_id].severity == IssueSeverity.BLOCKING
        and issues[iss_id].state == IssueState.OPEN
    ]
    if blocking_issues:
        diagnostics.append({
            "code": "intent.unresolved_blocking_issue",
            "field": "issue_ids",
            "message": f"Intent has open blocking issues: {', '.join(blocking_issues)}",
            "severity": "error",
        })

    return diagnostics


def is_semantic_intent_change(current: Intent, update_data: dict[str, Any]) -> bool:
    """Determine if an update modifies semantic fields that force resetting ready intent to draft."""
    semantic_keys = {
        "preconditions",
        "trigger",
        "expected_behavior",
        "observations",
        "rationale",
        "origin",
        "participants",
        "requirement_ids",
        "dependency_ids",
    }
    for key in semantic_keys:
        if key in update_data:
            current_val = getattr(current, key)
            new_val = update_data[key]
            # Convert models to dict for comparison if needed
            if key == "observations":
                obs_dicts = [o.model_dump() if hasattr(o, "model_dump") else o for o in current_val]
                if obs_dicts != new_val:
                    return True
            elif current_val != new_val:
                return True
    return False
