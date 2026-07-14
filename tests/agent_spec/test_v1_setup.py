import spec2gds.agent_spec.actions as actions


def test_action_registry_lists_all_enabled_actions() -> None:
    registry = actions.create_default_registry()
    action_ids = {action.action_id for action in registry.list_actions()}
    assert action_ids == {"systemc.perf", "systemc.bitaccurate", "agent_spec.delayed_report"}
    assert all(action.input_schema["type"] == "object" for action in registry.list_actions())
