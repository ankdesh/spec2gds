"""IP-XACT-centered V1 `.spec` source package support.

This subsystem intentionally sits beside the legacy ODT implementation until
the V1.4 cutover.  It owns the deterministic package format, V1 source
schemas, and profile validation; it does not implement actions or editing UI.
"""

from spec2gds.agent_spec.spec_format.archive import SpecPackage, SpecValidationError
from spec2gds.agent_spec.spec_format.models import (
    ComponentComposition,
    DocumentEntry,
    EntityRef,
    NarrativeBlock,
    NarrativeDocument,
    SpecManifest,
)
from spec2gds.agent_spec.spec_format.samples import build_v1_sample

__all__ = [
    "ComponentComposition",
    "DocumentEntry",
    "EntityRef",
    "NarrativeBlock",
    "NarrativeDocument",
    "SpecManifest",
    "SpecPackage",
    "SpecValidationError",
    "build_v1_sample",
]
