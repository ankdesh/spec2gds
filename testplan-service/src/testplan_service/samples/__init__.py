"""Pre-built sample testplan definitions for diverse hardware verification domains."""

from __future__ import annotations

from testplan_service.models.testplan import TestPlanDocument
from testplan_service.samples.alu_plan import AluTestPlanBuilder
from testplan_service.samples.crossbar_plan import CrossbarTestPlanBuilder
from testplan_service.samples.fifo_plan import FifoTestPlanBuilder
from testplan_service.samples.uart_plan import UartTestPlanBuilder


def build_all_sample_plans() -> list[TestPlanDocument]:
    """Instantiate and return all pre-configured domain sample testplans."""
    return [
        AluTestPlanBuilder().build(),
        UartTestPlanBuilder().build(),
        FifoTestPlanBuilder().build(),
        CrossbarTestPlanBuilder().build(),
    ]


__all__ = [
    "AluTestPlanBuilder",
    "CrossbarTestPlanBuilder",
    "FifoTestPlanBuilder",
    "UartTestPlanBuilder",
    "build_all_sample_plans",
]
