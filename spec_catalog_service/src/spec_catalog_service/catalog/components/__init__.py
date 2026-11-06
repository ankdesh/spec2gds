"""Component definitions for spec library."""

from spec_catalog_service.catalog.components.models import ComponentDef, ParamDef, PortDef
from spec_catalog_service.catalog.components.phase1 import (
    PHASE1_COMPONENTS,
    PHASE1_COMPONENTS_BY_ID,
)
from spec_catalog_service.catalog.components.phase2 import (
    PHASE2_COMPONENTS,
    PHASE2_COMPONENTS_BY_ID,
)
from spec_catalog_service.catalog.components.adapters import (
    ADAPTER_COMPONENTS,
    DIVIDER_STREAM_ADAPTER_DEF,
    MULTIPLIER_STREAM_ADAPTER_DEF,
)
from spec_catalog_service.catalog.components.phase3 import (
    PHASE3_COMPONENTS,
    PHASE3_COMPONENTS_BY_ID,
)

ALL_COMPONENTS_BY_ID: dict[str, ComponentDef] = {
    **PHASE1_COMPONENTS_BY_ID,
    **PHASE2_COMPONENTS_BY_ID,
    **PHASE3_COMPONENTS_BY_ID,
    **{c.id: c for c in ADAPTER_COMPONENTS},
}

__all__ = [
    "ComponentDef",
    "ParamDef",
    "PortDef",
    "ADAPTER_COMPONENTS",
    "DIVIDER_STREAM_ADAPTER_DEF",
    "MULTIPLIER_STREAM_ADAPTER_DEF",
    "PHASE1_COMPONENTS",
    "PHASE1_COMPONENTS_BY_ID",
    "PHASE2_COMPONENTS",
    "PHASE2_COMPONENTS_BY_ID",
    "PHASE3_COMPONENTS",
    "PHASE3_COMPONENTS_BY_ID",
    "ALL_COMPONENTS_BY_ID",
]
