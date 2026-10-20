/* Generated from circuit-designer.v1.schema.json. Do not edit. */

export type Slug = string;
export type NonEmptyString = string;
export type ParameterDefinition =
  StringParameterDefinition | NumberParameterDefinition | BooleanParameterDefinition | EnumParameterDefinition;
export type JsonScalar = string | number | boolean | null;
export type ParameterValue = string | number | boolean;
export type NetEndpoint = InstanceNetEndpoint | BoundaryNetEndpoint;
export type CircuitOperation =
  | AddComponentOperation
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
  | SetInstanceGeometryOperation
  | SetTerminalPlacementOperation
  | SetNetRouteOperation
  | SetLabelGeometryOperation
  | SetLayoutSettingsOperation
  | AddCycleEdgeOperation
  | UpdateCycleEdgeOperation
  | RemoveCycleEdgeOperation
  | SetClockDomainOperation
  | RemoveClockDomainOperation
  | SetSubjectClockDomainOperation
  | SetDocumentLabelOperation;
export type AddComponentOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "add_component";
  component: ComponentDefinition;
};
export type UpdateComponentOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "update_component";
  component: ComponentDefinition;
  cascade?: boolean;
};
export type RemoveComponentOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "remove_component";
  component_id: Slug;
  cascade?: boolean;
};
export type AddInstanceOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "add_instance";
  instance: CircuitInstance;
};
export type UpdateInstanceOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "update_instance";
  instance: CircuitInstance;
};
export type RemoveInstanceOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "remove_instance";
  instance_id: Slug;
  cascade?: boolean;
};
export type AddBoundaryTerminalOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "add_boundary_terminal";
  terminal: BoundaryTerminal;
};
export type UpdateBoundaryTerminalOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "update_boundary_terminal";
  terminal: BoundaryTerminal;
  cascade?: boolean;
};
export type RemoveBoundaryTerminalOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "remove_boundary_terminal";
  terminal_id: Slug;
  cascade?: boolean;
};
export type CreateNetOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "create_net";
  net: CircuitNet;
};
export type UpdateNetOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "update_net";
  net: CircuitNet;
};
export type DeleteNetOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "delete_net";
  net_id: Slug;
};
export type ConnectEndpointOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "connect_endpoint";
  net_id: Slug;
  endpoint: NetEndpoint;
};
export type DisconnectEndpointOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "disconnect_endpoint";
  net_id: Slug;
  endpoint: NetEndpoint;
};
export type SetInstanceGeometryOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "set_instance_geometry";
  instance_id: Slug;
  geometry: NodeGeometry;
};
export type SetTerminalPlacementOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "set_terminal_placement";
  terminal_key: NonEmptyString;
  placement?: TerminalPlacement | null;
};
export type SetNetRouteOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "set_net_route";
  net_id: Slug;
  route?: NetRoute | null;
};
export type SetLabelGeometryOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "set_label_geometry";
  element_key: NonEmptyString;
  geometry?: LabelGeometry | null;
};
export type SetLayoutSettingsOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "set_layout_settings";
  grid_size?: number;
  direction?: "RIGHT" | "DOWN";
};
export type AddCycleEdgeOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "add_cycle_edge";
  edge: CycleEdgeMarkerV1;
};
export type UpdateCycleEdgeOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "update_cycle_edge";
  edge: CycleEdgeMarkerV1;
};
export type RemoveCycleEdgeOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "remove_cycle_edge";
  edge_id: Slug;
};
export type SetClockDomainOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "set_clock_domain";
  domain: ClockDomainV1;
};
export type RemoveClockDomainOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "remove_clock_domain";
  domain_id: Slug;
};
export type SetSubjectClockDomainOperation = OperationBase & {
  operation_id: NonEmptyString;
  type: "set_subject_clock_domain";
  subject_key: string;
  domain_id?: Slug | null;
};
export type CircuitProposalCreateRequest = {
  proposal_id: NonEmptyString;
  document_id: Slug;
  base_revision: NonEmptyString;
  title: NonEmptyString;
  summary: NonEmptyString;
  rationale?: string;
  assumptions?: NonEmptyString[];
  construction?: CircuitConstruction;
  batch?: CircuitOperationBatch;
} & CircuitProposalCreateRequest1;
export type CircuitProposalCreateRequest1 = {
  [k: string]: any;
};
export type CircuitProposal = {
  proposal_id: NonEmptyString;
  document_id: Slug;
  base_revision: NonEmptyString;
  title: NonEmptyString;
  summary: NonEmptyString;
  rationale?: string;
  assumptions?: NonEmptyString[];
  status: "pending" | "stale";
  construction?: CircuitConstruction;
  batch?: CircuitOperationBatch;
  diagnostics: Diagnostic[];
  diff: CircuitDiff;
  created_at: NonEmptyString;
} & CircuitProposal1;
export type CircuitProposal1 = {
  [k: string]: any;
};

/**
 * Independent, renderer-neutral Circuit Designer v1 contracts.
 */
export interface CircuitDesignerProtocol {
  document?: CircuitDocument;
  snapshot?: CircuitSnapshot;
  construction?: CircuitConstruction;
  batch?: CircuitOperationBatch;
  result?: CircuitChangeResult;
  proposal_create_request?: CircuitProposalCreateRequest;
  proposal?: CircuitProposal;
  lease?: EditLease;
  provider?: ResolvedComponentDesign;
  summary?: DocumentSummary;
  provider_commit_request?: ProviderCommitRequest;
  provider_commit_result?: ProviderCommitResult;
  event?: ServiceEvent;
  error?: ServiceError;
}
export interface CircuitDocument {
  protocol_version: "circuit-designer.v1";
  document_id: Slug;
  label: NonEmptyString;
  components: ComponentDefinition[];
  design: CircuitDesign;
  layout: CircuitLayout;
  timing?: CircuitTimingV1;
}
export interface ComponentDefinition {
  id: Slug;
  label: NonEmptyString;
  origin: "local" | "builtin" | "provider";
  editable: boolean;
  terminals: TerminalDefinition[];
  parameters: ParameterDefinition[];
  appearance: ComponentAppearance;
}
export interface TerminalDefinition {
  id: Slug;
  label: NonEmptyString;
  direction: "input" | "output" | "inout";
  width: number | string;
  category?: "port" | "interface";
}
export interface StringParameterDefinition {
  id: Slug;
  label: NonEmptyString;
  type: "string";
  default: string;
}
export interface NumberParameterDefinition {
  id: Slug;
  label: NonEmptyString;
  type: "number";
  default: number;
  minimum?: number;
  maximum?: number;
}
export interface BooleanParameterDefinition {
  id: Slug;
  label: NonEmptyString;
  type: "boolean";
  default: boolean;
}
export interface EnumParameterDefinition {
  id: Slug;
  label: NonEmptyString;
  type: "enum";
  default: string;
  /**
   * @minItems 1
   */
  values: [string, ...string[]];
}
export interface ComponentAppearance {
  renderer_key: NonEmptyString;
  properties: {
    [k: string]: JsonScalar;
  };
}
export interface CircuitDesign {
  id: Slug;
  label: NonEmptyString;
  boundary_terminals: BoundaryTerminal[];
  instances: CircuitInstance[];
  nets: CircuitNet[];
}
export interface BoundaryTerminal {
  id: Slug;
  label: NonEmptyString;
  direction: "input" | "output" | "inout";
  width: number | string;
  category?: "port" | "interface";
}
export interface CircuitInstance {
  id: Slug;
  label: NonEmptyString;
  component_id: Slug;
  parameter_values: {
    [k: string]: ParameterValue;
  };
}
export interface CircuitNet {
  id: Slug;
  label: string;
  /**
   * @minItems 1
   */
  endpoints: [NetEndpoint, ...NetEndpoint[]];
}
export interface InstanceNetEndpoint {
  kind: "instance";
  instance_id: Slug;
  terminal_id: Slug;
  slice?: EndpointSlice;
}
export interface EndpointSlice {
  lsb: number;
  width: number;
}
export interface BoundaryNetEndpoint {
  kind: "boundary";
  terminal_id: Slug;
  slice?: EndpointSlice;
}
export interface CircuitLayout {
  grid_size: number;
  direction: "RIGHT" | "DOWN";
  instance_geometry: {
    [k: string]: NodeGeometry;
  };
  terminal_placements: {
    [k: string]: TerminalPlacement;
  };
  net_routes: {
    [k: string]: NetRoute;
  };
  label_geometry: {
    [k: string]: LabelGeometry;
  };
}
export interface NodeGeometry {
  x: number;
  y: number;
  width: number;
  height: number;
  pinned?: boolean;
}
export interface TerminalPlacement {
  side: "NORTH" | "EAST" | "SOUTH" | "WEST";
  order: number;
  locked?: boolean;
}
export interface NetRoute {
  vertices: RouteVertex[];
  segments: RouteSegment[];
}
export interface RouteVertex {
  id: NonEmptyString;
  kind: "endpoint" | "bend" | "junction";
  point: Point;
  terminal_id?: string | null;
  locked?: boolean;
}
export interface Point {
  x: number;
  y: number;
}
export interface RouteSegment {
  id?: string | null;
  from_vertex: NonEmptyString;
  to_vertex: NonEmptyString;
  locked?: boolean;
}
export interface LabelGeometry {
  x: number;
  y: number;
  anchor?: "start" | "middle" | "end";
}
export interface CircuitTimingV1 {
  schema_version: 1;
  /**
   * @minItems 1
   */
  clock_domains: [ClockDomainV1, ...ClockDomainV1[]];
  cycle_edges: CycleEdgeMarkerV1[];
  subject_domain_overrides: {
    [k: string]: Slug;
  };
  leading_stage_label?: NonEmptyString;
}
export interface ClockDomainV1 {
  id: Slug;
  label: NonEmptyString;
  color?: string;
  signal?: ClockSignalReference;
}
export interface ClockSignalReference {
  kind: "boundary" | "net";
  id: Slug;
}
export interface CycleEdgeMarkerV1 {
  id: Slug;
  x: number;
  label?: NonEmptyString;
  next_stage_label?: NonEmptyString;
  locked: boolean;
}
export interface CircuitSnapshot {
  revision: NonEmptyString;
  document: CircuitDocument;
}
export interface CircuitConstruction {
  mode: "create" | "replace";
  document_id: Slug;
  label: NonEmptyString;
  design_id: Slug;
  design_label: NonEmptyString;
  expected_revision?: string;
  components: ConstructionComponent[];
  instances: ConstructionInstance[];
  boundary_terminals: ConstructionBoundaryTerminal[];
  nets: ConstructionNet[];
  layout?: CircuitLayout;
}
export interface ConstructionComponent {
  alias?: Slug;
  name: NonEmptyString;
  template?: string;
  template_parameters?: {
    [k: string]: ParameterValue;
  };
  terminals?: TerminalDefinition[];
  parameters?: ParameterDefinition[];
  renderer_key?: string;
}
export interface ConstructionInstance {
  alias?: Slug;
  name: NonEmptyString;
  component: NonEmptyString;
  parameter_values?: {
    [k: string]: ParameterValue;
  };
  position?: Point;
}
export interface ConstructionBoundaryTerminal {
  alias?: Slug;
  name: NonEmptyString;
  direction: "input" | "output" | "inout";
  width?: number | string;
  category?: "port" | "interface";
}
export interface ConstructionNet {
  alias?: Slug;
  name?: string;
  /**
   * @minItems 1
   */
  endpoints: [NonEmptyString, ...NonEmptyString[]];
}
export interface CircuitOperationBatch {
  request_id: NonEmptyString;
  expected_revision: NonEmptyString;
  /**
   * @minItems 1
   */
  operations: [CircuitOperation, ...CircuitOperation[]];
}
export interface OperationBase {
  operation_id: NonEmptyString;
  type: string;
  [k: string]: any;
}
export interface SetDocumentLabelOperation {
  operation_id: string;
  type: "set_document_label";
  label: string;
}
export interface CircuitChangeResult {
  status: "accepted" | "rejected" | "conflict" | "locked" | "provider_failed";
  snapshot?: CircuitSnapshot;
  candidate?: CircuitDocument;
  diagnostics: Diagnostic[];
  diff: CircuitDiff;
  alias_map: {
    [k: string]: string;
  };
}
export interface Diagnostic {
  severity: "info" | "warning" | "error";
  code: NonEmptyString;
  message: NonEmptyString;
  element_key?: string;
  operation_id?: string;
  path?: string;
}
export interface CircuitDiff {
  added: ElementChange[];
  removed: ElementChange[];
  changed: ElementChange[];
  connections_changed: Slug[];
}
export interface ElementChange {
  kind: "component" | "instance" | "boundary_terminal" | "net" | "layout" | "timing" | "document";
  id: NonEmptyString;
}
export interface EditLease {
  lease_id: NonEmptyString;
  document_id: Slug;
  owner_id: NonEmptyString;
  expires_at: NonEmptyString;
}
export interface ResolvedComponentDesign {
  status: "available" | "unavailable";
  document?: CircuitDocument;
  provider_revision?: string;
  writable?: boolean;
  message?: string;
}
export interface DocumentSummary {
  document_id: Slug;
  label: NonEmptyString;
  design_id: Slug;
  component_count: number;
  instance_count: number;
  net_count: number;
  warning_count: number;
}
export interface ProviderCommitRequest {
  component: ComponentDefinition;
  base_provider_revision: NonEmptyString;
  batch: CircuitOperationBatch;
  document: CircuitDocument;
  diagnostics: Diagnostic[];
}
export interface ProviderCommitResult {
  accepted: boolean;
  provider_revision: NonEmptyString;
  document?: CircuitDocument;
  diagnostics: Diagnostic[];
}
export interface ServiceEvent {
  event_id: NonEmptyString;
  kind: "document.changed" | "lock.changed" | "proposal.changed" | "provider.requested";
  document_id: Slug;
  revision?: string;
  timestamp: NonEmptyString;
}
export interface ServiceError {
  code: NonEmptyString;
  message: NonEmptyString;
  details?: {
    [k: string]: any;
  };
  diagnostics?: Diagnostic[];
}
