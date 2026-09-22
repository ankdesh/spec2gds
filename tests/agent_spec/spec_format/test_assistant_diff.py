from spec2gds.agent_spec.spec_format.assistant import _json_diff


def test_assistant_json_diff_is_deterministic_for_keyed_sections() -> None:
    before = [
        {"section_id": "b", "title": "Before B", "value": 1},
        {"section_id": "a", "title": "Before A", "value": 1},
    ]
    after = [
        {"section_id": "a", "title": "After A", "value": 2},
        {"section_id": "c", "title": "Added C", "value": 1},
    ]

    assert _json_diff(before, after) == [
        {"path": "$[a].title", "change": "changed", "before": "Before A", "after": "After A"},
        {"path": "$[a].value", "change": "changed", "before": 1, "after": 2},
        {"path": "$[b]", "change": "removed", "before": before[0], "after": None},
        {"path": "$[c]", "change": "added", "before": None, "after": after[1]},
    ]


def test_assistant_json_diff_reports_no_change_for_equal_semantics() -> None:
    value = {"section_id": "same", "rows": [{"row_id": "one", "value": "x"}]}
    assert _json_diff(value, value) == []
