"""Phase 2 Component definitions aggregator (32 components).

Aggregates:
- Storage components (12): fifo_sync, fifo_fallthrough, fifo_async, fifo_packet,
  lifo_stack, ring_buffer, ram_1rw, ram_1r1w, ram_2rw, rom, register_file_2r1w, cam_binary.
- Stream components (12): stream_register, stream_skid_buffer, stream_spill_buffer,
  stream_half_buffer, stream_mux, stream_demux, stream_fork, stream_join,
  stream_upsizer, stream_downsizer, stream_credit_adapter, stream_rate_limiter.
- CDC & Reset components (8): cdc_level_sync, cdc_pulse_toggle, cdc_pulse_handshake,
  cdc_bus_handshake, reset_sync, reset_stretcher, reset_sequencer, input_deglitch.
"""

from __future__ import annotations

from spec_catalog_service.catalog.components.models import ComponentDef
from spec_catalog_service.catalog.components.phase2_cdc import PHASE2_CDC_COMPONENTS
from spec_catalog_service.catalog.components.phase2_storage import PHASE2_STORAGE_COMPONENTS
from spec_catalog_service.catalog.components.phase2_streams import PHASE2_STREAMS_COMPONENTS

PHASE2_COMPONENTS: list[ComponentDef] = [
    *PHASE2_STORAGE_COMPONENTS,
    *PHASE2_STREAMS_COMPONENTS,
    *PHASE2_CDC_COMPONENTS,
]

PHASE2_COMPONENTS_BY_ID: dict[str, ComponentDef] = {c.id: c for c in PHASE2_COMPONENTS}
