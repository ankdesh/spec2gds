"""Phase 3 Component definitions aggregator (All 32 components across 4 batches).

Aggregates:
- Basic & Saturating Arithmetic (5 components): add_sub, saturating_add_sub, comparator, min_max, absolute_value.
- Multipliers, Dividers & Roots (7 components): multiplier_comb, multiplier_pipeline, multiplier_iterative,
  mac, divider_iterative, divider_pipeline, integer_sqrt.
- DSP (7 components): fixed_round, fixed_saturate, fixed_scale, dot_product, fir_filter, cic_decimator, cic_interpolator.
- CORDIC (2 components): cordic_rotate, cordic_vector.
- Integrity & ECC (6 components): parity, crc_serial, crc_parallel, lfsr, secded_encode, secded_decode.
- Monitoring & Control (5 components): watchdog, timeout_monitor, interrupt_controller, fault_collector, lockstep_compare.
"""

from __future__ import annotations

from spec_catalog_service.catalog.components.models import ComponentDef
from spec_catalog_service.catalog.components.phase3_arithmetic import PHASE3_ARITHMETIC_COMPONENTS
from spec_catalog_service.catalog.components.phase3_control import PHASE3_CONTROL_COMPONENTS
from spec_catalog_service.catalog.components.phase3_cordic import PHASE3_CORDIC_COMPONENTS
from spec_catalog_service.catalog.components.phase3_dsp import PHASE3_DSP_COMPONENTS
from spec_catalog_service.catalog.components.phase3_integrity import PHASE3_INTEGRITY_COMPONENTS
from spec_catalog_service.catalog.components.phase3_mult_div import PHASE3_MULT_DIV_COMPONENTS

PHASE3_COMPONENTS: list[ComponentDef] = [
    *PHASE3_ARITHMETIC_COMPONENTS,
    *PHASE3_MULT_DIV_COMPONENTS,
    *PHASE3_DSP_COMPONENTS,
    *PHASE3_CORDIC_COMPONENTS,
    *PHASE3_INTEGRITY_COMPONENTS,
    *PHASE3_CONTROL_COMPONENTS,
]

PHASE3_COMPONENTS_BY_ID: dict[str, ComponentDef] = {c.id: c for c in PHASE3_COMPONENTS}
