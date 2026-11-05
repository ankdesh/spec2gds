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

ALL_COMPONENTS_BY_ID: dict[str, ComponentDef] = {
    **PHASE1_COMPONENTS_BY_ID,
    **PHASE2_COMPONENTS_BY_ID,
}

__all__ = [
    "ComponentDef",
    "ParamDef",
    "PortDef",
    "PHASE1_COMPONENTS",
    "PHASE1_COMPONENTS_BY_ID",
    "PHASE2_COMPONENTS",
    "PHASE2_COMPONENTS_BY_ID",
    "ALL_COMPONENTS_BY_ID",
]
