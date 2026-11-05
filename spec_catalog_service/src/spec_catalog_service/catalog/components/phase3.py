"""Phase 3 Component definitions aggregator (Part 1: 12 components).

Aggregates:
- Basic & Saturating Arithmetic (5 components): add_sub, saturating_add_sub, comparator, min_max, absolute_value.
- Multipliers, Dividers & Roots (7 components): multiplier_comb, multiplier_pipeline, multiplier_iterative,
  mac, divider_iterative, divider_pipeline, integer_sqrt.
"""

from __future__ import annotations

from spec_catalog_service.catalog.components.models import ComponentDef
from spec_catalog_service.catalog.components.phase3_arithmetic import PHASE3_ARITHMETIC_COMPONENTS
from spec_catalog_service.catalog.components.phase3_mult_div import PHASE3_MULT_DIV_COMPONENTS

PHASE3_COMPONENTS: list[ComponentDef] = [
    *PHASE3_ARITHMETIC_COMPONENTS,
    *PHASE3_MULT_DIV_COMPONENTS,
]

PHASE3_COMPONENTS_BY_ID: dict[str, ComponentDef] = {c.id: c for c in PHASE3_COMPONENTS}
