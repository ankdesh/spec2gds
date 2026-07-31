"""Public V1 API for deterministic, IP-XACT-centered ``.spec`` packages.

This package owns the full post-pivot model: package I/O, validated immutable
SpecIR, revision-guarded edits, local action execution, artifacts, and change
proposals.  The HTTP composition root and browser client are intentionally
available from their dedicated modules instead of being imported eagerly.
"""

from spec2gds.agent_spec.spec_format.archive import SpecPackage, SpecValidationError
from spec2gds.agent_spec.spec_format.actions import (
    ActionDefinition,
    ActionExecution,
    ActionRegistry,
    ActionService,
    ActionSnapshot,
    ActivityStore,
    ArtifactRef,
    ArtifactSidecar,
    ChangeProposal,
    create_reference_registry,
)
from spec2gds.agent_spec.spec_format.ir import (
    AbstractionDefinitionIR,
    BusDefinitionIR,
    ComponentIR,
    ConnectionIR,
    DesignIR,
    InstanceIR,
    SpecRevision,
)
from spec2gds.agent_spec.spec_format.models import (
    ComponentComposition,
    DocumentEntry,
    EntityRef,
    NarrativeBlock,
    NarrativeDocument,
    SpecManifest,
)
from spec2gds.agent_spec.spec_format.transactions import EditResult, SpecEditTransaction

__all__ = [
    "ComponentComposition",
    "ComponentIR",
    "ConnectionIR",
    "DesignIR",
    "DocumentEntry",
    "ActionDefinition",
    "ActionExecution",
    "ActionRegistry",
    "ActionService",
    "ActionSnapshot",
    "ActivityStore",
    "ArtifactRef",
    "ArtifactSidecar",
    "ChangeProposal",
    "EditResult",
    "EntityRef",
    "NarrativeBlock",
    "NarrativeDocument",
    "InstanceIR",
    "BusDefinitionIR",
    "AbstractionDefinitionIR",
    "SpecRevision",
    "SpecManifest",
    "SpecPackage",
    "SpecEditTransaction",
    "SpecValidationError",
    "create_reference_registry",
]
