"""Synthetic Synchronous FIFO Activity Snapshot generator."""

from __future__ import annotations

from spec2gds.spec.activities import ActivitySnapshot
from spec2gds.spec.spec_format.archive import SpecPackage
from spec2gds.spec.spec_format.ir import SpecRevision
from spec2gds.spec.spec_format.models import EntityRef, NarrativeBlock

_NS = "http://www.accellera.org/XMLSchema/IPXACT/1685-2022"


def _fifo_component_xml() -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ipxact:component xmlns:ipxact="{_NS}" xml:id="sync_fifo">
  <ipxact:vendor>spec2gds.example</ipxact:vendor>
  <ipxact:library>fifo</ipxact:library>
  <ipxact:name>sync_fifo</ipxact:name>
  <ipxact:version>1.0</ipxact:version>
  <ipxact:model>
    <ipxact:ports>
      <ipxact:port><ipxact:name>clk</ipxact:name><ipxact:wire><ipxact:direction>in</ipxact:direction></ipxact:wire></ipxact:port>
      <ipxact:port><ipxact:name>rst</ipxact:name><ipxact:wire><ipxact:direction>in</ipxact:direction></ipxact:wire></ipxact:port>
      <ipxact:port><ipxact:name>wr_en</ipxact:name><ipxact:wire><ipxact:direction>in</ipxact:direction></ipxact:wire></ipxact:port>
      <ipxact:port><ipxact:name>rd_en</ipxact:name><ipxact:wire><ipxact:direction>in</ipxact:direction></ipxact:wire></ipxact:port>
      <ipxact:port><ipxact:name>din</ipxact:name><ipxact:wire><ipxact:direction>in</ipxact:direction><ipxact:vectors><ipxact:vector><ipxact:left>7</ipxact:left><ipxact:right>0</ipxact:right></ipxact:vector></ipxact:vectors></ipxact:wire></ipxact:port>
      <ipxact:port><ipxact:name>dout</ipxact:name><ipxact:wire><ipxact:direction>out</ipxact:direction><ipxact:vectors><ipxact:vector><ipxact:left>7</ipxact:left><ipxact:right>0</ipxact:right></ipxact:vector></ipxact:vectors></ipxact:wire></ipxact:port>
      <ipxact:port><ipxact:name>full</ipxact:name><ipxact:wire><ipxact:direction>out</ipxact:direction></ipxact:wire></ipxact:port>
      <ipxact:port><ipxact:name>empty</ipxact:name><ipxact:wire><ipxact:direction>out</ipxact:direction></ipxact:wire></ipxact:port>
      <ipxact:port><ipxact:name>count</ipxact:name><ipxact:wire><ipxact:direction>out</ipxact:direction><ipxact:vectors><ipxact:vector><ipxact:left>2</ipxact:left><ipxact:right>0</ipxact:right></ipxact:vector></ipxact:vectors></ipxact:wire></ipxact:port>
    </ipxact:ports>
  </ipxact:model>
</ipxact:component>
""".encode("utf-8")


def build_fifo_snapshot() -> ActivitySnapshot:
    """Build the synthetic Synchronous FIFO Activity Snapshot according to Section 7."""
    doc_id = "fifo_spec"
    package = SpecPackage.create(doc_id)

    comp_entry = package.add_document("component", _fifo_component_xml())

    # Narrative blocks for the 8 requirements defined in Section 7
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
            ]
        }
    )

    revision = SpecRevision.from_package(package)
    target = EntityRef(document_id=doc_id, entity_id=comp_entry.entity_id, entity_kind="component")
    return ActivitySnapshot.create(revision, target=target)


def get_fifo_snapshot_bytes() -> bytes:
    """Return deterministic bytes for the FIFO Activity Snapshot."""
    return build_fifo_snapshot().to_bytes()


def build_modified_fifo_snapshot(modified_reset_text: str | None = None) -> ActivitySnapshot:
    """Build a modified Synchronous FIFO Activity Snapshot with updated reset narrative."""
    doc_id = "fifo_spec"
    package = SpecPackage.create(doc_id)

    comp_entry = package.add_document("component", _fifo_component_xml())

    reset_text = (
        modified_reset_text
        if modified_reset_text is not None
        else "Reset (Updated): Synchronous reset clears the queue immediately, setting count=0 and asserting empty=1."
    )

    package.narrative = package.narrative.model_copy(
        update={
            "blocks": [
                NarrativeBlock(
                    block_id="sec-reset",
                    type="section",
                    text=reset_text,
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
            ]
        }
    )

    revision = SpecRevision.from_package(package)
    target = EntityRef(document_id=doc_id, entity_id=comp_entry.entity_id, entity_kind="component")
    return ActivitySnapshot.create(revision, target=target)


def get_modified_fifo_snapshot_bytes(modified_reset_text: str | None = None) -> bytes:
    """Return bytes for the modified FIFO Activity Snapshot."""
    return build_modified_fifo_snapshot(modified_reset_text).to_bytes()
