"""Explicit registry, plugin loader, decorators, and direct contract harness."""

from __future__ import annotations

import importlib
import typing
from dataclasses import dataclass

import pydantic

from spec2gds.agent_spec.activities.contracts import (
    Activity,
    ActivityAvailability,
    ActivityContext,
    ActivityDefinition,
    ActivityOutputWriter,
    ActivityResult,
    ActivityScopes,
    ActivitySelectionContext,
    ActivityWorkspaceWriter,
    BaseActivity,
    ContextRenderContext,
    ContextRenderer,
    NeverCancelled,
    RenderedContext,
)
from spec2gds.agent_spec.activities.snapshot import ActivitySnapshot
from spec2gds.agent_spec.activities.view import SpecAccess
from spec2gds.agent_spec.spec_format.models import StrictModel


class ExtensionDiagnostic(StrictModel):
    """One disabled plugin and its actionable loading error."""

    import_path: str
    message: str


class SpecExtensionRegistry:
    """One deterministic registry with distinct Activity and renderer roles."""

    def __init__(self) -> None:
        self._activities: dict[str, Activity] = {}
        self._renderers: dict[str, ContextRenderer] = {}
        self._diagnostics: list[ExtensionDiagnostic] = []

    @property
    def diagnostics(self) -> tuple[ExtensionDiagnostic, ...]:
        """Return immutable plugin-load failures without hiding valid plugins."""
        return tuple(self._diagnostics)

    def register_activity(self, extension: Activity) -> None:
        """Validate and register an Activity without silent replacement."""
        definition = ActivityDefinition.model_validate(extension.definition.model_dump(mode="json"))
        if not issubclass(extension.report_model, pydantic.BaseModel):
            raise TypeError("Activity report_model must be a Pydantic BaseModel type.")
        if definition.report_schema != extension.report_model.model_json_schema():
            raise ValueError("Activity report_schema must match report_model.model_json_schema().")
        self._assert_id_available(definition.activity_id)
        self._activities[definition.activity_id] = extension

    def register_context_renderer(self, extension: ContextRenderer) -> None:
        """Validate and register a Context Renderer without replacement."""
        definition = extension.definition
        self._assert_id_available(definition.renderer_id)
        self._renderers[definition.renderer_id] = extension

    def activity(self, activity_id: str) -> Activity:
        """Resolve one registered Activity or raise a descriptive key error."""
        if activity_id not in self._activities:
            raise KeyError(f"Unknown Activity: {activity_id}")
        return self._activities[activity_id]

    def context_renderer(self, renderer_id: str) -> ContextRenderer:
        """Resolve one registered Context Renderer by its stable identifier."""
        if renderer_id not in self._renderers:
            raise KeyError(f"Unknown Context Renderer: {renderer_id}")
        return self._renderers[renderer_id]

    def activities(self) -> tuple[ActivityDefinition, ...]:
        """Return Activity catalog metadata sorted by identifier."""
        return tuple(self._activities[key].definition for key in sorted(self._activities))

    def context_renderers(self) -> tuple[typing.Any, ...]:
        """Return renderer catalog metadata sorted by identifier."""
        return tuple(self._renderers[key].definition for key in sorted(self._renderers))

    def add_diagnostic(self, import_path: str, reason: BaseException) -> None:
        """Record one isolated extension-loading failure for host display."""
        self._diagnostics.append(
            ExtensionDiagnostic(import_path=import_path, message=f"{type(reason).__name__}: {reason}")
        )

    def merge(self, other: "SpecExtensionRegistry") -> None:
        """Atomically merge a plugin-local registry after checking all IDs."""
        incoming = set(other._activities) | set(other._renderers)
        if len(incoming) != len(other._activities) + len(other._renderers):
            raise ValueError("One plugin reused an ID across extension roles.")
        existing = set(self._activities) | set(self._renderers)
        collisions = sorted(existing & incoming)
        if collisions:
            raise ValueError("Extension ids are already registered: " + ", ".join(collisions))
        self._activities.update(other._activities)
        self._renderers.update(other._renderers)

    def _assert_id_available(self, extension_id: str) -> None:
        if extension_id in self._activities or extension_id in self._renderers:
            raise ValueError(f"Extension id is already registered: {extension_id}")


AvailabilityFunction = typing.Callable[[ActivitySelectionContext], ActivityAvailability]
ActivityFunction = typing.Callable[[ActivityContext], ActivityResult]


@dataclass
class FunctionActivity(BaseActivity):
    """Adapter allowing ordinary functions to satisfy the Activity protocol."""

    definition: ActivityDefinition
    report_model: type[pydantic.BaseModel]
    function: ActivityFunction
    availability_function: AvailabilityFunction | None = None

    def availability(self, context: ActivitySelectionContext) -> ActivityAvailability:
        """Combine the base scope check with the decorated custom preflight."""
        base = super().availability(context)
        if not base.available or self.availability_function is None:
            return base
        return self.availability_function(context)

    def run(self, context: ActivityContext) -> ActivityResult:
        """Delegate execution to the decorated Activity function."""
        return self.function(context)


def activity(
    *,
    activity_id: str,
    version: str,
    title: str,
    description: str,
    scopes: ActivityScopes,
    report_model: type[pydantic.BaseModel],
    artifact_roles: tuple[str, ...] = (),
    may_propose_changes: bool = False,
    requires_workspace_output: bool = False,
    availability: AvailabilityFunction | None = None,
) -> typing.Callable[[ActivityFunction], FunctionActivity]:
    """Decorate a plain function as a fully described Activity."""

    def decorate(function: ActivityFunction) -> FunctionActivity:
        return FunctionActivity(
            definition=ActivityDefinition(
                activity_id=activity_id,
                version=version,
                title=title,
                description=description,
                scopes=scopes,
                report_schema=report_model.model_json_schema(),
                artifact_roles=artifact_roles,
                may_propose_changes=may_propose_changes,
                requires_workspace_output=requires_workspace_output,
            ),
            report_model=report_model,
            function=function,
            availability_function=availability,
        )

    return decorate


def load_extension_modules(
    import_paths: typing.Iterable[str],
    registry: SpecExtensionRegistry | None = None,
) -> SpecExtensionRegistry:
    """Load ``module:callable`` plugins, disabling one module on any error."""
    result = registry or SpecExtensionRegistry()
    for import_path in import_paths:
        temporary = SpecExtensionRegistry()
        try:
            module_name, separator, callable_name = import_path.partition(":")
            if not separator or not module_name or not callable_name:
                raise ValueError("Plugin import paths must use module:callable syntax.")
            module = importlib.import_module(module_name)
            register = getattr(module, callable_name)
            if not callable(register):
                raise TypeError("Configured plugin registration target is not callable.")
            register(temporary)
            result.merge(temporary)
        except Exception as exc:  # Plugin errors are isolated and made visible by contract.
            result.add_diagnostic(import_path, exc)
    return result


def activity_availability(
    registry: SpecExtensionRegistry,
    activity_id: str,
    snapshot: ActivitySnapshot,
) -> ActivityAvailability:
    """Evaluate one Activity's pure preflight contract."""
    extension = registry.activity(activity_id)
    context = ActivitySelectionContext(
        snapshot=snapshot.manifest,
        spec=SpecAccess(snapshot.revision, snapshot.target),
    )
    return extension.availability(context)


def invoke_activity(
    registry: SpecExtensionRegistry,
    activity_id: str,
    snapshot: ActivitySnapshot,
    workspace: ActivityWorkspaceWriter | None = None,
) -> ActivityResult:
    """Direct reference invocation used by tests and future host adapters."""
    extension = registry.activity(activity_id)
    spec = SpecAccess(snapshot.revision, snapshot.target)
    availability = extension.availability(
        ActivitySelectionContext(snapshot=snapshot.manifest, spec=spec)
    )
    if not availability.available:
        raise ValueError("Activity is unavailable: " + "; ".join(availability.diagnostics))
    if extension.definition.requires_workspace_output and workspace is None:
        raise ValueError("Activity requires a workspace output writer.")
    context = ActivityContext(
        snapshot=snapshot.manifest,
        spec=spec,
        outputs=ActivityOutputWriter(),
        cancellation=NeverCancelled(),
        workspace=workspace,
    )
    result = ActivityResult.model_validate(extension.run(context).model_dump(mode="python"))
    return _validate_result(extension, snapshot, result)


def render_context(
    registry: SpecExtensionRegistry,
    renderer_id: str,
    snapshot: ActivitySnapshot,
) -> RenderedContext:
    """Directly invoke and verify one deterministic Context Renderer."""
    renderer = registry.context_renderer(renderer_id)
    if not renderer.definition.scopes.supports(snapshot.target):
        raise ValueError("Context Renderer does not support this snapshot scope.")
    result = renderer.render(
        ContextRenderContext(
            snapshot=snapshot.manifest,
            spec=SpecAccess(snapshot.revision, snapshot.target),
        )
    )
    if result.renderer_id != renderer.definition.renderer_id:
        raise ValueError("Rendered context renderer_id does not match the registry definition.")
    if result.renderer_version != renderer.definition.version:
        raise ValueError("Rendered context version does not match the registry definition.")
    if result.snapshot_id != snapshot.manifest.snapshot_id:
        raise ValueError("Rendered context snapshot_id does not match its input.")
    if result.document_id != snapshot.revision.document_id:
        raise ValueError("Rendered context document_id does not match its input.")
    if result.source_revision_hash != snapshot.revision.source_revision_hash:
        raise ValueError("Rendered context source hash does not match its input.")
    if result.target != snapshot.target:
        raise ValueError("Rendered context target does not match its input.")
    return result


def _validate_result(
    extension: Activity,
    snapshot: ActivitySnapshot,
    result: ActivityResult,
) -> ActivityResult:
    normalized_report = extension.report_model.model_validate(result.report).model_dump(mode="json")
    allowed_roles = set(extension.definition.artifact_roles)
    for artifact in result.artifacts:
        if artifact.role not in allowed_roles:
            raise ValueError(f"Activity returned undeclared artifact role: {artifact.role}")
        for reference in artifact.source_entities:
            snapshot.revision.resolve(reference)
    if result.proposals and not extension.definition.may_propose_changes:
        raise ValueError("Activity is not allowed to return source proposals.")
    return result.model_copy(update={"report": normalized_report})
