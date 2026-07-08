"""Action registry and built-in pseudo SystemC actions.

Actions are server-side functions that consume immutable input snapshots and
return artifact metadata plus diagnostics. The built-ins here are intentionally
small pseudo actions used to exercise the full run/writeback pipeline before
real synthesis or simulation providers are plugged in.
"""

import importlib
import json
import pathlib
import time
import typing

import spec2gds.agent_spec.models as agent_models
import spec2gds.agent_spec.storage.repository as agent_repository


ActionHandler = typing.Callable[[agent_models.ActionRunContext], agent_models.ActionResult]


class RegisteredAction:
    """Action metadata plus its Python handler."""

    spec: agent_models.ActionSpec
    handler: ActionHandler

    def __init__(self, spec: agent_models.ActionSpec, handler: ActionHandler) -> None:
        self.spec = spec
        self.handler = handler


class ActionRegistry:
    """Registry populated from Python modules and optional deployment config."""

    _actions: dict[str, RegisteredAction]

    def __init__(self) -> None:
        """Create an empty action registry."""
        self._actions = {}

    def register(self, spec: agent_models.ActionSpec, handler: ActionHandler) -> None:
        """Register one action specification and its handler callable."""
        self._actions[spec.action_id] = RegisteredAction(spec=spec, handler=handler)

    def get(self, action_id: str) -> RegisteredAction:
        """Return an enabled action or raise a user-facing error."""
        if action_id not in self._actions:
            raise KeyError(f"Unknown action: {action_id}")
        action = self._actions[action_id]
        if not action.spec.enabled:
            raise ValueError(f"Action is disabled: {action_id}")
        return action

    def list_actions(self) -> list[agent_models.ActionSpec]:
        """Return copies of enabled action specs for API/UI use."""
        return [action.spec.model_copy(deep=True) for action in self._actions.values() if action.spec.enabled]

    def actions_for_tags(self, tags: list[str]) -> list[agent_models.ActionSpec]:
        """Return enabled actions whose required tags match the selected block."""
        tag_set = set(tags)
        matches: list[agent_models.ActionSpec] = []
        for action in self._actions.values():
            if not action.spec.enabled:
                continue
            if not action.spec.required_tags or tag_set.intersection(action.spec.required_tags):
                matches.append(action.spec.model_copy(deep=True))
        return matches

    def load_python_modules(self, module_names: list[str]) -> None:
        """Import extension modules and let each one register its actions."""
        for module_name in module_names:
            module = importlib.import_module(module_name)
            register_actions = getattr(module, "register_actions")
            register_actions(self)

    def apply_config(self, config: dict[str, typing.Any]) -> None:
        """Apply a tiny deployment config, currently used to enable/disable actions."""
        actions_config = config.get("actions", {})
        if not isinstance(actions_config, dict):
            return
        for action_id, action_config in actions_config.items():
            if action_id not in self._actions or not isinstance(action_config, dict):
                continue
            enabled = action_config.get("enabled")
            if isinstance(enabled, bool):
                self._actions[action_id].spec.enabled = enabled


def load_config(path: str) -> dict[str, typing.Any]:
    """Load a small JSON-or-YAML deployment config without adding dependencies."""
    config_path = pathlib.Path(path)
    text = config_path.read_text(encoding="utf-8")
    stripped = text.strip()
    if not stripped:
        return {}
    if stripped.startswith("{"):
        return typing.cast(dict[str, typing.Any], json.loads(stripped))
    return _parse_simple_yaml(stripped)


def _parse_simple_yaml(text: str) -> dict[str, typing.Any]:
    """Parse the small YAML subset accepted for action configuration.

    This avoids adding a YAML dependency for config that is currently just a
    nested mapping of action ids to scalar settings.
    """
    result: dict[str, typing.Any] = {}
    stack: list[tuple[int, dict[str, typing.Any]]] = [(-1, result)]
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        key, value = _split_yaml_key_value(line.strip())
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value == "":
            child: dict[str, typing.Any] = {}
            parent[key] = child
            stack.append((indent, child))
            continue
        parent[key] = _parse_yaml_scalar(value)
    return result


def _split_yaml_key_value(line: str) -> tuple[str, str]:
    """Split one `key: value` YAML-like line."""
    if ":" not in line:
        raise ValueError(f"Invalid config line: {line}")
    key, value = line.split(":", 1)
    return key.strip(), value.strip()


def _parse_yaml_scalar(value: str) -> typing.Any:
    """Parse booleans, flat string lists, and quoted strings from config."""
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value.startswith("[") and value.endswith("]"):
        raw_items = value[1:-1].strip()
        if not raw_items:
            return []
        return [item.strip().strip("\"'") for item in raw_items.split(",")]
    return value.strip("\"'")


def create_default_registry(config_path: str | None = None) -> ActionRegistry:
    """Build the built-in registry and apply an optional config file."""
    registry = ActionRegistry()
    register_actions(registry)
    if config_path is not None:
        registry.apply_config(load_config(config_path))
    return registry


def register_actions(registry: ActionRegistry) -> None:
    """Register the built-in pseudo actions used by tests and local demos."""
    registry.register(_pseudo_spec("systemc.perf.pseudo", "SystemC Performance", ["systemc-perf"]), _systemc_perf)
    registry.register(
        _pseudo_spec(
            "systemc.bitaccurate.pseudo",
            "SystemC Bit-Accurate",
            ["systemc-bitaccurate"],
        ),
        _systemc_bitaccurate,
    )
    registry.register(_inspect_spec(), _inspect)


def _pseudo_spec(action_id: str, title: str, required_tags: list[str]) -> agent_models.ActionSpec:
    """Construct a standard pseudo action spec with common demo parameters."""
    return agent_models.ActionSpec(
        action_id=action_id,
        title=title,
        summary=f"Pseudo {title} pipeline that returns fixed artifact metadata.",
        version="0.1.0",
        provider="spec2gds.agent_spec.actions",
        required_tags=required_tags,
        parameters=[
            agent_models.ActionParameter(name="delay_seconds", parameter_type="number", default=0.01),
            agent_models.ActionParameter(name="output_name", parameter_type="string", default="model.txt"),
        ],
        output_roles=[action_id],
    )


def _inspect_spec() -> agent_models.ActionSpec:
    """Construct the metadata-only inspection action spec."""
    return agent_models.ActionSpec(
        action_id="agent_spec.inspect",
        title="Inspect Agent Spec",
        summary="Validate graph, tags, versions, and artifact references.",
        version="0.1.0",
        provider="spec2gds.agent_spec.actions",
        required_tags=[],
        output_roles=[],
    )


def _systemc_perf(context: agent_models.ActionRunContext) -> agent_models.ActionResult:
    """Produce a deterministic pseudo SystemC performance artifact."""
    return _fixed_artifact(context, "systemc-perf-model", "text/x-systemc", "Pseudo SystemC performance artifact")


def _systemc_bitaccurate(context: agent_models.ActionRunContext) -> agent_models.ActionResult:
    """Produce a deterministic pseudo SystemC bit-accurate artifact."""
    return _fixed_artifact(context, "systemc-bitaccurate-model", "text/x-systemc", "Pseudo SystemC bit-accurate artifact")


def _inspect(context: agent_models.ActionRunContext) -> agent_models.ActionResult:
    """Return a successful diagnostic proving the snapshot could be inspected."""
    return agent_models.ActionResult(
        diagnostics=[
            agent_models.AgentSpecDiagnostic(
                severity="info",
                source="agent_spec.inspect",
                message=f"Snapshot {context.snapshot.snapshot_id} is valid.",
            )
        ]
    )


def _fixed_artifact(
    context: agent_models.ActionRunContext,
    artifact_kind: str,
    media_type: str,
    summary: str,
) -> agent_models.ActionResult:
    """Write a tiny deterministic artifact and return its metadata record."""
    delay = context.snapshot.parameters.get("delay_seconds", 0.01)
    if isinstance(delay, int | float):
        # Bound demo sleeps so a user-provided parameter cannot stall the local
        # server for an unreasonable amount of time.
        time.sleep(max(0.0, min(float(delay), 2.0)))
    selected = context.snapshot.selected_versions[0]
    # The artifact body is deliberately simple and traceable so tests can verify
    # the action/read-set/writeback loop without external toolchains.
    artifact_body = (
        f"{summary}\n"
        f"action={context.action.action_id}\n"
        f"block={selected.block_id}\n"
        f"version={selected.version_id}\n"
    ).encode("utf-8")
    artifact_id = agent_repository.stable_id("artifact")
    artifact_dir = pathlib.Path(context.sidecar_root) / "runs" / context.run_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    output_name = context.snapshot.parameters.get("output_name", "model.txt")
    if not isinstance(output_name, str) or not output_name:
        output_name = "model.txt"
    artifact_path = artifact_dir / output_name
    artifact_path.write_bytes(artifact_body)
    # ArtifactRef is the durable handle stored in the `.spec` graph; the bytes
    # themselves live in the sidecar so the document package stays compact.
    artifact = agent_models.ArtifactRef(
        artifact_id=artifact_id,
        artifact_kind=artifact_kind,
        media_type=media_type,
        summary=summary,
        sha256=agent_repository.stable_hash(artifact_body),
        external_uri=f"file://{artifact_path}",
        producer=context.action.action_id,
        source_trace=agent_models.SourceTrace(
            block_id=selected.block_id,
            version_id=selected.version_id,
            artifact_refs=[artifact.artifact_id for artifact in context.snapshot.artifact_refs],
        ),
        role=context.action.action_id,
        created_at=agent_repository.utc_now(),
    )
    return agent_models.ActionResult(artifacts=[artifact])
