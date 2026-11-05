"""Component definition structures for library components."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from spec_catalog_service.catalog.schemas import TimingInfo


@dataclass(frozen=True)
class PortDef:
    """Definition of a component port."""

    name: str
    direction: str  # "in", "out", "inout"
    range_expr: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class ParamDef:
    """Definition of a parameter."""

    name: str
    rtl_type: str
    default_value: str
    description: str
    min_value: int | None = None
    max_value: int | None = None  # None or static int; dynamic bounds evaluated by validator


@dataclass
class ComponentDef:
    """Full normative contract and implementation for one library component."""

    id: str
    category: str
    version: str = "1.0.0"
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    licence: str = "NOASSERTION"
    implementation: str = "body_sv"
    contract_anchor: str = ""
    phase: int = 1
    parameters: list[ParamDef] = field(default_factory=list)
    ports: list[PortDef] = field(default_factory=list)
    systemverilog: str = ""
    presets: dict[str, dict[str, str]] = field(default_factory=dict)
    timing: TimingInfo = field(default_factory=lambda: TimingInfo(latency="0", throughput="1", reset="none"))
    limitations: list[str] = field(default_factory=list)
    is_stateful: bool = False

    # Validation callback: returns list of error messages if parameter values violate bounds/constraints
    validate_params: Callable[[dict[str, int]], list[str]] | None = None

    # Reference simulator factory: creates a simulator instance for a given parameter map
    create_reference: Callable[[dict[str, int]], Any] | None = None
