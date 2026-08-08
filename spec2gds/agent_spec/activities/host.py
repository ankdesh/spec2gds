"""Replaceable host ports around the stable Activity SDK contracts."""

from __future__ import annotations

import typing

from spec2gds.agent_spec.activities.contracts import ActivityDefinition, ActivityResult
from spec2gds.agent_spec.activities.snapshot import ActivitySnapshot
from spec2gds.agent_spec.spec_format.ir import SpecRevision
from spec2gds.agent_spec.spec_format.models import EntityRef


class SnapshotFactory(typing.Protocol):
    """Capture a full immutable source revision for any execution host."""

    def create(
        self,
        revision: SpecRevision,
        target: EntityRef | None = None,
    ) -> ActivitySnapshot: ...


class ActivityCatalog(typing.Protocol):
    """Discover definitions without depending on how Activities are launched."""

    def activities(self) -> tuple[ActivityDefinition, ...]: ...


class ActivityInvoker(typing.Protocol):
    """Invoke one Activity without prescribing queue, process, or transport."""

    def invoke(self, activity_id: str, snapshot: ActivitySnapshot) -> ActivityResult: ...


class ActivityResultSink(typing.Protocol):
    """Accept a validated result without prescribing its durable storage."""

    def accept(
        self,
        definition: ActivityDefinition,
        snapshot: ActivitySnapshot,
        result: ActivityResult,
    ) -> None: ...
