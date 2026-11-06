"""Unit tests for Phase 3 Batch 4 (Monitoring & Control) reference models."""

from spec_catalog_service.catalog.components.phase3_models import (
    WatchdogRef,
    TimeoutMonitorRef,
    InterruptControllerRef,
    FaultCollectorRef,
    LockstepCompareRef,
)


def test_watchdog_ref():
    ref = WatchdogRef({"W": 4})
    # Reset state
    assert ref.count == 0 and ref.expired == 0

    # Count up to 3
    ref.eval({"enable_i": 1, "kick_i": 0, "clear_i": 0, "limit_i": 3})
    assert ref.count == 1 and ref.expired == 0
    ref.eval({"enable_i": 1, "kick_i": 0, "clear_i": 0, "limit_i": 3})
    assert ref.count == 2 and ref.expired == 0
    # Reaching limit
    ref.eval({"enable_i": 1, "kick_i": 0, "clear_i": 0, "limit_i": 3})
    assert ref.count == 3 and ref.expired == 1

    # Enabled kick clears count, but expired stays sticky
    ref.eval({"enable_i": 1, "kick_i": 1, "clear_i": 0, "limit_i": 3})
    assert ref.count == 0 and ref.expired == 1

    # Clear clears both
    ref.eval({"enable_i": 1, "kick_i": 0, "clear_i": 1, "limit_i": 3})
    assert ref.count == 0 and ref.expired == 0

    # Limit = 0 expires immediately on first enabled non-kick edge
    ref.eval({"enable_i": 1, "kick_i": 0, "clear_i": 0, "limit_i": 0})
    assert ref.count == 0 and ref.expired == 1


def test_timeout_monitor_ref():
    ref = TimeoutMonitorRef({"W": 4})

    # Start with limit 3
    r = ref.eval({"start_i": 1, "complete_i": 0, "cancel_i": 0, "limit_i": 3})
    assert r["busy_o"] == 1 and r["timeout_o"] == 0

    # Cycle 1
    r = ref.eval({"start_i": 0, "complete_i": 0, "cancel_i": 0, "limit_i": 3})
    assert r["busy_o"] == 1 and r["timeout_o"] == 0

    # Cycle 2
    r = ref.eval({"start_i": 0, "complete_i": 0, "cancel_i": 0, "limit_i": 3})
    assert r["busy_o"] == 1 and r["timeout_o"] == 0

    # Cycle 3 -> timeout pulse
    r = ref.eval({"start_i": 0, "complete_i": 0, "cancel_i": 0, "limit_i": 3})
    assert r["busy_o"] == 0 and r["timeout_o"] == 1

    # Zero limit pulses immediately
    r = ref.eval({"start_i": 1, "complete_i": 0, "cancel_i": 0, "limit_i": 0})
    assert r["busy_o"] == 0 and r["timeout_o"] == 1

    # Completion on expiry edge wins over timeout
    ref.eval({"start_i": 1, "complete_i": 0, "cancel_i": 0, "limit_i": 1})
    r = ref.eval({"start_i": 0, "complete_i": 1, "cancel_i": 0, "limit_i": 1})
    assert r["busy_o"] == 0 and r["timeout_o"] == 0


def test_interrupt_controller_ref():
    ref = InterruptControllerRef({"N": 4})

    # Assert IRQ 0 and 2, but only 2 is enabled
    r = ref.eval({"irq_i": 0b0101, "enable_i": 0b0100, "clear_i": 0b0000})
    assert r["pending_o"] == 0b0101
    assert r["irq_o"] == 1
    assert r["valid_o"] == 1
    assert r["index_o"] == 2

    # Clear IRQ 2
    r = ref.eval({"irq_i": 0b0000, "enable_i": 0b0100, "clear_i": 0b0100})
    assert r["pending_o"] == 0b0001
    assert r["irq_o"] == 0
    assert r["valid_o"] == 0
    assert r["index_o"] == 0

    # Unmask IRQ 0
    r = ref.eval({"irq_i": 0b0000, "enable_i": 0b0001, "clear_i": 0b0000})
    assert r["pending_o"] == 0b0001
    assert r["irq_o"] == 1
    assert r["valid_o"] == 1
    assert r["index_o"] == 0


def test_fault_collector_ref():
    ref = FaultCollectorRef({"N": 4})

    # First fault on bit 1 and 3
    r = ref.eval({"fault_i": 0b1010, "clear_i": 0})
    assert r["sticky_o"] == 0b1010
    assert r["any_o"] == 1
    assert r["first_valid_o"] == 1
    assert r["first_index_o"] == 1  # lowest fault index

    # Clear bit 1 while bit 3 remains -> first_index remains 1
    r = ref.eval({"fault_i": 0b0000, "clear_i": 0b0010})
    assert r["sticky_o"] == 0b1000
    assert r["any_o"] == 1
    assert r["first_valid_o"] == 1
    assert r["first_index_o"] == 1  # retained!

    # Clear bit 3 -> sticky becomes 0, first_valid becomes 0
    r = ref.eval({"fault_i": 0b0000, "clear_i": 0b1000})
    assert r["sticky_o"] == 0b0000
    assert r["any_o"] == 0
    assert r["first_valid_o"] == 0


def test_lockstep_compare_ref():
    ref = LockstepCompareRef({"W": 8})

    # Both invalid -> no mismatch
    r = ref.eval({"valid_a_i": 0, "data_a_i": 10, "valid_b_i": 0, "data_b_i": 20, "clear_i": 0})
    assert r["mismatch_o"] == 0 and r["sticky_o"] == 0

    # One valid, one invalid -> mismatch
    r = ref.eval({"valid_a_i": 1, "data_a_i": 10, "valid_b_i": 0, "data_b_i": 20, "clear_i": 0})
    assert r["mismatch_o"] == 1 and r["sticky_o"] == 1

    # Both valid, same data -> no mismatch, but sticky stays 1
    r = ref.eval({"valid_a_i": 1, "data_a_i": 10, "valid_b_i": 1, "data_b_i": 10, "clear_i": 0})
    assert r["mismatch_o"] == 0 and r["sticky_o"] == 1

    # Clear sticky
    r = ref.eval({"valid_a_i": 1, "data_a_i": 10, "valid_b_i": 1, "data_b_i": 10, "clear_i": 1})
    assert r["mismatch_o"] == 0 and r["sticky_o"] == 0
