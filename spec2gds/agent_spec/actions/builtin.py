"""Action registry and declarative example SystemC actions.

Actions describe work an external executor may perform.  They deliberately do
not execute commands inside agent-spec; the runner dispatches a durable run and
an executor later reports completion through the action API.
"""

import importlib
import json
import pathlib
import typing

import spec2gds.agent_spec.models as agent_models


class RegisteredAction:
    """Action metadata and lifecycle hooks owned by the server."""

    def __init__(
        self,
        spec: agent_models.ActionSpec,
        precondition: typing.Callable[[str, dict[str, typing.Any]], list[agent_models.ConditionCheck]] | None = None,
        postcondition: typing.Callable[[dict[str, typing.Any]], list[agent_models.ConditionCheck]] | None = None,
    ) -> None:
        self.spec = spec
        self.precondition = precondition
        self.postcondition = postcondition


class ActionRegistry:
    """Registry populated from Python modules and deployment configuration."""

    def __init__(self) -> None:
        self._actions: dict[str, RegisteredAction] = {}

    def register(
        self,
        spec: agent_models.ActionSpec,
        precondition: typing.Callable[[str, dict[str, typing.Any]], list[agent_models.ConditionCheck]] | None = None,
        postcondition: typing.Callable[[dict[str, typing.Any]], list[agent_models.ConditionCheck]] | None = None,
    ) -> None:
        """Register one action and optional action-specific condition checks."""
        self._actions[spec.action_id] = RegisteredAction(spec, precondition, postcondition)

    def get(self, action_id: str) -> RegisteredAction:
        """Return one enabled action or raise a user-facing error."""
        if action_id not in self._actions:
            raise KeyError(f"Unknown action: {action_id}")
        action = self._actions[action_id]
        if not action.spec.enabled:
            raise ValueError(f"Action is disabled: {action_id}")
        return action

    def list_actions(self) -> list[agent_models.ActionSpec]:
        """Return all enabled actions. Availability is determined by checks."""
        return [item.spec.model_copy(deep=True) for item in self._actions.values() if item.spec.enabled]

    def load_python_modules(self, module_names: list[str]) -> None:
        for module_name in module_names:
            module = importlib.import_module(module_name)
            getattr(module, "register_actions")(self)

    def apply_config(self, config: dict[str, typing.Any]) -> None:
        actions_config = config.get("actions", {})
        if not isinstance(actions_config, dict):
            return
        for action_id, action_config in actions_config.items():
            if action_id in self._actions and isinstance(action_config, dict) and isinstance(action_config.get("enabled"), bool):
                self._actions[action_id].spec.enabled = action_config["enabled"]


def load_config(path: str) -> dict[str, typing.Any]:
    """Load the small JSON/YAML action enablement configuration."""
    text = pathlib.Path(path).read_text(encoding="utf-8").strip()
    if not text:
        return {}
    if text.startswith("{"):
        return typing.cast(dict[str, typing.Any], json.loads(text))
    result: dict[str, typing.Any] = {}
    current: dict[str, typing.Any] | None = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        stripped = line.strip()
        if stripped == "actions:":
            result["actions"] = {}
        elif line.startswith("  ") and stripped.endswith(":"):
            current = {}
            typing.cast(dict[str, typing.Any], result["actions"])[stripped[:-1]] = current
        elif line.startswith("    ") and current is not None and ":" in stripped:
            key, value = stripped.split(":", 1)
            current[key] = value.strip().lower() == "true" if value.strip().lower() in {"true", "false"} else value.strip()
    return result


def _schema(properties: dict[str, typing.Any], required: list[str] | None = None) -> dict[str, typing.Any]:
    return {"type": "object", "properties": properties, "required": required or [], "additionalProperties": False}


def _systemc_action(action_id: str, title: str, role: str) -> agent_models.ActionSpec:
    return agent_models.ActionSpec(
        action_id=action_id,
        title=title,
        summary=f"Request an external executor to produce a {title.lower()} artifact.",
        version="1.0.0",
        provider="spec2gds.agent_spec.actions",
        executor_id=action_id,
        input_schema=_schema({"output_name": {"type": "string", "title": "Output name", "default": "model.txt"}}),
        report_schema=_schema(
            {
                "summary": {"type": "string", "title": "Summary"},
                "details": {"type": "string", "title": "Details", "default": ""},
            },
            ["summary"],
        ),
        output_roles=[role],
    )


def _delayed_report_action() -> agent_models.ActionSpec:
    """Return a local five-second action used to exercise report rendering."""
    return agent_models.ActionSpec(
        action_id="agent_spec.delayed_report",
        title="Delayed report demo",
        summary="Wait five seconds, then create a pseudo executor report for this section.",
        version="1.0.0",
        provider="spec2gds.agent_spec.actions",
        executor_id="agent-spec.pseudo-delayed-report",
        input_schema=_schema({}),
        report_schema=_schema(
            {
                "summary": {"type": "string", "title": "Summary"},
                "details": {"type": "string", "title": "Details"},
            },
            ["summary", "details"],
        ),
    )


def _non_empty_section(block_id: str, inputs: dict[str, typing.Any]) -> list[agent_models.ConditionCheck]:
    del inputs
    return [
        agent_models.ConditionCheck(
            check_id="section-selected",
            severity="info",
            message=f"Section {block_id} is selected for execution.",
            passed=True,
        )
    ]


def register_actions(registry: ActionRegistry) -> None:
    """Register examples used by the local editor and external executor tests."""
    registry.register(_systemc_action("systemc.perf", "SystemC Performance", "systemc.perf.model"), _non_empty_section)
    registry.register(
        _systemc_action("systemc.bitaccurate", "SystemC Bit-Accurate", "systemc.bitaccurate.model"),
        _non_empty_section,
    )
    registry.register(_delayed_report_action(), _non_empty_section)


def create_default_registry(config_path: str | None = None) -> ActionRegistry:
    registry = ActionRegistry()
    register_actions(registry)
    if config_path:
        registry.apply_config(load_config(config_path))
    return registry
