"""Office-compatible `.spec` archive mechanics and validation."""

from spec2gds.agent_spec.package.archive import AgentSpecArchive
from spec2gds.agent_spec.package.verifier import (
    ContainerVerificationReport,
    ContainerVerifier,
    FileVerification,
    LinkVerification,
)

__all__ = [
    "AgentSpecArchive",
    "ContainerVerificationReport",
    "ContainerVerifier",
    "FileVerification",
    "LinkVerification",
]
