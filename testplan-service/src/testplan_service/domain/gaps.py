"""Typed deterministic coverage gaps domain model and classifications."""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from testplan_service.constants import MAX_TEXT_LENGTH, MAX_TITLE_LENGTH


class GapCode(str, Enum):
    """The 16 deterministic gap classification codes."""

    SOURCE_UNREVIEWED = "source_unreviewed"
    REQUIREMENT_UNMAPPED = "requirement_unmapped"
    INTENT_POLICY_MISSING = "intent_policy_missing"
    OBJECTIVE_INCOMPLETE = "objective_incomplete"
    CHECKING_MISSING = "checking_missing"
    DANGLING_MAPPING = "dangling_mapping"
    BIN_UNPLANNED = "bin_unplanned"
    IMPLEMENTATION_MISSING = "implementation_missing"
    BACKEND_UNSUPPORTED = "backend_unsupported"
    EVIDENCE_MISSING = "evidence_missing"
    BIN_UNHIT = "bin_unhit"
    CHECK_FAILED = "check_failed"
    PROOF_INCONCLUSIVE = "proof_inconclusive"
    STALE_EVIDENCE = "stale_evidence"
    UNBOUND_RESULT = "unbound_result"
    WEAK_CHECK_EVIDENCE = "weak_check_evidence"


class GapSeverity(str, Enum):
    """Severity classification for a coverage gap."""

    ERROR = "error"
    WARNING = "warning"
    ADVISORY = "advisory"


class CoverageGap(BaseModel):
    """Deterministic actionable gap record."""

    model_config = ConfigDict(extra="ignore")

    id: str
    gap_code: GapCode
    severity: GapSeverity
    title: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)
    explanation: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    affected_record_ids: list[str] = Field(default_factory=list)
    profile_id: str | None = None
    primary_action: dict[str, Any] = Field(default_factory=dict)
