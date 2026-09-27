"""Synthetic Two-FIFO pipeline design Activity Snapshot generator."""

from __future__ import annotations

from spec2gds.agent_spec.activities import ActivitySnapshot
from spec2gds.agent_spec.spec_format.archive import SpecPackage
from spec2gds.agent_spec.spec_format.ir import SpecRevision
from spec2gds.agent_spec.spec_format.models import EntityRef, NarrativeBlock

from testplan_service.fixtures.fifo_snapshot import _fifo_component_xml

_NS = "http://www.accellera.org/XMLSchema/IPXACT/1685-2022"


def _pipeline_design_xml(renamed_ingress: bool = False) -> bytes:
    display_ingress = "ingress_renamed" if renamed_ingress else "ingress"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ipxact:design xmlns:ipxact="{_NS}" xml:id="fifo_pipeline">
  <ipxact:vendor>spec2gds.example</ipxact:vendor>
  <ipxact:library>fifo</ipxact:library>
  <ipxact:name>fifo_pipeline</ipxact:name>
  <ipxact:version>1.0</ipxact:version>
  <ipxact:componentInstances>
    <ipxact:componentInstance>
      <ipxact:instanceName>ingress</ipxact:instanceName>
      <ipxact:displayName>{display_ingress}</ipxact:displayName>
      <ipxact:componentRef vendor="spec2gds.example" library="fifo" name="sync_fifo" version="1.0"/>
    </ipxact:componentInstance>
    <ipxact:componentInstance>
      <ipxact:instanceName>egress</ipxact:instanceName>
      <ipxact:displayName>egress</ipxact:displayName>
      <ipxact:componentRef vendor="spec2gds.example" library="fifo" name="sync_fifo" version="1.0"/>
    </ipxact:componentInstance>
  </ipxact:componentInstances>
</ipxact:design>
""".encode("utf-8")


def build_two_fifo_snapshot() -> ActivitySnapshot:
    """Build the synthetic Two-FIFO design Activity Snapshot according to Section 7."""
    doc_id = "two_fifo_spec"
    package = SpecPackage.create(doc_id)

    # 1. Add component definition sync_fifo
    comp_entry = package.add_document("component", _fifo_component_xml())

    # 2. Add design definition fifo_pipeline
    design_entry = package.add_document("design", _pipeline_design_xml())

    # 3. Add narrative blocks
    package.narrative = package.narrative.model_copy(
        update={
            "blocks": [
                # Component level sections (same as FIFO)
                NarrativeBlock(
                    block_id="sec-reset",
                    type="section",
                    text="Reset: Reset clears the queue and sets count=0, empty=1, full=0, dout=0. Active-high reset overrides simultaneous read and write requests.",
                ),
                NarrativeBlock(
                    block_id="sec-write",
                    type="section",
                    text="Normal write: Write appends one word when space is available (count < DEPTH). Din is accepted on rising clock edge.",
                ),
                NarrativeBlock(
                    block_id="sec-read",
                    type="section",
                    text="Normal read: Read returns the oldest word when data is available (count > 0). Dout publishes accepted word after edge.",
                ),
                NarrativeBlock(
                    block_id="sec-full",
                    type="section",
                    text="Boundaries - Full write: Full write preserves occupancy and preserves queued data; no item is accepted when full (count == DEPTH).",
                ),
                NarrativeBlock(
                    block_id="sec-empty",
                    type="section",
                    text="Boundaries - Empty read: Empty read preserves queue state and dout output; no item is returned when empty (count == 0).",
                ),
                NarrativeBlock(
                    block_id="sec-both",
                    type="section",
                    text="Simultaneous requests: Mid-occupancy accepts both read and write; full accepts read only; empty accepts write only.",
                ),
                NarrativeBlock(
                    block_id="sec-order",
                    type="section",
                    text="Ordering: FIFO queue retains sequence ordering across wrap-around index boundaries without data corruption.",
                ),
                NarrativeBlock(
                    block_id="sec-flags",
                    type="section",
                    text="Status flags: Full and empty status flags consistently agree with count (full=(count==DEPTH), empty=(count==0)).",
                ),
                # Design level composition sections
                NarrativeBlock(
                    block_id="sec-pipe-order",
                    type="section",
                    text="Pipeline Ordering: Preserve ordering and data integrity across both FIFOs without data loss.",
                ),
                NarrativeBlock(
                    block_id="sec-pipe-stall",
                    type="section",
                    text="Pipeline Stall: Stalled egress preserves the held bridge register word during backpressure.",
                ),
                NarrativeBlock(
                    block_id="sec-pipe-bubble",
                    type="section",
                    text="Pipeline Handshake: Bridge register never requests ingress read while holding data, inserting a clean transfer bubble.",
                ),
                NarrativeBlock(
                    block_id="sec-pipe-reset",
                    type="section",
                    text="Pipeline Reset: Reset clears all pending data across both FIFO queues and the intermediate bridge holding register.",
                ),
            ]
        }
    )

    revision = SpecRevision.from_package(package)
    target = EntityRef(document_id=doc_id, entity_id="fifo_pipeline", entity_kind="design")
    return ActivitySnapshot.create(revision, target=target)


def get_two_fifo_snapshot_bytes() -> bytes:
    """Return deterministic bytes for the Two-FIFO Activity Snapshot."""
    return build_two_fifo_snapshot().to_bytes()


def build_renamed_two_fifo_snapshot() -> ActivitySnapshot:
    """Build Two-FIFO design snapshot with renamed instance display/path, keeping stable occurrence ID."""
    doc_id = "two_fifo_spec"
    package = SpecPackage.create(doc_id)

    comp_entry = package.add_document("component", _fifo_component_xml())
    design_entry = package.add_document("design", _pipeline_design_xml(renamed_ingress=True))

    package.narrative = package.narrative.model_copy(
        update={
            "blocks": [
                NarrativeBlock(
                    block_id="sec-reset",
                    type="section",
                    text="Reset: Reset clears the queue and sets count=0, empty=1, full=0, dout=0. Active-high reset overrides simultaneous read and write requests.",
                ),
                NarrativeBlock(
                    block_id="sec-write",
                    type="section",
                    text="Normal write: Write appends one word when space is available (count < DEPTH). Din is accepted on rising clock edge.",
                ),
                NarrativeBlock(
                    block_id="sec-read",
                    type="section",
                    text="Normal read: Read returns the oldest word when data is available (count > 0). Dout publishes accepted word after edge.",
                ),
                NarrativeBlock(
                    block_id="sec-full",
                    type="section",
                    text="Boundaries - Full write: Full write preserves occupancy and preserves queued data; no item is accepted when full (count == DEPTH).",
                ),
                NarrativeBlock(
                    block_id="sec-empty",
                    type="section",
                    text="Boundaries - Empty read: Empty read preserves queue state and dout output; no item is returned when empty (count == 0).",
                ),
                NarrativeBlock(
                    block_id="sec-both",
                    type="section",
                    text="Simultaneous requests: Mid-occupancy accepts both read and write; full accepts read only; empty accepts write only.",
                ),
                NarrativeBlock(
                    block_id="sec-order",
                    type="section",
                    text="Ordering: FIFO queue retains sequence ordering across wrap-around index boundaries without data corruption.",
                ),
                NarrativeBlock(
                    block_id="sec-flags",
                    type="section",
                    text="Status flags: Full and empty status flags consistently agree with count (full=(count==DEPTH), empty=(count==0)).",
                ),
                NarrativeBlock(
                    block_id="sec-pipe-ordering",
                    type="section",
                    text="Pipeline Ordering: Words transferred end-to-end maintain strict first-in, first-out ordering with zero item loss.",
                ),
                NarrativeBlock(
                    block_id="sec-pipe-stall",
                    type="section",
                    text="Pipeline Stall: Stalled egress preserves the held bridge register word during backpressure.",
                ),
                NarrativeBlock(
                    block_id="sec-pipe-bubble",
                    type="section",
                    text="Pipeline Handshake: Bridge register never requests ingress read while holding data, inserting a clean transfer bubble.",
                ),
                NarrativeBlock(
                    block_id="sec-pipe-reset",
                    type="section",
                    text="Pipeline Reset: Reset clears all pending data across both FIFO queues and the intermediate bridge holding register.",
                ),
            ]
        }
    )

    revision = SpecRevision.from_package(package)
    target = EntityRef(document_id=doc_id, entity_id="fifo_pipeline", entity_kind="design")
    return ActivitySnapshot.create(revision, target=target)


def get_renamed_two_fifo_snapshot_bytes() -> bytes:
    """Return bytes for the renamed Two-FIFO Activity Snapshot."""
    return build_renamed_two_fifo_snapshot().to_bytes()
