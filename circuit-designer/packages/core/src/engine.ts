import type {
  CircuitChangeResult,
  CircuitConstruction,
  CircuitDiff,
  CircuitDocument,
  CircuitInstance,
  CircuitNet,
  CircuitOperation,
  CircuitOperationBatch,
  ComponentDefinition,
  Diagnostic,
  ElementChange,
  NetEndpoint,
  NodeGeometry,
} from "./types.generated";
import { clone, emptyLayout, endpointKey, endpointTerminalKey, validateDocumentSemantics } from "./model";
import { createPrimitiveComponent, isPrimitiveTemplate } from "./primitives";

export interface ApplyOperationOptions {
  allowProviderComponentChanges?: boolean;
}

export interface ConstructionResult {
  document?: CircuitDocument;
  diagnostics: Diagnostic[];
  alias_map: Record<string, string>;
}

const noDiff = (): CircuitDiff => ({ added: [], removed: [], changed: [], connections_changed: [] });

export function slugify(value: string): string {
  const normalized = value.trim().toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "_")
    .replace(/^[_-]+|[_-]+$/g, "")
    .replace(/[_-]{2,}/g, "_");
  return /^[a-z]/.test(normalized) ? normalized : `item_${normalized || "1"}`;
}

export function uniqueSlug(requested: string, used: Iterable<string>): string {
  const base = slugify(requested);
  const values = new Set(used);
  if (!values.has(base)) return base;
  let index = 2;
  while (values.has(`${base}_${index}`)) index += 1;
  return `${base}_${index}`;
}

function error(code: string, message: string, operation_id?: string, element_key?: string): Diagnostic {
  return { severity: "error", code, message, ...(operation_id ? { operation_id } : {}), ...(element_key ? { element_key } : {}) };
}

function equal(first: unknown, second: unknown): boolean {
  return JSON.stringify(first) === JSON.stringify(second);
}

function changes<T extends { id: string }>(
  before: T[],
  after: T[],
  kind: ElementChange["kind"],
): Pick<CircuitDiff, "added" | "removed" | "changed"> {
  const old = new Map(before.map((item) => [item.id, item]));
  const next = new Map(after.map((item) => [item.id, item]));
  return {
    added: [...next.keys()].filter((id) => !old.has(id)).map((id) => ({ kind, id })),
    removed: [...old.keys()].filter((id) => !next.has(id)).map((id) => ({ kind, id })),
    changed: [...next.keys()].filter((id) => old.has(id) && !equal(old.get(id), next.get(id))).map((id) => ({ kind, id })),
  };
}

export function diffDocuments(before: CircuitDocument | undefined, after: CircuitDocument): CircuitDiff {
  if (!before) {
    return {
      added: [
        ...after.components.map((item) => ({ kind: "component" as const, id: item.id })),
        ...after.design.instances.map((item) => ({ kind: "instance" as const, id: item.id })),
        ...after.design.boundary_terminals.map((item) => ({ kind: "boundary_terminal" as const, id: item.id })),
        ...after.design.nets.map((item) => ({ kind: "net" as const, id: item.id })),
      ],
      removed: [],
      changed: [],
      connections_changed: after.design.nets.map((net) => net.id),
    };
  }
  const groups = [
    changes(before.components, after.components, "component"),
    changes(before.design.instances, after.design.instances, "instance"),
    changes(before.design.boundary_terminals, after.design.boundary_terminals, "boundary_terminal"),
    changes(before.design.nets, after.design.nets, "net"),
  ];
  const layoutChanged = equal(before.layout, after.layout) ? [] : [{ kind: "layout" as const, id: after.design.id }];
  const oldNets = new Map(before.design.nets.map((net) => [net.id, net]));
  return {
    added: groups.flatMap((group) => group.added),
    removed: groups.flatMap((group) => group.removed),
    changed: [...groups.flatMap((group) => group.changed), ...layoutChanged],
    connections_changed: after.design.nets
      .filter((net) => !equal(oldNets.get(net.id)?.endpoints, net.endpoints))
      .map((net) => net.id),
  };
}

function endpointEqual(first: NetEndpoint, second: NetEndpoint): boolean {
  return endpointKey(first) === endpointKey(second);
}

function componentTerminals(document: CircuitDocument, instanceId: string): string[] {
  const instance = document.design.instances.find((item) => item.id === instanceId);
  const component = document.components.find((item) => item.id === instance?.component_id);
  return component?.terminals.map((terminal) => `${instanceId}:${terminal.id}`) ?? [];
}

function removeInstance(document: CircuitDocument, id: string, cascade: boolean, operationId: string): Diagnostic[] {
  const instance = document.design.instances.find((item) => item.id === id);
  if (!instance) return [error("unknown_instance", `Unknown instance: ${id}`, operationId, id)];
  const terminalKeys = componentTerminals(document, id);
  const connected = document.design.nets.filter((net) => net.endpoints.some((endpoint) => endpoint.kind === "instance" && endpoint.instance_id === id));
  if (connected.length && !cascade) return [error("cascade_required", `Instance ${id} is connected; explicit cascade is required.`, operationId, id)];
  document.design.instances = document.design.instances.filter((item) => item.id !== id);
  document.design.nets = document.design.nets.map((net) => ({
    ...net,
    endpoints: net.endpoints.filter((endpoint) => endpoint.kind !== "instance" || endpoint.instance_id !== id) as CircuitNet["endpoints"],
  }));
  delete document.layout.instance_geometry[id];
  for (const key of terminalKeys) delete document.layout.terminal_placements[key];
  for (const net of connected) delete document.layout.net_routes[net.id];
  return [];
}

function removeComponent(
  document: CircuitDocument,
  id: string,
  cascade: boolean,
  operationId: string,
  options: ApplyOperationOptions,
): Diagnostic[] {
  const component = document.components.find((item) => item.id === id);
  if (!component) return [error("unknown_component", `Unknown component: ${id}`, operationId, id)];
  if (!component.editable && !options.allowProviderComponentChanges) {
    return [error("component_read_only", `Component ${id} is read-only.`, operationId, id)];
  }
  const instances = document.design.instances.filter((item) => item.component_id === id);
  if (instances.length && !cascade) return [error("cascade_required", `Component ${id} is instantiated; explicit cascade is required.`, operationId, id)];
  for (const instance of instances) {
    const diagnostics = removeInstance(document, instance.id, true, operationId);
    if (diagnostics.length) return diagnostics;
  }
  document.components = document.components.filter((item) => item.id !== id);
  return [];
}

function updateComponent(
  document: CircuitDocument,
  component: ComponentDefinition,
  cascade: boolean,
  operationId: string,
  options: ApplyOperationOptions,
): Diagnostic[] {
  const current = document.components.find((item) => item.id === component.id);
  if (!current) return [error("unknown_component", `Unknown component: ${component.id}`, operationId, component.id)];
  if (!current.editable && !options.allowProviderComponentChanges) {
    return [error("component_read_only", `Component ${component.id} is read-only.`, operationId, component.id)];
  }
  const removedTerminals = new Set(current.terminals.filter((terminal) => !component.terminals.some((next) => next.id === terminal.id)).map((terminal) => terminal.id));
  const affectedInstances = new Set(document.design.instances.filter((instance) => instance.component_id === component.id).map((instance) => instance.id));
  const affectedNets = document.design.nets.filter((net) => net.endpoints.some((endpoint) =>
    endpoint.kind === "instance" && affectedInstances.has(endpoint.instance_id) && removedTerminals.has(endpoint.terminal_id)));
  if (affectedNets.length && !cascade) {
    return [error("cascade_required", `Component update removes connected terminals; explicit cascade is required.`, operationId, component.id)];
  }
  document.components = document.components.map((item) => item.id === component.id ? clone(component) : item);
  if (affectedNets.length) {
    document.design.nets = document.design.nets.map((net) => ({
      ...net,
      endpoints: net.endpoints.filter((endpoint) =>
        endpoint.kind !== "instance" || !affectedInstances.has(endpoint.instance_id) || !removedTerminals.has(endpoint.terminal_id)) as CircuitNet["endpoints"],
    }));
    for (const net of affectedNets) delete document.layout.net_routes[net.id];
  }
  for (const instanceId of affectedInstances) {
    for (const terminalId of removedTerminals) {
      delete document.layout.terminal_placements[`${instanceId}:${terminalId}`];
    }
  }
  return [];
}

function applyOne(document: CircuitDocument, operation: CircuitOperation, options: ApplyOperationOptions): Diagnostic[] {
  const id = operation.operation_id;
  switch (operation.type) {
    case "add_component":
      if (document.components.some((item) => item.id === operation.component.id)) return [error("duplicate_component", `Component already exists: ${operation.component.id}`, id)];
      document.components.push(clone(operation.component)); return [];
    case "update_component":
      return updateComponent(document, operation.component, operation.cascade ?? false, id, options);
    case "remove_component":
      return removeComponent(document, operation.component_id, operation.cascade ?? false, id, options);
    case "add_instance":
      if (document.design.instances.some((item) => item.id === operation.instance.id)) return [error("duplicate_instance", `Instance already exists: ${operation.instance.id}`, id)];
      document.design.instances.push(clone(operation.instance)); return [];
    case "update_instance":
      if (!document.design.instances.some((item) => item.id === operation.instance.id)) return [error("unknown_instance", `Unknown instance: ${operation.instance.id}`, id)];
      document.design.instances = document.design.instances.map((item) => item.id === operation.instance.id ? clone(operation.instance) : item);
      return [];
    case "remove_instance":
      return removeInstance(document, operation.instance_id, operation.cascade ?? false, id);
    case "add_boundary_terminal":
      if (document.design.boundary_terminals.some((item) => item.id === operation.terminal.id)) return [error("duplicate_boundary_terminal", `Boundary terminal already exists: ${operation.terminal.id}`, id)];
      document.design.boundary_terminals.push(clone(operation.terminal)); return [];
    case "update_boundary_terminal": {
      const current = document.design.boundary_terminals.find((item) => item.id === operation.terminal.id);
      if (!current) return [error("unknown_boundary_terminal", `Unknown boundary terminal: ${operation.terminal.id}`, id)];
      const affected = document.design.nets.filter((net) => net.endpoints.some((endpoint) =>
        endpoint.kind === "boundary"
        && endpoint.terminal_id === current.id
        && Boolean(endpoint.slice)
        && (typeof operation.terminal.width !== "number"
          || endpoint.slice!.lsb + endpoint.slice!.width > operation.terminal.width)));
      if (affected.length && !operation.cascade) return [error("cascade_required", `Boundary terminal update invalidates connected slices; explicit cascade is required.`, id)];
      document.design.boundary_terminals = document.design.boundary_terminals.map((item) => item.id === current.id ? clone(operation.terminal) : item);
      if (affected.length) {
        document.design.nets = document.design.nets.map((net) => ({
          ...net,
          endpoints: net.endpoints.filter((endpoint) => endpoint.kind !== "boundary" || endpoint.terminal_id !== current.id) as CircuitNet["endpoints"],
        }));
      }
      return [];
    }
    case "remove_boundary_terminal": {
      const exists = document.design.boundary_terminals.some((item) => item.id === operation.terminal_id);
      if (!exists) return [error("unknown_boundary_terminal", `Unknown boundary terminal: ${operation.terminal_id}`, id)];
      const affected = document.design.nets.filter((net) => net.endpoints.some((endpoint) => endpoint.kind === "boundary" && endpoint.terminal_id === operation.terminal_id));
      if (affected.length && !operation.cascade) return [error("cascade_required", `Boundary terminal is connected; explicit cascade is required.`, id)];
      document.design.boundary_terminals = document.design.boundary_terminals.filter((item) => item.id !== operation.terminal_id);
      document.design.nets = document.design.nets.map((net) => ({
        ...net,
        endpoints: net.endpoints.filter((endpoint) => endpoint.kind !== "boundary" || endpoint.terminal_id !== operation.terminal_id) as CircuitNet["endpoints"],
      }));
      delete document.layout.terminal_placements[`boundary:${operation.terminal_id}`];
      for (const net of affected) delete document.layout.net_routes[net.id];
      return [];
    }
    case "create_net":
      if (document.design.nets.some((item) => item.id === operation.net.id)) return [error("duplicate_net", `Net already exists: ${operation.net.id}`, id)];
      document.design.nets.push(clone(operation.net)); return [];
    case "update_net":
      if (!document.design.nets.some((item) => item.id === operation.net.id)) return [error("unknown_net", `Unknown net: ${operation.net.id}`, id)];
      document.design.nets = document.design.nets.map((item) => item.id === operation.net.id ? clone(operation.net) : item);
      delete document.layout.net_routes[operation.net.id]; return [];
    case "delete_net":
      if (!document.design.nets.some((item) => item.id === operation.net_id)) return [error("unknown_net", `Unknown net: ${operation.net_id}`, id)];
      document.design.nets = document.design.nets.filter((item) => item.id !== operation.net_id);
      delete document.layout.net_routes[operation.net_id]; return [];
    case "connect_endpoint": {
      const net = document.design.nets.find((item) => item.id === operation.net_id);
      if (!net) return [error("unknown_net", `Unknown net: ${operation.net_id}`, id)];
      if (!net.endpoints.some((item) => endpointEqual(item, operation.endpoint))) net.endpoints.push(clone(operation.endpoint));
      delete document.layout.net_routes[net.id]; return [];
    }
    case "disconnect_endpoint": {
      const net = document.design.nets.find((item) => item.id === operation.net_id);
      if (!net) return [error("unknown_net", `Unknown net: ${operation.net_id}`, id)];
      net.endpoints = net.endpoints.filter((item) => !endpointEqual(item, operation.endpoint)) as CircuitNet["endpoints"];
      delete document.layout.net_routes[net.id]; return [];
    }
    case "set_instance_geometry":
      if (!document.design.instances.some((item) => item.id === operation.instance_id)) return [error("unknown_instance", `Unknown instance: ${operation.instance_id}`, id)];
      document.layout.instance_geometry[operation.instance_id] = clone(operation.geometry);
      for (const net of document.design.nets.filter((item) => item.endpoints.some((endpoint) => endpoint.kind === "instance" && endpoint.instance_id === operation.instance_id))) delete document.layout.net_routes[net.id];
      return [];
    case "set_terminal_placement":
      if (operation.placement) document.layout.terminal_placements[operation.terminal_key] = clone(operation.placement);
      else delete document.layout.terminal_placements[operation.terminal_key];
      for (const net of document.design.nets.filter((item) => item.endpoints.some((endpoint) => endpointTerminalKey(endpoint) === operation.terminal_key))) delete document.layout.net_routes[net.id];
      return [];
    case "set_net_route":
      if (!document.design.nets.some((item) => item.id === operation.net_id)) return [error("unknown_net", `Unknown net: ${operation.net_id}`, id)];
      if (operation.route) document.layout.net_routes[operation.net_id] = clone(operation.route);
      else delete document.layout.net_routes[operation.net_id];
      return [];
    case "set_label_geometry":
      if (operation.geometry) document.layout.label_geometry[operation.element_key] = clone(operation.geometry);
      else delete document.layout.label_geometry[operation.element_key];
      return [];
    case "set_layout_settings":
      if (operation.grid_size !== undefined) document.layout.grid_size = operation.grid_size;
      if (operation.direction !== undefined) document.layout.direction = operation.direction;
      return [];
  }
}

export function applyOperations(
  document: CircuitDocument,
  operations: readonly CircuitOperation[],
  options: ApplyOperationOptions = {},
): CircuitChangeResult {
  const candidate = clone(document);
  const diagnostics: Diagnostic[] = [];
  for (const operation of operations) diagnostics.push(...applyOne(candidate, operation, options));
  if (!diagnostics.some((item) => item.severity === "error")) diagnostics.push(...validateDocumentSemantics(candidate));
  const rejected = diagnostics.some((item) => item.severity === "error");
  return {
    status: rejected ? "rejected" : "accepted",
    ...(rejected ? {} : { candidate }),
    diagnostics,
    diff: rejected ? noDiff() : diffDocuments(document, candidate),
    alias_map: {},
  };
}

function parseEndpoint(
  value: string,
  instances: Map<string, string>,
  boundaries: Map<string, string>,
  document: CircuitDocument,
): NetEndpoint | undefined {
  const rangeMatch = value.match(/^(.*)\[(\d+)(?::(\d+))?\]$/);
  const reference = rangeMatch ? rangeMatch[1] : value;
  const slice = rangeMatch
    ? (() => {
        const first = Number(rangeMatch[2]);
        const second = rangeMatch[3] === undefined ? first : Number(rangeMatch[3]);
        return { lsb: Math.min(first, second), width: Math.abs(first - second) + 1 };
      })()
    : undefined;
  if (reference.startsWith("boundary.")) {
    const alias = reference.slice("boundary.".length);
    const terminal_id = boundaries.get(alias) ?? alias;
    return { kind: "boundary", terminal_id, ...(slice ? { slice } : {}) };
  }
  const separator = reference.lastIndexOf(".");
  if (separator < 1) return undefined;
  const instanceAlias = reference.slice(0, separator);
  const terminalAlias = reference.slice(separator + 1);
  const instance_id = instances.get(instanceAlias) ?? instanceAlias;
  const instance = document.design.instances.find((item) => item.id === instance_id);
  const component = document.components.find((item) => item.id === instance?.component_id);
  const terminal_id = component?.terminals.find((item) => item.id === terminalAlias || slugify(item.label) === terminalAlias)?.id ?? terminalAlias;
  return { kind: "instance", instance_id, terminal_id, ...(slice ? { slice } : {}) };
}

function fillGeometry(document: CircuitDocument): void {
  const grid = document.layout.grid_size;
  const placed = Object.values(document.layout.instance_geometry);
  let index = 0;
  for (const instance of document.design.instances) {
    if (document.layout.instance_geometry[instance.id]) continue;
    const column = index % 5;
    const row = Math.floor(index / 5);
    document.layout.instance_geometry[instance.id] = {
      x: grid * (4 + column * 14),
      y: grid * (4 + row * 9),
      width: grid * 9,
      height: grid * 5,
      pinned: false,
    };
    index += 1;
  }
  void placed;
}

export function compileConstruction(construction: CircuitConstruction): ConstructionResult {
  const aliases: Record<string, string> = {};
  const components: ComponentDefinition[] = [];
  const usedComponents = new Set<string>();
  for (const input of construction.components) {
    const id = uniqueSlug(input.alias ?? input.name, usedComponents);
    usedComponents.add(id);
    aliases[input.alias ?? input.name] = id;
    const component = input.template && isPrimitiveTemplate(input.template)
      ? createPrimitiveComponent(input.template, id, input.name, input.template_parameters)
      : {
          id,
          label: input.name,
          origin: "local" as const,
          editable: true,
          terminals: clone(input.terminals ?? []),
          parameters: clone(input.parameters ?? []),
          appearance: { renderer_key: input.renderer_key ?? "generic", properties: {} },
        };
    components.push(component);
  }
  const instances: CircuitInstance[] = [];
  const instanceAliases = new Map<string, string>();
  const usedInstances = new Set<string>();
  for (const input of construction.instances) {
    const id = uniqueSlug(input.alias ?? input.name, usedInstances);
    usedInstances.add(id);
    instanceAliases.set(input.alias ?? input.name, id);
    aliases[input.alias ?? input.name] = id;
    const component_id = aliases[input.component] ?? input.component;
    instances.push({ id, label: input.name, component_id, parameter_values: clone(input.parameter_values ?? {}) });
  }
  const boundaries = construction.boundary_terminals.map((input) => ({
    id: slugify(input.alias ?? input.name),
    label: input.name,
    direction: input.direction,
    width: input.width ?? 1,
    ...(input.category ? { category: input.category } : {}),
  }));
  const boundaryAliases = new Map(construction.boundary_terminals.map((input, index) => [input.alias ?? input.name, boundaries[index].id]));
  const document: CircuitDocument = {
    protocol_version: "circuit-designer.v1",
    document_id: construction.document_id,
    label: construction.label,
    components,
    design: {
      id: construction.design_id,
      label: construction.design_label,
      boundary_terminals: boundaries,
      instances,
      nets: [],
    },
    layout: clone(construction.layout ?? emptyLayout()),
  };
  for (const input of construction.instances) {
    if (!input.position) continue;
    const id = instanceAliases.get(input.alias ?? input.name)!;
    document.layout.instance_geometry[id] = { x: input.position.x, y: input.position.y, width: 180, height: 100, pinned: true };
  }
  const usedNets = new Set<string>();
  for (const input of construction.nets) {
    const id = uniqueSlug(input.alias ?? input.name ?? "net", usedNets);
    usedNets.add(id);
    aliases[input.alias ?? input.name ?? id] = id;
    const endpoints = input.endpoints
      .map((value) => parseEndpoint(value, instanceAliases, boundaryAliases, document))
      .filter((value): value is NetEndpoint => Boolean(value));
    document.design.nets.push({ id, label: input.name ?? "", endpoints: endpoints as CircuitNet["endpoints"] });
  }
  fillGeometry(document);
  const diagnostics = validateDocumentSemantics(document);
  if (construction.nets.some((net) => net.endpoints.length) && document.design.nets.some((net, index) => net.endpoints.length !== construction.nets[index].endpoints.length)) {
    diagnostics.push(error("invalid_construction_endpoint", "One or more construction endpoints could not be parsed."));
  }
  return {
    ...(diagnostics.some((item) => item.severity === "error") ? {} : { document }),
    diagnostics,
    alias_map: aliases,
  };
}

export function createOperationBatch(requestId: string, expectedRevision: string, operations: CircuitOperation[]): CircuitOperationBatch {
  if (!operations.length) throw new Error("An operation batch requires at least one operation.");
  return { request_id: requestId, expected_revision: expectedRevision, operations: operations as CircuitOperationBatch["operations"] };
}

export function geometryOperation(
  operationId: string,
  instanceId: string,
  geometry: NodeGeometry,
): CircuitOperation {
  return { operation_id: operationId, type: "set_instance_geometry", instance_id: instanceId, geometry };
}
