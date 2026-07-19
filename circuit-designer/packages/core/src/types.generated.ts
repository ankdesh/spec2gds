/* Generated from circuit-designer.v1.schema.json. Do not edit. */

export type BatchId = string;
/**
 * @minItems 1
 */
export type Commands = [
  (
    | AddInstanceCommand
    | UpdateInstanceCommand
    | DuplicateInstancesCommand
    | DeleteInstanceCommand
    | CreateNetCommand
    | RenameNetCommand
    | AddNetEndpointCommand
    | RemoveNetEndpointCommand
    | DeleteNetCommand
    | SetNodeGeometryCommand
    | SetTerminalPlacementCommand
    | SetNetRouteCommand
    | SetLayoutDirectionCommand
  ),
  ...(
    | AddInstanceCommand
    | UpdateInstanceCommand
    | DuplicateInstancesCommand
    | DeleteInstanceCommand
    | CreateNetCommand
    | RenameNetCommand
    | AddNetEndpointCommand
    | RemoveNetEndpointCommand
    | DeleteNetCommand
    | SetNodeGeometryCommand
    | SetTerminalPlacementCommand
    | SetNetRouteCommand
    | SetLayoutDirectionCommand
  )[]
];
export type CommandId = string;
export type ComponentId = string;
export type DesignId = string;
export type Name = string;
export type NodeId = string;
export type Type = "add_instance";
export type CommandId1 = string;
export type ComponentId1 = string | null;
export type ConfigurationValues = {
  [k: string]: string;
} | null;
export type Description = string | null;
export type DesignId1 = string;
export type DisplayName = string | null;
export type Name1 = string | null;
export type NodeId1 = string;
export type Type1 = "update_instance";
export type CommandId2 = string;
export type DesignId2 = string;
/**
 * @minItems 1
 */
export type NodeIds = [string, ...string[]];
export type X = number;
export type Y = number;
export type Type2 = "duplicate_instances";
export type Cascade = boolean;
export type CommandId3 = string;
export type DesignId3 = string;
export type NodeId2 = string;
export type Type3 = "delete_instance";
export type CommandId4 = string;
export type DesignId4 = string;
export type Kind = "interface" | "ad_hoc";
export type Name2 = string;
export type NetId = string;
/**
 * @minItems 2
 */
export type TerminalIds = [string, string, ...string[]];
export type Type4 = "create_net";
export type CommandId5 = string;
export type DesignId5 = string;
export type Name3 = string;
export type NetId1 = string;
export type Type5 = "rename_net";
export type CommandId6 = string;
export type DesignId6 = string;
export type NetId2 = string;
export type TerminalId = string;
export type Type6 = "add_net_endpoint";
export type CommandId7 = string;
export type DesignId7 = string;
export type NetId3 = string;
export type TerminalId1 = string;
export type Type7 = "remove_net_endpoint";
export type CommandId8 = string;
export type DesignId8 = string;
export type NetId4 = string;
export type Type8 = "delete_net";
export type CommandId9 = string;
export type DesignId9 = string;
export type Height = number;
export type Pinned = boolean;
export type Width = number;
export type X1 = number;
export type Y1 = number;
export type NodeId3 = string;
export type Type9 = "set_node_geometry";
export type CommandId10 = string;
export type DesignId10 = string;
export type Order = number;
export type Side = "NORTH" | "EAST" | "SOUTH" | "WEST";
export type TerminalId2 = string;
export type Type10 = "set_terminal_placement";
export type CommandId11 = string;
export type DesignId11 = string;
export type NetId5 = string;
export type FromVertex = string;
export type ToVertex = string;
export type Segments = RouteSegment[];
export type Id = string;
export type Kind1 = "endpoint" | "bend" | "junction";
export type TerminalId3 = string | null;
export type Vertices = RouteVertex[];
export type Type11 = "set_net_route";
export type CommandId12 = string;
export type DesignId12 = string;
export type Direction = "RIGHT" | "DOWN";
export type Type12 = "set_layout_direction";
export type ExpectedSourceRevisionHash = string;
export type Id1 = string;
export type Label = string;
export type Kind2 = string;
export type SourceId = string;
export type Vlnv = string | null;
export type Designs = CircuitDesignRef[];
export type DocumentId = string;
export type EntryDesignIds = string[];
export type ComponentId2 = string;
export type InternalDesignId = string;
export type ParentDesignIds = string[];
export type HierarchyLinks = CircuitHierarchyLink[];
export type ProtocolVersion = "circuit-designer.v1";
export type SourceRevisionHash = string;
export type Breadcrumbs = CircuitDesignRef[];
export type EditInstanceDetails = boolean;
export type EditLayout = boolean;
export type EditTopology = boolean;
export type ReplaceComponent = boolean;
export type SubmitAgentProposal = boolean;
export type Id2 = string;
export type Label1 = string;
export type Vlnv1 = string | null;
export type Components = CircuitComponentDefinition[];
export type DocumentId1 = string;
export type Direction1 = "RIGHT" | "DOWN";
/**
 * @minItems 2
 */
export type Endpoints = [CircuitEndpointRef, CircuitEndpointRef, ...CircuitEndpointRef[]];
export type TerminalId4 = string;
export type Id3 = string;
export type Kind3 = "interface" | "ad_hoc";
export type Label2 = string;
export type Nets = CircuitNet[];
export type ComponentId3 = string;
export type ComponentVlnv = string | null;
export type Description1 = string | null;
export type DisplayName1 = string | null;
export type Id4 = string;
export type Label3 = string;
export type TerminalIds1 = string[];
export type Nodes = CircuitNode[];
export type ProtocolVersion1 = "circuit-designer.v1";
export type SourceRevisionHash1 = string;
export type AbstractionVlnv = string | null;
export type BusVlnv = string | null;
export type DeclaredBounds = string[];
export type Direction2 = string | null;
export type Id5 = string;
export type Kind4 = "interface" | "port" | "boundary_interface" | "boundary_port";
export type Label4 = string;
export type MappedPortIds = string[];
export type NodeId4 = string | null;
export type Role = string | null;
export type Terminals = CircuitTerminal[];
export type ExpiresAt = string;
export type LeaseId = string;
export type OwnerId = string;
export type OwnerKind = "human" | "agent";
export type Code = string;
export type CommandId13 = string | null;
export type ElementId = string | null;
export type Message = string;
export type Severity = "info" | "warning" | "error";
export type Diagnostics = ValidationDiagnostic[];
export type Diagnostics1 = ValidationDiagnostic[];
export type ProposalId = string;
export type Status = "pending" | "accepted" | "rejected" | "stale";
export type Title = string;

/**
 * Schema bundle used to generate language-neutral client contracts.
 */
export interface CircuitDesignerProtocol {
  batch: CommandBatch;
  catalog: CircuitDesignCatalog;
  graph: CircuitGraphSnapshot;
  lease: EditLease;
  preview: ChangePreview;
  proposal: AgentProposal;
}
/**
 * Ordered, revision-guarded set of proposed commands.
 */
export interface CommandBatch {
  batch_id: BatchId;
  commands: Commands;
  expected_source_revision_hash: ExpectedSourceRevisionHash;
}
export interface AddInstanceCommand {
  command_id: CommandId;
  component_id: ComponentId;
  design_id: DesignId;
  name: Name;
  node_id: NodeId;
  type?: Type;
}
export interface UpdateInstanceCommand {
  command_id: CommandId1;
  component_id?: ComponentId1;
  configuration_values?: ConfigurationValues;
  description?: Description;
  design_id: DesignId1;
  display_name?: DisplayName;
  name?: Name1;
  node_id: NodeId1;
  type?: Type1;
}
export interface DuplicateInstancesCommand {
  command_id: CommandId2;
  design_id: DesignId2;
  node_ids: NodeIds;
  offset?: Point;
  type?: Type2;
}
/**
 * Canvas-space point.
 */
export interface Point {
  x: X;
  y: Y;
}
export interface DeleteInstanceCommand {
  cascade?: Cascade;
  command_id: CommandId3;
  design_id: DesignId3;
  node_id: NodeId2;
  type?: Type3;
}
export interface CreateNetCommand {
  command_id: CommandId4;
  design_id: DesignId4;
  kind: Kind;
  name: Name2;
  net_id: NetId;
  terminal_ids: TerminalIds;
  type?: Type4;
}
export interface RenameNetCommand {
  command_id: CommandId5;
  design_id: DesignId5;
  name: Name3;
  net_id: NetId1;
  type?: Type5;
}
export interface AddNetEndpointCommand {
  command_id: CommandId6;
  design_id: DesignId6;
  net_id: NetId2;
  terminal_id: TerminalId;
  type?: Type6;
}
export interface RemoveNetEndpointCommand {
  command_id: CommandId7;
  design_id: DesignId7;
  net_id: NetId3;
  terminal_id: TerminalId1;
  type?: Type7;
}
export interface DeleteNetCommand {
  command_id: CommandId8;
  design_id: DesignId8;
  net_id: NetId4;
  type?: Type8;
}
export interface SetNodeGeometryCommand {
  command_id: CommandId9;
  design_id: DesignId9;
  geometry: NodeGeometry;
  node_id: NodeId3;
  type?: Type9;
}
/**
 * Persistable node placement independent of a renderer.
 */
export interface NodeGeometry {
  height: Height;
  pinned?: Pinned;
  width: Width;
  x: X1;
  y: Y1;
}
export interface SetTerminalPlacementCommand {
  command_id: CommandId10;
  design_id: DesignId10;
  placement: TerminalPlacement;
  terminal_id: TerminalId2;
  type?: Type10;
}
/**
 * Optional semantic-terminal placement override.
 */
export interface TerminalPlacement {
  order: Order;
  side: Side;
}
export interface SetNetRouteCommand {
  command_id: CommandId11;
  design_id: DesignId11;
  net_id: NetId5;
  route: NetRoute | null;
  type?: Type11;
}
/**
 * Renderer-neutral route tree for a possibly multi-endpoint net.
 */
export interface NetRoute {
  segments: Segments;
  vertices: Vertices;
}
/**
 * One edge between vertices in an orthogonal route tree.
 */
export interface RouteSegment {
  from_vertex: FromVertex;
  to_vertex: ToVertex;
}
/**
 * Endpoint, bend, or electrical junction in an orthogonal route tree.
 */
export interface RouteVertex {
  id: Id;
  kind: Kind1;
  point: Point1;
  terminal_id?: TerminalId3;
}
/**
 * Canvas-space point.
 */
export interface Point1 {
  x: X;
  y: Y;
}
export interface SetLayoutDirectionCommand {
  command_id: CommandId12;
  design_id: DesignId12;
  direction: Direction;
  type?: Type12;
}
/**
 * Designs available from one immutable source revision.
 */
export interface CircuitDesignCatalog {
  designs: Designs;
  document_id: DocumentId;
  entry_design_ids?: EntryDesignIds;
  hierarchy_links?: HierarchyLinks;
  protocol_version?: ProtocolVersion;
  source_revision_hash: SourceRevisionHash;
}
/**
 * One design available to the circuit canvas.
 */
export interface CircuitDesignRef {
  id: Id1;
  label: Label;
  source_ref: SourceRef;
  vlnv?: Vlnv;
}
/**
 * Opaque adapter-owned locator for one source-backed graph element.
 */
export interface SourceRef {
  kind: Kind2;
  source_id: SourceId;
}
/**
 * Reusable component composition and designs that instantiate it.
 */
export interface CircuitHierarchyLink {
  component_id: ComponentId2;
  internal_design_id: InternalDesignId;
  parent_design_ids?: ParentDesignIds;
}
/**
 * Complete immutable graph payload for one design revision.
 */
export interface CircuitGraphSnapshot {
  breadcrumbs?: Breadcrumbs;
  capabilities?: CircuitCapabilities;
  components: Components;
  design: CircuitDesignRef;
  document_id: DocumentId1;
  layout?: DiagramLayout | null;
  nets: Nets;
  nodes: Nodes;
  protocol_version?: ProtocolVersion1;
  source_revision_hash: SourceRevisionHash1;
  terminals: Terminals;
}
/**
 * Operations supported by the active backend adapter.
 */
export interface CircuitCapabilities {
  edit_instance_details?: EditInstanceDetails;
  edit_layout?: EditLayout;
  edit_topology?: EditTopology;
  replace_component?: ReplaceComponent;
  submit_agent_proposal?: SubmitAgentProposal;
}
/**
 * Reusable component definition exposed by the active adapter.
 */
export interface CircuitComponentDefinition {
  id: Id2;
  label: Label1;
  source_ref: SourceRef;
  vlnv?: Vlnv1;
}
/**
 * One canonical renderer-neutral layout for a design.
 */
export interface DiagramLayout {
  direction?: Direction1;
  net_routes?: NetRoutes;
  node_geometry?: NodeGeometry1;
  terminal_placements?: TerminalPlacements;
}
export interface NetRoutes {
  [k: string]: NetRoute;
}
export interface NodeGeometry1 {
  [k: string]: NodeGeometry;
}
export interface TerminalPlacements {
  [k: string]: TerminalPlacement;
}
/**
 * One interface or ad-hoc multi-endpoint connection.
 */
export interface CircuitNet {
  endpoints: Endpoints;
  id: Id3;
  kind: Kind3;
  label: Label2;
  source_ref: SourceRef;
}
/**
 * Reference from a net to one terminal.
 */
export interface CircuitEndpointRef {
  terminal_id: TerminalId4;
}
/**
 * One component instance in the selected design.
 */
export interface CircuitNode {
  component_id: ComponentId3;
  component_vlnv?: ComponentVlnv;
  configuration_values?: ConfigurationValues1;
  description?: Description1;
  display_name?: DisplayName1;
  id: Id4;
  label: Label3;
  source_ref: SourceRef;
  terminal_ids?: TerminalIds1;
}
export interface ConfigurationValues1 {
  [k: string]: string;
}
/**
 * Interface, physical port, or design-boundary connection point.
 */
export interface CircuitTerminal {
  abstraction_vlnv?: AbstractionVlnv;
  bus_vlnv?: BusVlnv;
  declared_bounds?: DeclaredBounds;
  direction?: Direction2;
  id: Id5;
  kind: Kind4;
  label: Label4;
  mapped_port_ids?: MappedPortIds;
  node_id?: NodeId4;
  role?: Role;
  source_ref: SourceRef;
}
/**
 * Exclusive edit ownership advertised by the application layer.
 */
export interface EditLease {
  expires_at: ExpiresAt;
  lease_id: LeaseId;
  owner_id: OwnerId;
  owner_kind: OwnerKind;
}
/**
 * Non-persisted result of validating one command batch.
 */
export interface ChangePreview {
  batch: CommandBatch;
  candidate?: CircuitGraphSnapshot | null;
  diagnostics: Diagnostics;
}
/**
 * Machine-addressable validation finding.
 */
export interface ValidationDiagnostic {
  code: Code;
  command_id?: CommandId13;
  element_id?: ElementId;
  message: Message;
  severity: Severity;
}
/**
 * Persistable, whole-batch agent change proposal.
 */
export interface AgentProposal {
  batch: CommandBatch;
  diagnostics?: Diagnostics1;
  proposal_id: ProposalId;
  status?: Status;
  title: Title;
}
