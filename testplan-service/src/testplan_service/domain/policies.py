"""Intent evidence policy, branch alternatives, and waiver domain models."""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from testplan_service.constants import MAX_TEXT_LENGTH, MAX_TITLE_LENGTH


class PolicyBranch(BaseModel):
    """An alternative or required branch of coverage objectives for an intent."""

    model_config = ConfigDict(extra="ignore")

    id: str
    title: str = Field(default="", max_length=MAX_TITLE_LENGTH)
    objective_ids: list[str] = Field(min_length=1)
    justifications: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def model_validate(cls, obj: Any, *args: Any, **kwargs: Any) -> PolicyBranch:
        if isinstance(obj, dict):
            d = dict(obj)
            if "id" not in d and "branch_id" in d:
                d["id"] = d["branch_id"]
            if "title" not in d:
                d["title"] = d.get("id", "Branch")
            return super().model_validate(d, *args, **kwargs)
        return super().model_validate(obj, *args, **kwargs)


class IntentEvidencePolicy(BaseModel):
    """Explicit mapping from an atomic intent to its evidence objectives."""

    model_config = ConfigDict(extra="ignore")

    id: str
    record_type: str = "policy"
    record_revision: int = 1
    intent_id: str
    intent_hash: str = ""
    branches: list[PolicyBranch] = Field(default_factory=list)
    supplemental_objective_ids: list[str] = Field(default_factory=list)
    rationale: str | None = Field(default=None, max_length=MAX_TEXT_LENGTH)
    archived: bool = False
    created_at: str
    updated_at: str


class IntentWaiver(BaseModel):
    """Explicit documented acceptance of incomplete verification for an intent."""

    model_config = ConfigDict(extra="ignore")

    id: str
    intent_id: str
    profile_ids: list[str] = Field(default_factory=list)
    checkpoint_id: str
    reason: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    designer_label: str = Field(validation_alias=AliasChoices("designer_label", "owner_label"))
    expires_at: str  # ISO 8601 UTC
    milestone_label: str | None = None
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    created_at: str
    revoked: bool = False
