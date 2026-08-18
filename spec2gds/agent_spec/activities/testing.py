"""Small direct test harness for third-party Activity plugin packages."""

from __future__ import annotations

from dataclasses import dataclass

from spec2gds.agent_spec.activities.contracts import (
    ActivityResult,
    ActivityWorkspaceWriter,
    RenderedContext,
)
from spec2gds.agent_spec.activities.registry import (
    SpecExtensionRegistry,
    invoke_activity,
    render_context,
)
from spec2gds.agent_spec.activities.snapshot import ActivitySnapshot
from spec2gds.agent_spec.spec_format.ir import SpecRevision
from spec2gds.agent_spec.spec_format.models import EntityRef


@dataclass(frozen=True)
class ActivityTestHarness:
    """Build snapshots and invoke registered extensions without choosing a host."""

    registry: SpecExtensionRegistry
    workspace: ActivityWorkspaceWriter | None = None

    def snapshot(
        self,
        revision: SpecRevision,
        target: EntityRef | None = None,
    ) -> ActivitySnapshot:
        """Capture a test revision through the same public snapshot contract."""
        return ActivitySnapshot.create(revision, target)

    def invoke(self, activity_id: str, snapshot: ActivitySnapshot) -> ActivityResult:
        """Invoke a registered Activity with the harness workspace capability."""
        return invoke_activity(self.registry, activity_id, snapshot, self.workspace)

    def render(self, renderer_id: str, snapshot: ActivitySnapshot) -> RenderedContext:
        """Render snapshot context through a registered deterministic renderer."""
        return render_context(self.registry, renderer_id, snapshot)
