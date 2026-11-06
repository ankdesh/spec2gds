"""Versioned source-semantic Component channel annotations (spec2gds.channels v1).

This module defines typed channel descriptors, payload field mappings, transfer
contracts, and verification rules for components across all rollout phases.
"""

from __future__ import annotations

import json
import typing

import pydantic
from lxml import etree

from spec2gds.spec.spec_format.models import AnnotationSchemaEntry, EntityRef, StrictModel

CHANNEL_NAMESPACE = "spec2gds.channels"
CHANNEL_ROOT = "annotations/channels"
CHANNEL_MAX_BYTES = 2 * 1024 * 1024


class ChannelFieldMappingV1(StrictModel):
    """Mapping from a logical field in a channel to a physical component port."""

    name: str
    port: str
    bit_slice: str | None = None
    signed: bool = False
    field_role: typing.Literal["operand", "result", "control", "flag", "tag", "marker"] = "operand"


class ChannelTransferContractV1(StrictModel):
    """Detailed transfer, timing, and buffering contract for a channel."""

    transfer_rule: typing.Literal["ready_valid_edge", "credit", "pulse", "static"] = "ready_valid_edge"
    min_latency: int = 0
    acceptance_interval: int = 1
    capacity: int = 0
    ordered: bool = True
    max_outstanding: int = 1


class ComponentChannelV1(StrictModel):
    """One logical channel (e.g. request, response, stream sink, stream source)."""

    id: str
    profile: typing.Literal[
        "ready_valid",
        "request",
        "response",
        "stream_sink",
        "stream_source",
        "combinational",
        "pulse",
    ]
    direction: typing.Literal["consumer", "producer"]
    valid_port: str | None = None
    ready_port: str | None = None
    clock_port: str = "clk_i"
    reset_port: str = "rst_ni"
    reset_polarity: typing.Literal["active_low", "active_high"] = "active_low"
    fields: tuple[ChannelFieldMappingV1, ...] = ()
    contract: ChannelTransferContractV1 = pydantic.Field(default_factory=ChannelTransferContractV1)
    combinational_dependencies: tuple[str, ...] = ()

    @pydantic.model_validator(mode="after")
    def validate_channel_semantics(self) -> "ComponentChannelV1":
        field_names = [f.name for f in self.fields]
        if len(field_names) != len(set(field_names)):
            raise ValueError(f"Channel {self.id} has duplicate field names: {field_names}")
        if self.profile in ("ready_valid", "request", "response", "stream_sink", "stream_source"):
            if not self.valid_port:
                raise ValueError(f"Elastic channel {self.id} must declare a valid_port")
            if not self.ready_port:
                raise ValueError(f"Elastic channel {self.id} must declare a ready_port")
        return self


class ComponentChannelsV1(StrictModel):
    """Collection of channels declared by a Component."""

    schema_version: typing.Literal[1] = 1
    component: EntityRef
    channels: tuple[ComponentChannelV1, ...] = ()

    @pydantic.model_validator(mode="after")
    def validate_payload(self) -> "ComponentChannelsV1":
        if self.component.entity_kind != "component":
            raise ValueError("Component channels must be attached to a Component.")
        channel_ids = [c.id for c in self.channels]
        if len(channel_ids) != len(set(channel_ids)):
            raise ValueError(f"Component channels must have unique IDs, got: {channel_ids}")
        # Check combinational dependencies refer to existing channels
        for c in self.channels:
            for dep in c.combinational_dependencies:
                if dep not in channel_ids:
                    raise ValueError(f"Channel {c.id} references unknown dependency channel '{dep}'")
        encoded = json.dumps(self.model_dump(mode="json"), separators=(",", ":")).encode("utf-8")
        if len(encoded) > CHANNEL_MAX_BYTES:
            raise ValueError("Component channels annotation exceeds 2 MiB limit.")
        return self


def channel_path(component_entity_id: str) -> str:
    """Canonical annotation file path for a component's channel descriptor."""
    return f"{CHANNEL_ROOT}/{component_entity_id}.json"


def load_component_channels(revision: typing.Any, component: EntityRef) -> ComponentChannelsV1 | None:
    """Load channel annotation for a component from a SpecRevision if present."""
    path = channel_path(component.entity_id)
    annotation = next((item for item in revision.annotations if item.path == path), None)
    if annotation is None:
        return None
    value = ComponentChannelsV1.model_validate_json(annotation.data)
    if value.component != component:
        raise ValueError(f"Component channel {path} does not match its owning component.")
    return value


def upsert_component_channels(package: typing.Any, channels: ComponentChannelsV1) -> None:
    """Save or update channel annotation and ensure schema registration in manifest."""
    path = channel_path(channels.component.entity_id)
    data = (json.dumps(channels.model_dump(mode="json", exclude_none=True), indent=2, sort_keys=True) + "\n").encode("utf-8")
    if len(data) > CHANNEL_MAX_BYTES:
        raise ValueError("Component channels annotation exceeds 2 MiB limit.")
    package.files[path] = data
    schemas = [item for item in package.manifest.annotation_schemas if item.namespace != CHANNEL_NAMESPACE]
    schemas.append(AnnotationSchemaEntry(namespace=CHANNEL_NAMESPACE, version=1, path_prefix=CHANNEL_ROOT))
    package.manifest = package.manifest.model_copy(update={"annotation_schemas": schemas})


def delete_component_channels(package: typing.Any, component: EntityRef) -> None:
    """Delete a component's channel annotation and clean schema if none remain."""
    path = channel_path(component.entity_id)
    package.files.pop(path, None)
    remaining = [p for p in package.files if p.startswith(f"{CHANNEL_ROOT}/") and p.endswith(".json")]
    if not remaining:
        schemas = [item for item in package.manifest.annotation_schemas if item.namespace != CHANNEL_NAMESPACE]
        package.manifest = package.manifest.model_copy(update={"annotation_schemas": schemas})


def validate_channel_annotations(manifest: typing.Any, files: typing.Mapping[str, bytes]) -> None:
    """Validate registered channel annotations against manifest components and port references."""
    registered = any(item.namespace == CHANNEL_NAMESPACE for item in manifest.annotation_schemas)
    channel_files = [path for path in files if path.startswith(f"{CHANNEL_ROOT}/") and path.endswith(".json")]
    if channel_files and not registered:
        raise ValueError("Channel annotations require manifest registration.")
    if registered and not channel_files:
        raise ValueError("Channel annotation registered in manifest but no channel files found.")

    component_docs = {e.entity_id: e for e in manifest.documents if e.kind == "component"}

    for path in channel_files:
        try:
            payload = json.loads(files[path].decode("utf-8"))
            channels_obj = ComponentChannelsV1.model_validate(payload)
        except Exception as exc:
            raise ValueError(f"Malformed channel annotation {path}: {exc}") from exc

        comp_id = channels_obj.component.entity_id
        if comp_id not in component_docs:
            raise ValueError(f"Channel annotation {path} references missing component {comp_id}")

        # Check port references against the component's IP-XACT port list
        if comp_id in component_docs and component_docs[comp_id].path in files:
            comp_root = etree.fromstring(files[component_docs[comp_id].path])
            known_ports = {
                str(node.text or "").strip()
                for node in comp_root.xpath(
                    "./*[local-name()='model']/*[local-name()='ports']/*[local-name()='port']/*[local-name()='name']"
                )
            }
            for chan in channels_obj.channels:
                if chan.valid_port and chan.valid_port not in known_ports:
                    raise ValueError(f"Channel {chan.id} references unknown valid_port '{chan.valid_port}'")
                if chan.ready_port and chan.ready_port not in known_ports:
                    raise ValueError(f"Channel {chan.id} references unknown ready_port '{chan.ready_port}'")
                for f in chan.fields:
                    if f.port not in known_ports:
                        raise ValueError(f"Channel {chan.id} field '{f.name}' references unknown port '{f.port}'")
                if chan.profile not in ("combinational",):
                    if chan.clock_port and chan.clock_port not in known_ports:
                        raise ValueError(f"Channel {chan.id} references unknown clock_port '{chan.clock_port}'")
                    if chan.reset_port and chan.reset_port not in known_ports:
                        raise ValueError(f"Channel {chan.id} references unknown reset_port '{chan.reset_port}'")


class ChannelConnectionDiagnostic(StrictModel):
    severity: typing.Literal["error", "warning", "info"]
    code: str
    message: str


class ChannelConnectionPreview(StrictModel):
    compatible: bool
    requires_adapter: bool
    recommended_adapter: str | None = None
    port_mappings: tuple[tuple[str, str], ...] = ()
    diagnostics: tuple[ChannelConnectionDiagnostic, ...] = ()


def detect_combinational_cycle(edges: typing.Iterable[tuple[str, str]]) -> list[list[str]]:
    """Detect cycles in a directed graph of combinational dependencies.

    Each edge (u, v) indicates that v combinationally depends on u.
    Returns a list of detected cycles (paths of node names forming cycles).
    """
    adj: dict[str, list[str]] = {}
    nodes: set[str] = set()
    for u, v in edges:
        nodes.add(u)
        nodes.add(v)
        adj.setdefault(u, []).append(v)

    visited: dict[str, int] = {}  # 0: unvisited, 1: visiting, 2: visited
    cycles: list[list[str]] = []

    def dfs(curr: str, path: list[str]) -> None:
        visited[curr] = 1
        path.append(curr)
        for nxt in adj.get(curr, []):
            if visited.get(nxt, 0) == 1:
                cycle_start = path.index(nxt)
                cycles.append(path[cycle_start:] + [nxt])
            elif visited.get(nxt, 0) == 0:
                dfs(nxt, path)
        path.pop()
        visited[curr] = 2

    for node in sorted(nodes):
        if visited.get(node, 0) == 0:
            dfs(node, [])

    return cycles


def validate_channel_connection(
    producer: ComponentChannelV1,
    consumer: ComponentChannelV1,
    producer_domain: str | None = None,
    consumer_domain: str | None = None,
) -> list[ChannelConnectionDiagnostic]:
    """Validate connection between a producer channel and consumer channel.

    Checks directionality, clock/reset agreement, domain agreement, and field compatibility.
    """
    diags: list[ChannelConnectionDiagnostic] = []

    if producer.direction != "producer":
        diags.append(
            ChannelConnectionDiagnostic(
                severity="error",
                code="DIRECTION_MISMATCH",
                message=f"Producer endpoint must have direction 'producer', got '{producer.direction}'.",
            )
        )
    if consumer.direction != "consumer":
        diags.append(
            ChannelConnectionDiagnostic(
                severity="error",
                code="DIRECTION_MISMATCH",
                message=f"Consumer endpoint must have direction 'consumer', got '{consumer.direction}'.",
            )
        )

    # Domain mismatch check
    if producer_domain and consumer_domain and producer_domain != consumer_domain:
        diags.append(
            ChannelConnectionDiagnostic(
                severity="error",
                code="CLOCK_DOMAIN_MISMATCH",
                message=(
                    f"Clock domain mismatch: producer is in domain '{producer_domain}', "
                    f"consumer is in domain '{consumer_domain}'. An explicit CDC adapter "
                    f"(e.g., cdc_fifo or cdc_bus_handshake) is required."
                ),
            )
        )

    # Clock port and reset polarity checks (if sequential)
    if producer.profile != "combinational" and consumer.profile != "combinational":
        if producer.clock_port != consumer.clock_port:
            diags.append(
                ChannelConnectionDiagnostic(
                    severity="warning",
                    code="CLOCK_PORT_MISMATCH",
                    message=(
                        f"Clock port mismatch: producer references '{producer.clock_port}', "
                        f"consumer references '{consumer.clock_port}'. Confirm synchronous routing."
                    ),
                )
            )
        if producer.reset_polarity != consumer.reset_polarity:
            diags.append(
                ChannelConnectionDiagnostic(
                    severity="error",
                    code="RESET_POLARITY_MISMATCH",
                    message=(
                        f"Reset polarity mismatch: producer uses '{producer.reset_polarity}', "
                        f"consumer uses '{consumer.reset_polarity}'. Reset polarity conversion required."
                    ),
                )
            )

    # Payload compatibility check
    prod_fields = [f.name for f in producer.fields]
    cons_fields = [f.name for f in consumer.fields]

    if prod_fields != cons_fields:
        if prod_fields == ["data"] and cons_fields == ["a", "b"]:
            diags.append(
                ChannelConnectionDiagnostic(
                    severity="info",
                    code="ADAPTER_REQUIRED",
                    message="Packed stream to multiplier operand split requires 'multiplier_stream_adapter'.",
                )
            )
        elif prod_fields == ["product"] and cons_fields == ["data"]:
            diags.append(
                ChannelConnectionDiagnostic(
                    severity="info",
                    code="ADAPTER_REQUIRED",
                    message="Multiplier response to stream packing requires 'multiplier_stream_adapter'.",
                )
            )
        elif prod_fields == ["data"] and cons_fields == ["dividend", "divisor"]:
            diags.append(
                ChannelConnectionDiagnostic(
                    severity="info",
                    code="ADAPTER_REQUIRED",
                    message="Packed stream to divider operand split requires 'divider_stream_adapter'.",
                )
            )
        elif prod_fields == ["quotient", "remainder", "div_zero", "overflow"] and cons_fields == ["data"]:
            diags.append(
                ChannelConnectionDiagnostic(
                    severity="info",
                    code="ADAPTER_REQUIRED",
                    message="Divider response and status flags to stream packing requires 'divider_stream_adapter'.",
                )
            )
        else:
            diags.append(
                ChannelConnectionDiagnostic(
                    severity="error",
                    code="FIELD_MISMATCH",
                    message=f"Payload fields mismatch: producer has {prod_fields}, consumer expects {cons_fields}.",
                )
            )

    return diags


def create_channel_connection_preview(
    producer: ComponentChannelV1,
    consumer: ComponentChannelV1,
    producer_domain: str | None = None,
    consumer_domain: str | None = None,
) -> ChannelConnectionPreview:
    """Generate a connection preview with port mappings, adapter hints, and diagnostics."""
    diags = validate_channel_connection(
        producer, consumer, producer_domain=producer_domain, consumer_domain=consumer_domain
    )
    has_errors = any(d.severity == "error" for d in diags)
    adapter_diag = next((d for d in diags if d.code == "ADAPTER_REQUIRED"), None)
    requires_adapter = adapter_diag is not None

    recommended_adapter = None
    if requires_adapter:
        prod_fields = [f.name for f in producer.fields]
        cons_fields = [f.name for f in consumer.fields]
        if (prod_fields == ["data"] and cons_fields == ["a", "b"]) or (
            prod_fields == ["product"] and cons_fields == ["data"]
        ):
            recommended_adapter = "multiplier_stream_adapter"
        elif (prod_fields == ["data"] and cons_fields == ["dividend", "divisor"]) or (
            prod_fields == ["quotient", "remainder", "div_zero", "overflow"] and cons_fields == ["data"]
        ):
            recommended_adapter = "divider_stream_adapter"

    port_mappings: list[tuple[str, str]] = []
    if not has_errors and not requires_adapter:
        # Map valid/ready handshakes
        if producer.valid_port and consumer.valid_port:
            port_mappings.append((producer.valid_port, consumer.valid_port))
        if consumer.ready_port and producer.ready_port:
            port_mappings.append((consumer.ready_port, producer.ready_port))
        # Map fields 1:1
        for p_f, c_f in zip(producer.fields, consumer.fields):
            port_mappings.append((p_f.port, c_f.port))

    compatible = (not has_errors) and (not requires_adapter)
    return ChannelConnectionPreview(
        compatible=compatible,
        requires_adapter=requires_adapter,
        recommended_adapter=recommended_adapter,
        port_mappings=tuple(port_mappings),
        diagnostics=tuple(diags),
    )
