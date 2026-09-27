"""Hierarchy tree generation and ordering projection for Verification Planner."""

from __future__ import annotations

from typing import Any

from testplan_service.domain.models import Intent, Section


def build_hierarchy_tree(
    scopes: list[dict[str, Any]],
    sections: dict[str, Section],
    intents: dict[str, Intent],
    filter_scope_id: str | None = None,
) -> list[dict[str, Any]]:
    """Build a nested hierarchy tree for UI navigation and REST read projections."""
    # Organize sections and intents by scope
    sections_by_scope: dict[str, list[Section]] = {}
    for sec in sections.values():
        if not sec.archived:
            sections_by_scope.setdefault(sec.scope_id, []).append(sec)

    intents_by_scope: dict[str, list[Intent]] = {}
    for intent in intents.values():
        if not intent.archived:
            intents_by_scope.setdefault(intent.scope_id, []).append(intent)

    def build_section_node(sec: Section) -> dict[str, Any]:
        # Children are ordered by sec.child_ids
        children: list[dict[str, Any]] = []
        visited_child_ids = set()

        for cid in sec.child_ids:
            if cid in sections and not sections[cid].archived and sections[cid].parent_section_id == sec.id:
                children.append(build_section_node(sections[cid]))
                visited_child_ids.add(cid)
            elif cid in intents and not intents[cid].archived and intents[cid].parent_section_id == sec.id:
                intent_item = intents[cid]
                children.append({
                    "id": intent_item.id,
                    "key": intent_item.key,
                    "kind": "intent",
                    "title": intent_item.title,
                    "authoring_state": intent_item.authoring_state.value,
                    "priority": intent_item.priority_override.value if intent_item.priority_override else sec.default_priority.value,
                    "requirement_count": len(intent_item.requirement_ids),
                    "children": [],
                })
                visited_child_ids.add(cid)

        # Fallback for any children whose IDs weren't listed in child_ids
        for candidate_sec in sections.values():
            if candidate_sec.parent_section_id == sec.id and not candidate_sec.archived and candidate_sec.id not in visited_child_ids:
                children.append(build_section_node(candidate_sec))
        for candidate_intent in intents.values():
            if candidate_intent.parent_section_id == sec.id and not candidate_intent.archived and candidate_intent.id not in visited_child_ids:
                children.append({
                    "id": candidate_intent.id,
                    "key": candidate_intent.key,
                    "kind": "intent",
                    "title": candidate_intent.title,
                    "authoring_state": candidate_intent.authoring_state.value,
                    "priority": candidate_intent.priority_override.value if candidate_intent.priority_override else sec.default_priority.value,
                    "requirement_count": len(candidate_intent.requirement_ids),
                    "children": [],
                })

        # Count total descendants
        descendant_intents = sum(1 for c in children if c["kind"] == "intent") + sum(c.get("descendant_intents", 0) for c in children if c["kind"] == "section")

        return {
            "id": sec.id,
            "key": sec.key,
            "kind": "section",
            "title": sec.title,
            "description": sec.description,
            "scope_id": sec.scope_id,
            "default_priority": sec.default_priority.value,
            "children": children,
            "descendant_intents": descendant_intents,
        }

    scope_nodes: list[dict[str, Any]] = []
    for sc in scopes:
        s_id = sc.get("occurrence_id") or sc.get("id") or ""
        if filter_scope_id and s_id != filter_scope_id:
            continue

        scope_sections = sections_by_scope.get(s_id, [])
        scope_intents = intents_by_scope.get(s_id, [])

        root_sections = [s for s in scope_sections if s.parent_section_id is None]
        root_intents = [i for i in scope_intents if i.parent_section_id is None]

        children: list[dict[str, Any]] = []
        for r_sec in root_sections:
            children.append(build_section_node(r_sec))
        for r_int in root_intents:
            children.append({
                "id": r_int.id,
                "key": r_int.key,
                "kind": "intent",
                "title": r_int.title,
                "authoring_state": r_int.authoring_state.value,
                "priority": r_int.priority_override.value if r_int.priority_override else "medium",
                "requirement_count": len(r_int.requirement_ids),
                "children": [],
            })

        descendant_intents = sum(1 for c in children if c["kind"] == "intent") + sum(c.get("descendant_intents", 0) for c in children if c["kind"] == "section")

        scope_nodes.append({
            "id": s_id,
            "key": s_id,
            "kind": "scope",
            "scope_kind": sc.get("kind", "component"),
            "name": sc.get("name", s_id),
            "type_name": sc.get("component_name", ""),
            "path": sc.get("path", s_id),
            "children": children,
            "descendant_intents": descendant_intents,
        })

    return scope_nodes
