"""IP-XACT-centered V1 `.spec` source package support.

This subsystem intentionally sits beside the legacy ODT implementation until
the V1.4 cutover.  It owns the deterministic package format, V1 source
schemas, and profile validation; it does not implement actions or editing UI.
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
from spec2gds.agent_spec.spec_format.samples import build_v1_sample
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
    "build_v1_sample",
    "create_reference_registry",
]
