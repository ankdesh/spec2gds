from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from spec2gds_assistant.database import AssistantDatabase


def test_thread_history_and_review_state_are_persistent(tmp_path: Path) -> None:
    database = AssistantDatabase(tmp_path / "assistant.db")
    database.initialize()
    thread = database.create_thread(thread_id="thread_1")
    bound = database.bind_circuit(
        thread["id"],
        base_url="http://127.0.0.1:4100/api/circuit-designer/v1",
        document_id="fixture_simple",
    )
    assert bound and bound["document_id"] == "fixture_simple"
    message = database.append_message(
        thread["id"],
        message_id="message_1",
        parent_id=None,
        role="user",
        content={"id": "message_1", "role": "user", "content": []},
    )
    assert database.list_messages(thread["id"]) == [message]
    review = database.upsert_review(
        proposal_id="proposal_1",
        thread_id=thread["id"],
        state="ready",
        artifact={"kind": "circuit_change_proposal"},
        diff={"added": [], "removed": [], "changed": [], "connections_changed": []},
    )
    assert database.get_review(thread["id"], "proposal_1") == review

    reopened = AssistantDatabase(tmp_path / "assistant.db")
    reopened_thread = reopened.get_thread(thread["id"])
    assert reopened_thread
    assert reopened_thread["document_id"] == bound["document_id"]
    assert reopened_thread["circuit_base_url"] == bound["circuit_base_url"]
    assert reopened.list_messages(thread["id"]) == [message]
    assert reopened.list_reviews(thread["id"]) == [review]


def test_chat_cannot_be_rebound_to_a_different_circuit(tmp_path: Path) -> None:
    database = AssistantDatabase(tmp_path / "assistant.db")
    database.initialize()
    database.create_thread(thread_id="thread_1")
    database.bind_circuit(
        "thread_1",
        base_url="http://127.0.0.1:4100/api/circuit-designer/v1",
        document_id="first",
    )
    with pytest.raises(ValueError, match="already bound"):
        database.bind_circuit(
            "thread_1",
            base_url="http://127.0.0.1:4100/api/circuit-designer/v1",
            document_id="second",
        )


def test_spec_binding_and_running_conversation_summary(tmp_path: Path) -> None:
    database = AssistantDatabase(tmp_path / "assistant.db")
    database.initialize()
    thread = database.create_thread(thread_id="thread_spec", domain="spec")
    bound = database.bind_spec(
        thread["id"],
        base_url="http://127.0.0.1:8000",
        document_id="spec_demo",
        entity_kind="component",
        entity_id="component_leaf",
    )
    assert bound and bound["domain"] == "spec"
    assert bound["entity_id"] == "component_leaf"
    for index in range(13):
        database.append_message(
            thread["id"],
            message_id=f"message_{index}",
            parent_id=f"message_{index - 1}" if index else None,
            role="user" if index % 2 == 0 else "assistant",
            content={"content": [{"type": "text", "text": f"message text {index}"}]},
        )
    context = database.conversation_context(thread["id"])
    assert context["summarized_message_count"] == 5
    assert "message text 0" in context["summary"]
    assert len(context["recent_messages"]) == 8


def test_existing_circuit_database_migrates_additively(tmp_path: Path) -> None:
    path = tmp_path / "assistant.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE threads (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL,
                circuit_base_url TEXT, document_id TEXT,
                include_png INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO threads VALUES (
                'old', 'Old circuit', 'regular',
                'http://127.0.0.1:4100/api/circuit-designer/v1', 'fixture', 0,
                '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'
            )
            """
        )
    database = AssistantDatabase(path)
    database.initialize()
    migrated = database.get_thread("old")
    assert migrated and migrated["domain"] == "circuit"
    assert migrated["service_base_url"] == migrated["circuit_base_url"]
