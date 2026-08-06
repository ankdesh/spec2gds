from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Slice(StrictModel):
    lsb: int = Field(ge=0)
    width: int = Field(gt=0)


class InstanceEndpoint(StrictModel):
    kind: Literal["instance"]
    instance_id: str
    terminal_id: str
    slice: Slice | None


class BoundaryEndpoint(StrictModel):
    kind: Literal["boundary"]
    terminal_id: str
    slice: Slice | None


NetEndpoint = InstanceEndpoint | BoundaryEndpoint


class CircuitTerminalDefinition(StrictModel):
    id: str
    label: str
    direction: Literal["input", "output", "inout"]
    width: int | str
    category: Literal["port", "interface"] = "port"


class CircuitStringParameterDefinition(StrictModel):
    id: str
    label: str
    type: Literal["string"]
    default: str


class CircuitNumberParameterDefinition(StrictModel):
    id: str
    label: str
    type: Literal["number"]
    default: float
    minimum: float | None = None
    maximum: float | None = None


class CircuitBooleanParameterDefinition(StrictModel):
    id: str
    label: str
    type: Literal["boolean"]
    default: bool


class CircuitEnumParameterDefinition(StrictModel):
    id: str
    label: str
    type: Literal["enum"]
    default: str
    values: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_default(self) -> "CircuitEnumParameterDefinition":
        if self.default not in self.values:
            raise ValueError("An enum parameter default must be one of its values.")
        return self


CircuitParameterDefinition = (
    CircuitStringParameterDefinition
    | CircuitNumberParameterDefinition
    | CircuitBooleanParameterDefinition
    | CircuitEnumParameterDefinition
)


class CircuitAppearanceProperty(StrictModel):
    """Structured-output-safe representation of one renderer property."""

    name: str
    value: str | float | bool | None


class CircuitComponentAppearance(StrictModel):
    renderer_key: str
    properties: list[CircuitAppearanceProperty]

    @field_validator("properties", mode="before")
    @classmethod
    def decode_property_map(cls, value: object) -> object:
        if isinstance(value, dict):
            return [{"name": name, "value": item} for name, item in value.items()]
        return value

    @field_serializer("properties")
    def encode_property_map(
        self, value: list[CircuitAppearanceProperty]
    ) -> dict[str, str | float | bool | None]:
        return {item.name: item.value for item in value}

    @model_validator(mode="after")
    def validate_unique_properties(self) -> "CircuitComponentAppearance":
        names = [item.name for item in self.properties]
        if len(names) != len(set(names)):
            raise ValueError("Renderer property names must be unique.")
        return self


class CircuitComponentDefinition(StrictModel):
    id: str
    label: str
    origin: Literal["local", "builtin", "provider"]
    editable: bool
    terminals: list[CircuitTerminalDefinition]
    parameters: list[CircuitParameterDefinition]
    appearance: CircuitComponentAppearance


class CircuitBoundaryTerminal(StrictModel):
    id: str
    label: str
    direction: Literal["input", "output", "inout"]
    width: int | str
    category: Literal["port", "interface"] = "port"


class CircuitParameterAssignment(StrictModel):
    """Structured-output-safe representation of one instance parameter value."""

    name: str
    value: str | float | bool


class CircuitInstance(StrictModel):
    id: str
    label: str
    component_id: str
    parameter_values: list[CircuitParameterAssignment]

    @field_validator("parameter_values", mode="before")
    @classmethod
    def decode_parameter_map(cls, value: object) -> object:
        if isinstance(value, dict):
            return [{"name": name, "value": item} for name, item in value.items()]
        return value

    @field_serializer("parameter_values")
    def encode_parameter_map(
        self, value: list[CircuitParameterAssignment]
    ) -> dict[str, str | float | bool]:
        return {item.name: item.value for item in value}

    @model_validator(mode="after")
    def validate_unique_parameter_values(self) -> "CircuitInstance":
        names = [item.name for item in self.parameter_values]
        if len(names) != len(set(names)):
            raise ValueError("Instance parameter names must be unique.")
        return self


class CircuitNet(StrictModel):
    id: str
    label: str
    endpoints: list[NetEndpoint] = Field(min_length=1)


class AddComponentOperation(StrictModel):
    operation_id: str
    type: Literal["add_component"]
    component: CircuitComponentDefinition

    @model_validator(mode="after")
    def validate_local_component(self) -> "AddComponentOperation":
        if self.component.origin != "local" or not self.component.editable:
            raise ValueError("New component definitions must be local and editable.")
        return self


class UpdateComponentOperation(StrictModel):
    operation_id: str
    type: Literal["update_component"]
    component: CircuitComponentDefinition
    cascade: bool


class RemoveComponentOperation(StrictModel):
    operation_id: str
    type: Literal["remove_component"]
    component_id: str
    cascade: bool


class AddInstanceOperation(StrictModel):
    operation_id: str
    type: Literal["add_instance"]
    instance: CircuitInstance


class UpdateInstanceOperation(StrictModel):
    operation_id: str
    type: Literal["update_instance"]
    instance: CircuitInstance


class RemoveInstanceOperation(StrictModel):
    operation_id: str
    type: Literal["remove_instance"]
    instance_id: str
    cascade: bool


class AddBoundaryTerminalOperation(StrictModel):
    operation_id: str
    type: Literal["add_boundary_terminal"]
    terminal: CircuitBoundaryTerminal


class UpdateBoundaryTerminalOperation(StrictModel):
    operation_id: str
    type: Literal["update_boundary_terminal"]
    terminal: CircuitBoundaryTerminal
    cascade: bool


class RemoveBoundaryTerminalOperation(StrictModel):
    operation_id: str
    type: Literal["remove_boundary_terminal"]
    terminal_id: str
    cascade: bool


class CreateNetOperation(StrictModel):
    operation_id: str
    type: Literal["create_net"]
    net: CircuitNet


class UpdateNetOperation(StrictModel):
    operation_id: str
    type: Literal["update_net"]
    net: CircuitNet


class DeleteNetOperation(StrictModel):
    operation_id: str
    type: Literal["delete_net"]
    net_id: str


class ConnectEndpointOperation(StrictModel):
    operation_id: str
    type: Literal["connect_endpoint"]
    net_id: str
    endpoint: NetEndpoint


class DisconnectEndpointOperation(StrictModel):
    operation_id: str
    type: Literal["disconnect_endpoint"]
    net_id: str
    endpoint: NetEndpoint


CircuitOperation = (
    AddComponentOperation
    | UpdateComponentOperation
    | RemoveComponentOperation
    | AddInstanceOperation
    | UpdateInstanceOperation
    | RemoveInstanceOperation
    | AddBoundaryTerminalOperation
    | UpdateBoundaryTerminalOperation
    | RemoveBoundaryTerminalOperation
    | CreateNetOperation
    | UpdateNetOperation
    | DeleteNetOperation
    | ConnectEndpointOperation
    | DisconnectEndpointOperation
)


class CircuitProposalDraft(StrictModel):
    """Model-authored proposal body used with OpenAI Structured Outputs."""

    supported: bool
    title: str
    summary: str
    rationale: str
    assumptions: list[str]
    unsupported_reason: str | None
    operations: list[CircuitOperation]

    @model_validator(mode="after")
    def validate_supported_shape(self) -> "CircuitProposalDraft":
        if self.supported and not self.operations:
            raise ValueError("A supported proposal must contain at least one operation.")
        if not self.supported and self.operations:
            raise ValueError("An unsupported request cannot contain operations.")
        if not self.supported and not self.unsupported_reason:
            raise ValueError("An unsupported request must explain why it is unsupported.")
        return self


class CircuitOperationBatch(StrictModel):
    request_id: str
    expected_revision: str
    operations: list[CircuitOperation] = Field(min_length=1)


class CircuitProposalArtifact(StrictModel):
    kind: Literal["circuit_change_proposal"] = "circuit_change_proposal"
    schema_version: Literal["1"] = "1"
    proposal_id: str
    document_id: str
    base_revision: str
    title: str
    summary: str
    rationale: str
    assumptions: list[str]
    batch: CircuitOperationBatch


class CircuitAgentRequest(StrictModel):
    user_request: str
    snapshot: dict[str, object]
    svg: str | None = None
    png_base64: str | None = None


class ProcessedContext(StrictModel):
    text: str
    document_id: str
    revision: str
    warnings: list[str]


class SpecEntityRef(StrictModel):
    document_id: str
    entity_id: str
    entity_kind: Literal[
        "component",
        "design",
        "bus_definition",
        "abstraction_definition",
        "narrative_block",
    ]


SpecOperationType = Literal[
    "set_entity_metadata",
    "upsert_parameter",
    "delete_parameter",
    "upsert_component_port",
    "delete_component_port",
    "upsert_bus_interface",
    "delete_bus_interface",
    "upsert_channel",
    "delete_channel",
    "upsert_instance",
    "delete_instance",
    "reorder_instances",
    "upsert_connection",
    "delete_connection",
    "reorder_connections",
    "set_internal_design",
    "clear_internal_design",
    "update_bus_definition",
    "set_abstraction_bus_type",
    "upsert_abstraction_port",
    "delete_abstraction_port",
    "upsert_narrative_block",
    "delete_narrative_block",
    "reorder_narrative_blocks",
    "set_narrative_entity_links",
]


class SpecParameterValue(StrictModel):
    name: str
    value: str
    resolve: str | None = None
    data_type: str | None = None
    choice_ref: str | None = None
    minimum: str | None = None
    maximum: str | None = None
    description: str | None = None


class SpecWireComponentPortValue(StrictModel):
    """Editor-profiled physical wire port used in an AI proposal."""

    name: str
    family: Literal["wire"]
    display_name: str | None = None
    description: str | None = None
    direction: Literal["in", "out", "inout"]
    range: str | None = None


class SpecTransactionalComponentPortValue(StrictModel):
    """Editor-profiled transactional port used in an AI proposal."""

    name: str
    family: Literal["transactional"]
    display_name: str | None = None
    description: str | None = None
    initiative: Literal["requires", "provides", "both"]
    kind: Literal[
        "tlm_port",
        "tlm_socket",
        "simple_socket",
        "multi_socket",
        "custom",
    ] | None = None
    custom_kind: str | None = None
    bus_width: str | None = None

    @model_validator(mode="after")
    def validate_custom_kind(self) -> "SpecTransactionalComponentPortValue":
        custom_name = (self.custom_kind or "").strip()
        if self.kind == "custom" and not custom_name:
            raise ValueError("A custom transactional port requires a custom kind name.")
        if self.kind != "custom" and custom_name:
            raise ValueError("Custom kind is only valid when Kind is custom.")
        return self


class SpecStructuredComponentPortValue(StrictModel):
    """Opaque packed structured port from the current editor profile."""

    name: str
    family: Literal["structured"]
    display_name: str | None = None
    description: str | None = None
    direction: Literal["in", "out", "inout"]


SpecComponentPortValue = (
    SpecWireComponentPortValue
    | SpecTransactionalComponentPortValue
    | SpecStructuredComponentPortValue
)


class SpecPortMapValue(StrictModel):
    logical: str
    physical: str
    tie_off: str | None = None
    invert: bool | None = None
    informative: bool | None = None


class SpecBusInterfaceValue(StrictModel):
    name: str
    role: Literal["initiator", "target", "system", "monitor"]
    bus_vlnv: str
    abstraction_vlnv: str
    connection_required: bool | None = None
    bits_in_lau: str | None = None
    endianness: str | None = None
    description: str | None = None
    port_maps: list[SpecPortMapValue]


class SpecChannelValue(StrictModel):
    name: str
    interfaces: list[str]
    description: str | None = None


class SpecInstanceValue(StrictModel):
    name: str
    component_vlnv: str


class SpecInterfaceEndpointValue(StrictModel):
    instance_name: str
    interface_name: str


class SpecPortEndpointValue(StrictModel):
    instance_name: str
    port_name: str


class SpecInterfaceConnectionValue(StrictModel):
    name: str
    kind: Literal["interface"]
    interface_endpoints: list[SpecInterfaceEndpointValue] = Field(min_length=2)
    hierarchy_interfaces: list[str]


class SpecAdHocConnectionValue(StrictModel):
    name: str
    kind: Literal["ad_hoc"]
    port_endpoints: list[SpecPortEndpointValue]
    external_ports: list[str]

    @model_validator(mode="after")
    def validate_endpoint_count(self) -> "SpecAdHocConnectionValue":
        if len(self.port_endpoints) + len(self.external_ports) < 2:
            raise ValueError("An ad-hoc connection requires at least two port endpoints.")
        return self


SpecConnectionValue = SpecInterfaceConnectionValue | SpecAdHocConnectionValue


SpecBusClearField = Literal[
    "direct_connection",
    "broadcast",
    "addressable",
    "extends_vlnv",
    "max_initiators",
    "max_targets",
    "system_groups",
]


class SpecBusDefinitionProperties(StrictModel):
    direct_connection: bool | None = None
    broadcast: bool | None = None
    addressable: bool | None = None
    extends_vlnv: str | None = None
    max_initiators: int | None = None
    max_targets: int | None = None
    system_groups: list[str] | None = None
    clear_fields: list[SpecBusClearField] = Field(default_factory=list)


class SpecAbstractionRoleValue(StrictModel):
    group: str | None = None
    direction: str | None = None
    initiative: str | None = None
    presence: str | None = None
    width: str | None = None
    bus_width: str | None = None


class SpecAbstractionPortValue(StrictModel):
    name: str
    style: Literal["wire", "transactional"]
    match: bool | None = None
    description: str | None = None
    qualifiers: list[str]
    on_initiator: SpecAbstractionRoleValue | None = None
    on_target: SpecAbstractionRoleValue | None = None
    on_system: list[SpecAbstractionRoleValue]


class SpecNarrativeInlineValue(StrictModel):
    type: Literal["text", "emphasis", "strong", "code", "link"]
    text: str
    href: str
    entity_ref: SpecEntityRef | None = None


class SpecNarrativeOptionValue(StrictModel):
    key: str
    value: str | int | float | bool


class SpecNarrativeBlockValue(StrictModel):
    block_id: str
    type: Literal[
        "paragraph",
        "section",
        "list",
        "table",
        "image",
        "entity_link",
        "live_view",
    ]
    text: str
    inlines: list[SpecNarrativeInlineValue]
    children: list["SpecNarrativeBlockValue"]
    ordered: bool
    rows: list[list[str]]
    asset_id: str
    alt_text: str
    caption: str
    entity_refs: list[SpecEntityRef]
    renderer_id: str
    options: list[SpecNarrativeOptionValue]


SpecNarrativeBlockValue.model_rebuild()


class SetEntityMetadataOperation(StrictModel):
    operation_id: str
    type: Literal["set_entity_metadata"]
    entity: SpecEntityRef
    display_name: str | None = None
    short_description: str | None = None
    description: str | None = None
    clear_fields: list[
        Literal["display_name", "short_description", "description"]
    ] = Field(default_factory=list)


class UpsertParameterOperation(StrictModel):
    operation_id: str
    type: Literal["upsert_parameter"]
    entity: SpecEntityRef
    parameter: SpecParameterValue


class DeleteParameterOperation(StrictModel):
    operation_id: str
    type: Literal["delete_parameter"]
    entity: SpecEntityRef
    name: str


class UpsertComponentPortOperation(StrictModel):
    operation_id: str
    type: Literal["upsert_component_port"]
    component: SpecEntityRef
    port: SpecComponentPortValue


class DeleteComponentPortOperation(StrictModel):
    operation_id: str
    type: Literal["delete_component_port"]
    component: SpecEntityRef
    name: str


class UpsertBusInterfaceOperation(StrictModel):
    operation_id: str
    type: Literal["upsert_bus_interface"]
    component: SpecEntityRef
    interface: SpecBusInterfaceValue


class DeleteBusInterfaceOperation(StrictModel):
    operation_id: str
    type: Literal["delete_bus_interface"]
    component: SpecEntityRef
    name: str


class UpsertChannelOperation(StrictModel):
    operation_id: str
    type: Literal["upsert_channel"]
    component: SpecEntityRef
    channel: SpecChannelValue


class DeleteChannelOperation(StrictModel):
    operation_id: str
    type: Literal["delete_channel"]
    component: SpecEntityRef
    name: str


class UpsertInstanceOperation(StrictModel):
    operation_id: str
    type: Literal["upsert_instance"]
    design: SpecEntityRef
    instance: SpecInstanceValue


class DeleteInstanceOperation(StrictModel):
    operation_id: str
    type: Literal["delete_instance"]
    design: SpecEntityRef
    instance_name: str


class ReorderInstancesOperation(StrictModel):
    operation_id: str
    type: Literal["reorder_instances"]
    design: SpecEntityRef
    instance_names: list[str]


class UpsertConnectionOperation(StrictModel):
    operation_id: str
    type: Literal["upsert_connection"]
    design: SpecEntityRef
    connection: SpecConnectionValue


class DeleteConnectionOperation(StrictModel):
    operation_id: str
    type: Literal["delete_connection"]
    design: SpecEntityRef
    connection_name: str


class ReorderConnectionsOperation(StrictModel):
    operation_id: str
    type: Literal["reorder_connections"]
    design: SpecEntityRef
    kind: Literal["interface", "ad_hoc"]
    connection_names: list[str]


class SetInternalDesignOperation(StrictModel):
    operation_id: str
    type: Literal["set_internal_design"]
    component: SpecEntityRef
    internal_design: SpecEntityRef


class ClearInternalDesignOperation(StrictModel):
    operation_id: str
    type: Literal["clear_internal_design"]
    component: SpecEntityRef


class UpdateBusDefinitionOperation(StrictModel):
    operation_id: str
    type: Literal["update_bus_definition"]
    bus_definition: SpecEntityRef
    properties: SpecBusDefinitionProperties


class SetAbstractionBusTypeOperation(StrictModel):
    operation_id: str
    type: Literal["set_abstraction_bus_type"]
    abstraction_definition: SpecEntityRef
    bus_vlnv: str


class UpsertAbstractionPortOperation(StrictModel):
    operation_id: str
    type: Literal["upsert_abstraction_port"]
    abstraction_definition: SpecEntityRef
    port: SpecAbstractionPortValue


class DeleteAbstractionPortOperation(StrictModel):
    operation_id: str
    type: Literal["delete_abstraction_port"]
    abstraction_definition: SpecEntityRef
    name: str


class UpsertNarrativeBlockOperation(StrictModel):
    operation_id: str
    type: Literal["upsert_narrative_block"]
    block: SpecNarrativeBlockValue
    parent_block_id: str | None = None
    index: int | None = None


class DeleteNarrativeBlockOperation(StrictModel):
    operation_id: str
    type: Literal["delete_narrative_block"]
    block_id: str


class ReorderNarrativeBlocksOperation(StrictModel):
    operation_id: str
    type: Literal["reorder_narrative_blocks"]
    block_ids: list[str]
    parent_block_id: str | None = None


class SetNarrativeEntityLinksOperation(StrictModel):
    operation_id: str
    type: Literal["set_narrative_entity_links"]
    block_id: str
    entity_refs: list[SpecEntityRef]


SpecProposalOperation = (
    SetEntityMetadataOperation
    | UpsertParameterOperation
    | DeleteParameterOperation
    | UpsertComponentPortOperation
    | DeleteComponentPortOperation
    | UpsertBusInterfaceOperation
    | DeleteBusInterfaceOperation
    | UpsertChannelOperation
    | DeleteChannelOperation
    | UpsertInstanceOperation
    | DeleteInstanceOperation
    | ReorderInstancesOperation
    | UpsertConnectionOperation
    | DeleteConnectionOperation
    | ReorderConnectionsOperation
    | SetInternalDesignOperation
    | ClearInternalDesignOperation
    | UpdateBusDefinitionOperation
    | SetAbstractionBusTypeOperation
    | UpsertAbstractionPortOperation
    | DeleteAbstractionPortOperation
    | UpsertNarrativeBlockOperation
    | DeleteNarrativeBlockOperation
    | ReorderNarrativeBlocksOperation
    | SetNarrativeEntityLinksOperation
)


class SpecProposalDraft(StrictModel):
    supported: bool
    title: str
    summary: str
    rationale: str
    assumptions: list[str]
    unsupported_reason: str | None
    operations: list[SpecProposalOperation]

    @model_validator(mode="after")
    def validate_supported_shape(self) -> "SpecProposalDraft":
        if self.supported and not self.operations:
            raise ValueError("A supported proposal requires at least one operation.")
        if not self.supported and self.operations:
            raise ValueError("An unsupported request cannot contain operations.")
        if not self.supported and not self.unsupported_reason:
            raise ValueError("An unsupported request must explain why it is unsupported.")
        return self


class SpecProposalArtifact(StrictModel):
    kind: Literal["spec_change_proposal"] = "spec_change_proposal"
    schema_version: Literal["1.0"] = "1.0"
    proposal_id: str
    document_id: str
    target: SpecEntityRef
    base_source_revision_hash: str
    title: str
    summary: str
    rationale: str
    assumptions: list[str]
    operations: list[dict[str, Any]]


class SpecAgentRequest(StrictModel):
    user_request: str
    context: dict[str, Any]
    proposal_requested: bool = False
    conversation_summary: str | None = None
    recent_messages: list[dict[str, Any]] = Field(default_factory=list)
