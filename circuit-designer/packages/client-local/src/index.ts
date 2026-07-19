import type {
  AgentProposal,
  ChangePreview,
  CircuitDesignCatalog,
  CircuitDesignerApi,
  CircuitGraphSnapshot,
  CircuitHistoryResult,
  CircuitHistoryStatus,
  CircuitNet,
  CommandBatch,
  DesignerCommand,
  EditLease,
  ValidationDiagnostic,
} from "@spec2gds/circuit-core";

const clone = <T>(value: T): T => structuredClone(value);

export class LocalCircuitError extends Error {
  constructor(message: string, public readonly status = 400) { super(message); }
}

export interface LocalCircuitDesignerOptions {
  now?: () => Date;
}

/**
 * Standalone implementation of the shared circuit API. It intentionally has
 * no HTTP, Python, SpecIR, IP-XACT, or filesystem dependency.
 */
export class LocalCircuitDesignerApi implements CircuitDesignerApi {
  private graph: CircuitGraphSnapshot;
  private readonly original: CircuitGraphSnapshot;
  private undoStack: CircuitGraphSnapshot[] = [];
  private redoStack: CircuitGraphSnapshot[] = [];
  private lease: EditLease | null = null;
  private proposals: AgentProposal[] = [];
  private revision = 0;
  private sequence = 0;
  private readonly now: () => Date;

  constructor(graph: CircuitGraphSnapshot, options: LocalCircuitDesignerOptions = {}) {
    this.original = clone(graph);
    this.graph = this.withLocalCapabilities(clone(graph));
    this.now = options.now ?? (() => new Date());
  }

  async getCatalog(): Promise<CircuitDesignCatalog> {
    return {
      protocol_version: "circuit-designer.v1",
      document_id: this.graph.document_id,
      source_revision_hash: this.graph.source_revision_hash,
      designs: [clone(this.graph.design)],
      entry_design_ids: [this.graph.design.id],
      hierarchy_links: [],
    };
  }

  async getGraph(designId: string): Promise<CircuitGraphSnapshot> {
    if (designId !== this.graph.design.id) throw new LocalCircuitError(`Unknown local design: ${designId}`, 404);
    return clone(this.graph);
  }

  async getLease(): Promise<EditLease | null> {
    if (this.lease && new Date(this.lease.expires_at) <= this.now()) this.lease = null;
    return clone(this.lease);
  }

  async acquireLease(ownerId: string, ownerKind: "human" | "agent", ttlSeconds = 900): Promise<EditLease> {
    const current = await this.getLease();
    if (current && (current.owner_id !== ownerId || current.owner_kind !== ownerKind)) {
      throw new LocalCircuitError(`Local document is locked by ${current.owner_kind} ${current.owner_id}.`, 409);
    }
    this.lease = {
      lease_id: current?.lease_id ?? this.nextId("lease"),
      owner_id: ownerId,
      owner_kind: ownerKind,
      expires_at: new Date(this.now().getTime() + ttlSeconds * 1000).toISOString(),
    };
    return clone(this.lease);
  }

  async releaseLease(leaseId: string): Promise<void> {
    this.requireLease(leaseId);
    this.lease = null;
  }

  async preview(batch: CommandBatch): Promise<ChangePreview> {
    return this.evaluate(batch);
  }

  async apply(batch: CommandBatch, leaseId: string): Promise<ChangePreview> {
    this.requireLease(leaseId);
    const result = this.evaluate(batch);
    if (!result.candidate || result.diagnostics.some((item) => item.severity === "error")) return result;
    this.undoStack.push(clone(this.graph));
    this.redoStack = [];
    this.graph = this.bumpRevision(result.candidate);
    return { ...result, candidate: clone(this.graph) };
  }

  async getHistory(): Promise<CircuitHistoryStatus> {
    return { can_undo: this.undoStack.length > 0, can_redo: this.redoStack.length > 0 };
  }

  async undo(leaseId: string, designId: string): Promise<CircuitHistoryResult> {
    this.requireLease(leaseId); this.requireDesign(designId);
    const prior = this.undoStack.pop();
    if (!prior) throw new LocalCircuitError("Nothing to undo.", 409);
    this.redoStack.push(clone(this.graph));
    this.graph = this.bumpRevision(prior);
    return { ...(await this.getHistory()), graph: clone(this.graph) };
  }

  async redo(leaseId: string, designId: string): Promise<CircuitHistoryResult> {
    this.requireLease(leaseId); this.requireDesign(designId);
    const next = this.redoStack.pop();
    if (!next) throw new LocalCircuitError("Nothing to redo.", 409);
    this.undoStack.push(clone(this.graph));
    this.graph = this.bumpRevision(next);
    return { ...(await this.getHistory()), graph: clone(this.graph) };
  }

  async listProposals(): Promise<AgentProposal[]> { return clone(this.proposals); }

  async submitProposal(proposal: AgentProposal): Promise<AgentProposal> {
    if (this.proposals.some((item) => item.proposal_id === proposal.proposal_id)) {
      throw new LocalCircuitError(`Proposal already exists: ${proposal.proposal_id}`, 409);
    }
    const checked = await this.preview(proposal.batch);
    const saved: AgentProposal = { ...clone(proposal), status: "pending", diagnostics: checked.diagnostics };
    this.proposals.push(saved);
    return clone(saved);
  }

  async decideProposal(proposalId: string, decision: "accepted" | "rejected", leaseId?: string): Promise<AgentProposal> {
    const proposal = this.proposals.find((item) => item.proposal_id === proposalId);
    if (!proposal) throw new LocalCircuitError(`Unknown proposal: ${proposalId}`, 404);
    if (proposal.status !== "pending") throw new LocalCircuitError(`Proposal is already ${proposal.status}.`, 409);
    if (decision === "accepted") {
      if (!leaseId) throw new LocalCircuitError("Accepting a proposal requires an edit lease.", 409);
      const result = await this.apply(proposal.batch, leaseId);
      if (!result.candidate) throw new LocalCircuitError("Proposal is not applicable.", 409);
    }
    proposal.status = decision;
    return clone(proposal);
  }

  /** Restore the bundled example without replacing this API instance. */
  async reset(): Promise<CircuitGraphSnapshot> {
    this.graph = this.bumpRevision(this.withLocalCapabilities(clone(this.original)));
    this.undoStack = []; this.redoStack = []; this.proposals = [];
    return clone(this.graph);
  }

  /** Return a portable renderer-neutral document for download or bug reports. */
  exportGraph(): CircuitGraphSnapshot { return clone(this.graph); }

  private evaluate(batch: CommandBatch): ChangePreview {
    const diagnostics: ValidationDiagnostic[] = [];
    if (batch.expected_source_revision_hash !== this.graph.source_revision_hash) {
      diagnostics.push(this.diagnostic("revision_conflict", "The local document changed; refresh and retry."));
      return { batch: clone(batch), diagnostics };
    }
    const candidate = clone(this.graph);
    for (const command of batch.commands) {
      try { this.applyCommand(candidate, command); }
      catch (reason) {
        diagnostics.push(this.diagnostic("invalid_command", reason instanceof Error ? reason.message : String(reason), command.command_id));
      }
    }
    return { batch: clone(batch), diagnostics, candidate: diagnostics.length ? null : candidate };
  }

  private applyCommand(graph: CircuitGraphSnapshot, command: DesignerCommand): void {
    this.requireDesign(command.design_id);
    const type = command.type;
    if (type === "add_instance") {
      if (graph.nodes.some((item) => item.id === command.node_id)) throw new Error(`Node already exists: ${command.node_id}`);
      let component = graph.components.find((item) => item.id === command.component_id);
      if (!component) {
        component = {
          id: command.component_id,
          label: command.name,
          vlnv: `example:local:${command.name}:0.1`,
          source_ref: this.localRef(command.component_id, "component"),
        };
        graph.components.push(component);
      }
      graph.nodes.push({ id: command.node_id, label: command.name, component_id: component.id, component_vlnv: component.vlnv, terminal_ids: [], configuration_values: {}, source_ref: this.localRef(command.node_id, "instance") });
      return;
    }
    if (type === "update_instance") {
      const node = graph.nodes.find((item) => item.id === command.node_id);
      if (!node) throw new Error(`Unknown node: ${command.node_id}`);
      if (command.component_id !== undefined && command.component_id !== null) {
        const component = graph.components.find((item) => item.id === command.component_id);
        if (!component) throw new Error(`Unknown component: ${command.component_id}`);
        node.component_id = component.id; node.component_vlnv = component.vlnv;
      }
      if (command.name !== undefined && command.name !== null) node.label = command.name;
      if (command.display_name !== undefined) node.display_name = command.display_name ?? undefined;
      if (command.description !== undefined) node.description = command.description ?? undefined;
      if (command.configuration_values !== undefined) node.configuration_values = command.configuration_values ?? {};
      return;
    }
    if (type === "duplicate_instances") {
      for (const nodeId of command.node_ids) this.duplicateNode(graph, nodeId, command.offset);
      return;
    }
    if (type === "delete_instance") {
      const terminalIds = new Set(graph.terminals.filter((item) => item.node_id === command.node_id).map((item) => item.id));
      if (!graph.nodes.some((item) => item.id === command.node_id)) throw new Error(`Unknown node: ${command.node_id}`);
      const connected = graph.nets.filter((net) => net.endpoints.some((endpoint) => terminalIds.has(endpoint.terminal_id)));
      if (connected.length && !command.cascade) throw new Error("Node has connected nets; use cascade deletion.");
      graph.nodes = graph.nodes.filter((item) => item.id !== command.node_id);
      graph.terminals = graph.terminals.filter((item) => item.node_id !== command.node_id);
      graph.nets = graph.nets.filter((net) => !net.endpoints.some((endpoint) => terminalIds.has(endpoint.terminal_id)));
      if (graph.layout?.node_geometry) delete graph.layout.node_geometry[command.node_id];
      return;
    }
    if (type === "add_terminal") {
      const terminalKind = command.kind ?? "port";
      const node = graph.nodes.find((item) => item.id === command.node_id);
      if (!node) throw new Error(`Unknown node: ${command.node_id}`);
      if (graph.terminals.some((item) => item.id === command.terminal_id)) throw new Error(`Terminal already exists: ${command.terminal_id}`);
      if (graph.terminals.some((item) => item.node_id === command.node_id && item.label === command.name)) throw new Error(`Terminal name already exists on the node: ${command.name}`);
      graph.terminals.push({
        id: command.terminal_id,
        node_id: command.node_id,
        label: command.name,
        kind: terminalKind,
        direction: command.direction,
        mapped_port_ids: [],
        declared_bounds: [],
        source_ref: this.localRef(command.terminal_id, terminalKind),
      });
      node.terminal_ids = [...(node.terminal_ids ?? []), command.terminal_id];
      return;
    }
    if (type === "delete_terminal") {
      const terminal = graph.terminals.find((item) => item.id === command.terminal_id);
      if (!terminal) throw new Error(`Unknown terminal: ${command.terminal_id}`);
      const connected = graph.nets.filter((net) => net.endpoints.some((endpoint) => endpoint.terminal_id === command.terminal_id));
      if (connected.length && !command.cascade) throw new Error("Terminal is connected; use cascade deletion.");
      graph.terminals = graph.terminals.filter((item) => item.id !== command.terminal_id);
      if (terminal.node_id) {
        const node = graph.nodes.find((item) => item.id === terminal.node_id);
        if (node) node.terminal_ids = (node.terminal_ids ?? []).filter((id) => id !== command.terminal_id);
      }
      graph.nets = graph.nets.flatMap((net) => {
        if (!net.endpoints.some((endpoint) => endpoint.terminal_id === command.terminal_id)) return [net];
        const endpoints = net.endpoints.filter((endpoint) => endpoint.terminal_id !== command.terminal_id);
        return endpoints.length >= 2 ? [{ ...net, endpoints: endpoints as CircuitNet["endpoints"] }] : [];
      });
      if (graph.layout?.terminal_placements) delete graph.layout.terminal_placements[command.terminal_id];
      if (graph.layout?.net_routes) for (const net of connected) delete graph.layout.net_routes[net.id];
      return;
    }
    if (type === "create_net") {
      if (graph.nets.some((item) => item.id === command.net_id)) throw new Error(`Net already exists: ${command.net_id}`);
      this.requireTerminals(graph, command.terminal_ids);
      graph.nets.push({ id: command.net_id, label: command.name, kind: command.kind, endpoints: command.terminal_ids.map((terminal_id) => ({ terminal_id })) as CircuitNet["endpoints"], source_ref: this.localRef(command.net_id, "connection") });
      return;
    }
    if (type === "rename_net") { this.net(graph, command.net_id).label = command.name; return; }
    if (type === "add_net_endpoint") {
      const net = this.net(graph, command.net_id); this.requireTerminals(graph, [command.terminal_id]);
      if (!net.endpoints.some((item) => item.terminal_id === command.terminal_id)) net.endpoints.push({ terminal_id: command.terminal_id });
      return;
    }
    if (type === "remove_net_endpoint") {
      const net = this.net(graph, command.net_id);
      if (net.endpoints.length <= 2) throw new Error("A net must retain at least two endpoints.");
      net.endpoints = net.endpoints.filter((item) => item.terminal_id !== command.terminal_id) as typeof net.endpoints;
      return;
    }
    if (type === "delete_net") {
      this.net(graph, command.net_id); graph.nets = graph.nets.filter((item) => item.id !== command.net_id);
      if (graph.layout?.net_routes) delete graph.layout.net_routes[command.net_id];
      return;
    }
    if (type === "set_node_geometry") {
      if (!graph.nodes.some((item) => item.id === command.node_id)) throw new Error(`Unknown node: ${command.node_id}`);
      graph.layout ??= {}; graph.layout.node_geometry ??= {}; graph.layout.node_geometry[command.node_id] = clone(command.geometry); return;
    }
    if (type === "set_terminal_placement") {
      this.requireTerminals(graph, [command.terminal_id]); graph.layout ??= {}; graph.layout.terminal_placements ??= {}; graph.layout.terminal_placements[command.terminal_id] = clone(command.placement); return;
    }
    if (type === "set_net_route") {
      this.net(graph, command.net_id); graph.layout ??= {}; graph.layout.net_routes ??= {};
      if (command.route) graph.layout.net_routes[command.net_id] = clone(command.route); else delete graph.layout.net_routes[command.net_id];
      return;
    }
    if (type === "set_layout_direction") { graph.layout ??= {}; graph.layout.direction = command.direction; return; }
    throw new Error(`Unsupported command type: ${String(type)}`);
  }

  private duplicateNode(graph: CircuitGraphSnapshot, nodeId: string, offset = { x: 40, y: 40 }): void {
    const node = graph.nodes.find((item) => item.id === nodeId);
    if (!node) throw new Error(`Unknown node: ${nodeId}`);
    let suffix = 1; let cloneId = `${nodeId}_copy`;
    while (graph.nodes.some((item) => item.id === cloneId)) cloneId = `${nodeId}_copy${++suffix}`;
    const terminalMap = new Map<string, string>();
    const terminals = graph.terminals.filter((item) => item.node_id === nodeId).map((terminal) => {
      const id = `${cloneId}:${terminal.id.slice(nodeId.length + 1)}`; terminalMap.set(terminal.id, id);
      return { ...clone(terminal), id, node_id: cloneId, source_ref: this.localRef(id, terminal.source_ref.kind) };
    });
    graph.terminals.push(...terminals);
    graph.nodes.push({ ...clone(node), id: cloneId, label: `${node.label} copy`, terminal_ids: (node.terminal_ids ?? []).map((id) => terminalMap.get(id) ?? id), source_ref: this.localRef(cloneId, "instance") });
    const geometry = graph.layout?.node_geometry?.[nodeId];
    if (geometry) { graph.layout!.node_geometry![cloneId] = { ...geometry, x: geometry.x + offset.x, y: geometry.y + offset.y, pinned: true }; }
  }

  private requireLease(leaseId: string): void {
    if (!this.lease || this.lease.lease_id !== leaseId || new Date(this.lease.expires_at) <= this.now()) throw new LocalCircuitError("A valid local edit lease is required.", 409);
  }
  private requireDesign(designId: string): void { if (designId !== this.graph.design.id) throw new LocalCircuitError(`Unknown local design: ${designId}`, 404); }
  private requireTerminals(graph: CircuitGraphSnapshot, terminalIds: readonly string[]): void { for (const id of terminalIds) if (!graph.terminals.some((item) => item.id === id)) throw new Error(`Unknown terminal: ${id}`); }
  private net(graph: CircuitGraphSnapshot, netId: string) { const net = graph.nets.find((item) => item.id === netId); if (!net) throw new Error(`Unknown net: ${netId}`); return net; }
  private nextId(prefix: string): string { this.sequence += 1; return `${prefix}_${this.sequence}`; }
  private localRef(source_id: string, kind: string) { return { source_id, kind: `local_${kind}` }; }
  private diagnostic(code: string, message: string, command_id?: string): ValidationDiagnostic { return { code, message, command_id, severity: "error" }; }
  private bumpRevision(graph: CircuitGraphSnapshot): CircuitGraphSnapshot { this.revision += 1; return { ...clone(graph), source_revision_hash: `local:${this.revision}` }; }
  private withLocalCapabilities(graph: CircuitGraphSnapshot): CircuitGraphSnapshot { return { ...graph, capabilities: { edit_topology: true, edit_layout: true, replace_component: true, edit_instance_details: true, submit_agent_proposal: true } }; }
}
