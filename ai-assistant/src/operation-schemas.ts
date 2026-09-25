import type { ValueSchemaSpec } from "@deepseek-ai/dsh-tools";

type Schema = ValueSchemaSpec;
type Properties = Record<string, Schema & { required?: true }>;

const string = (options: Omit<Extract<Schema, { type: "string" }>, "type"> = {}): Schema => ({ type: "string", ...options });
const number = (): Schema => ({ type: "number" });
const integer = (): Schema => ({ type: "integer" });
const boolean = (options: Omit<Extract<Schema, { type: "boolean" }>, "type"> = {}): Schema => ({ type: "boolean", ...options });
const nullable = (schema: Schema): Schema => ({ oneOf: [schema, { type: "null" }] });
const array = (items: Schema): Schema => ({ type: "array", items });
const object = (properties: Properties): Schema => ({ type: "object", properties, additionalProperties: false });
const required = <T extends Schema>(schema: T): T & { required: true } => ({ ...schema, required: true });
const literal = (value: string): Schema => string({ const: value });
const strings = (...values: string[]): Schema => string({ enum: values });

const scalar = { oneOf: [string(), number(), boolean(), { type: "null" }] } satisfies Schema;
const circuitSlice = object({ lsb: required(integer()), width: required(integer()) });
const circuitEndpoint = {
  oneOf: [
    object({ kind: required(literal("instance")), instance_id: required(string()), terminal_id: required(string()), slice: required(nullable(circuitSlice)) }),
    object({ kind: required(literal("boundary")), terminal_id: required(string()), slice: required(nullable(circuitSlice)) }),
  ],
} satisfies Schema;
const circuitTerminal = object({
  id: required(string()), label: required(string()), direction: required(strings("input", "output", "inout")),
  width: required({ oneOf: [integer(), string()] }), category: required(strings("port", "interface")),
});
const circuitParameter = {
  oneOf: [
    object({ id: required(string()), label: required(string()), type: required(literal("string")), default: required(string()) }),
    object({ id: required(string()), label: required(string()), type: required(literal("number")), default: required(number()), minimum: required(nullable(number())), maximum: required(nullable(number())) }),
    object({ id: required(string()), label: required(string()), type: required(literal("boolean")), default: required(boolean()) }),
    object({ id: required(string()), label: required(string()), type: required(literal("enum")), default: required(string()), values: required(array(string())) }),
  ],
} satisfies Schema;
const nameValue = object({ name: required(string()), value: required(scalar) });
const circuitComponent = object({
  id: required(string()), label: required(string()), origin: required(strings("local", "builtin", "provider")), editable: required(boolean()),
  terminals: required(array(circuitTerminal)), parameters: required(array(circuitParameter)),
  appearance: required(object({ renderer_key: required(string()), properties: required(array(nameValue)) })),
});
const circuitInstance = object({
  id: required(string()), label: required(string()), component_id: required(string()),
  parameter_values: required(array(object({ name: required(string()), value: required({ oneOf: [string(), number(), boolean()] }) }))),
});
const circuitNet = object({ id: required(string()), label: required(string()), endpoints: required(array(circuitEndpoint)) });
const operationBase = (type: string, fields: Properties): Schema => object({
  operation_id: required(string()), type: required(literal(type)), ...fields,
});

export const CIRCUIT_OPERATION_SCHEMA: Schema = {
  oneOf: [
    operationBase("add_component", { component: required(circuitComponent) }),
    operationBase("update_component", { component: required(circuitComponent), cascade: required(boolean()) }),
    operationBase("remove_component", { component_id: required(string()), cascade: required(boolean()) }),
    operationBase("add_instance", { instance: required(circuitInstance) }),
    operationBase("update_instance", { instance: required(circuitInstance) }),
    operationBase("remove_instance", { instance_id: required(string()), cascade: required(boolean()) }),
    operationBase("add_boundary_terminal", { terminal: required(circuitTerminal) }),
    operationBase("update_boundary_terminal", { terminal: required(circuitTerminal), cascade: required(boolean()) }),
    operationBase("remove_boundary_terminal", { terminal_id: required(string()), cascade: required(boolean()) }),
    operationBase("create_net", { net: required(circuitNet) }),
    operationBase("update_net", { net: required(circuitNet) }),
    operationBase("delete_net", { net_id: required(string()) }),
    operationBase("connect_endpoint", { net_id: required(string()), endpoint: required(circuitEndpoint) }),
    operationBase("disconnect_endpoint", { net_id: required(string()), endpoint: required(circuitEndpoint) }),
  ],
};

const entityRef = object({
  document_id: required(string()), entity_id: required(string()),
  entity_kind: required(strings("component", "design", "bus_definition", "abstraction_definition", "narrative_block")),
});
const specInstance = object({ name: required(string()), component_vlnv: required(string()) });
const specParameter = object({
  name: required(string()), value: required(string()), resolve: required(nullable(string())), data_type: required(nullable(string())),
  choice_ref: required(nullable(string())), minimum: required(nullable(string())), maximum: required(nullable(string())), description: required(nullable(string())),
});
const specPort = {
  oneOf: [
    object({ name: required(string()), family: required(literal("wire")), display_name: required(nullable(string())), description: required(nullable(string())), direction: required(strings("in", "out", "inout")), range: required(nullable(string())) }),
    object({ name: required(string()), family: required(literal("transactional")), display_name: required(nullable(string())), description: required(nullable(string())), initiative: required(strings("requires", "provides", "both")), kind: required(nullable(strings("tlm_port", "tlm_socket", "simple_socket", "multi_socket", "custom"))), custom_kind: required(nullable(string())), bus_width: required(nullable(string())) }),
    object({ name: required(string()), family: required(literal("structured")), display_name: required(nullable(string())), description: required(nullable(string())), direction: required(strings("in", "out", "inout")) }),
  ],
} satisfies Schema;
const portMap = object({ logical: required(string()), physical: required(string()), tie_off: required(nullable(string())), invert: required(nullable(boolean())), informative: required(nullable(boolean())) });
const busInterface = object({
  name: required(string()), role: required(strings("initiator", "target", "system", "monitor")), bus_vlnv: required(string()), abstraction_vlnv: required(string()),
  connection_required: required(nullable(boolean())), bits_in_lau: required(nullable(string())), endianness: required(nullable(string())),
  description: required(nullable(string())), port_maps: required(array(portMap)),
});
const interfaceConnection = object({
  name: required(string()), kind: required(literal("interface")),
  interface_endpoints: required(array(object({ instance_name: required(string()), interface_name: required(string()) }))),
  hierarchy_interfaces: required(array(string())),
});
const adHocConnection = object({
  name: required(string()), kind: required(literal("ad_hoc")),
  port_endpoints: required(array(object({ instance_name: required(string()), port_name: required(string()) }))),
  external_ports: required(array(string())),
});
const abstractionRole = object({
  group: required(nullable(string())), direction: required(nullable(string())), initiative: required(nullable(string())),
  presence: required(nullable(string())), width: required(nullable(string())), bus_width: required(nullable(string())),
});
const abstractionPort = object({
  name: required(string()), style: required(strings("wire", "transactional")), match: required(nullable(boolean())), description: required(nullable(string())),
  qualifiers: required(array(string())), on_initiator: required(nullable(abstractionRole)), on_target: required(nullable(abstractionRole)), on_system: required(array(abstractionRole)),
});

export const SPEC_OPERATION_SCHEMA: Schema = {
  oneOf: [
    operationBase("create_entity", {
      kind: required(strings("component", "design")), name: required(string()), instances: required(array(specInstance)),
      ports: array(specPort), systemverilog: nullable(string()),
    }),
    operationBase("set_entity_metadata", { entity: required(entityRef), display_name: required(nullable(string())), short_description: required(nullable(string())), description: required(nullable(string())), clear_fields: required(array(strings("display_name", "short_description", "description"))) }),
    operationBase("upsert_parameter", { entity: required(entityRef), parameter: required(specParameter) }),
    operationBase("delete_parameter", { entity: required(entityRef), name: required(string()) }),
    operationBase("upsert_component_port", { component: required(entityRef), port: required(specPort) }),
    operationBase("delete_component_port", { component: required(entityRef), name: required(string()) }),
    operationBase("upsert_bus_interface", { component: required(entityRef), interface: required(busInterface) }),
    operationBase("delete_bus_interface", { component: required(entityRef), name: required(string()) }),
    operationBase("upsert_channel", { component: required(entityRef), channel: required(object({ name: required(string()), interfaces: required(array(string())), description: required(nullable(string())) })) }),
    operationBase("delete_channel", { component: required(entityRef), name: required(string()) }),
    operationBase("upsert_instance", { design: required(entityRef), instance: required(specInstance) }),
    operationBase("delete_instance", { design: required(entityRef), instance_name: required(string()) }),
    operationBase("reorder_instances", { design: required(entityRef), instance_names: required(array(string())) }),
    operationBase("upsert_connection", { design: required(entityRef), connection: required({ oneOf: [interfaceConnection, adHocConnection] }) }),
    operationBase("delete_connection", { design: required(entityRef), connection_name: required(string()) }),
    operationBase("reorder_connections", { design: required(entityRef), kind: required(strings("interface", "ad_hoc")), connection_names: required(array(string())) }),
    operationBase("set_internal_design", { component: required(entityRef), internal_design: required(entityRef) }),
    operationBase("clear_internal_design", { component: required(entityRef) }),
    operationBase("update_bus_definition", { bus_definition: required(entityRef), properties: required(object({
      direct_connection: required(nullable(boolean())), broadcast: required(nullable(boolean())), addressable: required(nullable(boolean())), extends_vlnv: required(nullable(string())),
      max_initiators: required(nullable(integer())), max_targets: required(nullable(integer())), system_groups: required(nullable(array(string()))),
      clear_fields: required(array(strings("direct_connection", "broadcast", "addressable", "extends_vlnv", "max_initiators", "max_targets", "system_groups"))),
    })) }),
    operationBase("set_abstraction_bus_type", { abstraction_definition: required(entityRef), bus_vlnv: required(string()) }),
    operationBase("upsert_abstraction_port", { abstraction_definition: required(entityRef), port: required(abstractionPort) }),
    operationBase("delete_abstraction_port", { abstraction_definition: required(entityRef), name: required(string()) }),
    operationBase("upsert_narrative_block", { block: required({ type: "json", description: "Exact recursive block {block_id,type,text,inlines,children,ordered,rows,asset_id,alt_text,caption,entity_refs,renderer_id,options:[{key,value}]} with no extra fields." }), parent_block_id: required(nullable(string())), index: required(nullable(integer())) }),
    operationBase("delete_narrative_block", { block_id: required(string()) }),
    operationBase("reorder_narrative_blocks", { block_ids: required(array(string())), parent_block_id: required(nullable(string())) }),
    operationBase("set_narrative_entity_links", { block_id: required(string()), entity_refs: required(array(entityRef)) }),
    operationBase("upsert_entity_section", { owner: required(entityRef), section_type: required(literal("sv")), type_version: required({ type: "integer", const: 1 }), section_id: required(nullable(string())), payload: required(object({ content: required(string()) })) }),
    operationBase("delete_entity_section", { owner: required(entityRef), section_type: required(literal("sv")), section_id: required(nullable(string())) }),
  ],
};

export function validateProposalSemantics(domain: "spec" | "circuit", supported: boolean, reason: string | null, operations: unknown[]): void {
  if (supported && operations.length === 0) throw new Error("A supported proposal must contain at least one operation.");
  if (!supported && operations.length !== 0) throw new Error("An unsupported request cannot contain operations.");
  if (!supported && !reason?.trim()) throw new Error("An unsupported request must include unsupported_reason.");
  if (supported && reason !== null) throw new Error("A supported proposal must use unsupported_reason=null.");
  const ids = new Set<string>();
  for (const [index, value] of operations.entries()) {
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`Operation ${index + 1} must be an object.`);
    const operation = value as Record<string, unknown>;
    const id = operation.operation_id;
    if (typeof id !== "string" || !id.trim()) throw new Error(`Operation ${index + 1} requires operation_id.`);
    if (ids.has(id)) throw new Error(`Duplicate operation_id: ${id}`);
    ids.add(id);
    if (domain === "circuit") validateCircuitSemantic(operation);
    else validateSpecSemantic(operation);
  }
}

function validateCircuitSemantic(operation: Record<string, unknown>): void {
  const type = String(operation.type ?? "");
  if ((type === "create_net" || type === "update_net") && isObject(operation.net) && Array.isArray(operation.net.endpoints) && operation.net.endpoints.length === 0) {
    throw new Error(`${type} requires at least one endpoint.`);
  }
  if (type === "add_component" && isObject(operation.component) && (operation.component.origin !== "local" || operation.component.editable !== true)) {
    throw new Error("New Circuit components must be local and editable.");
  }
  const component = isObject(operation.component) ? operation.component : null;
  const parameters = component && Array.isArray(component.parameters) ? component.parameters : [];
  for (const parameter of parameters) {
    if (isObject(parameter) && parameter.type === "enum" && Array.isArray(parameter.values) && !parameter.values.includes(parameter.default)) {
      throw new Error(`Enum parameter ${String(parameter.id)} has a default outside values.`);
    }
  }
}

function validateSpecSemantic(operation: Record<string, unknown>): void {
  if (operation.type === "create_entity") {
    if (typeof operation.name !== "string" || !/^[A-Za-z_][A-Za-z0-9_.-]*$/.test(operation.name)) throw new Error("New Spec entity names must be XML-compatible identifiers.");
    if (operation.kind === "component" && Array.isArray(operation.instances) && operation.instances.length) throw new Error("A new component cannot contain design instances.");
    if (operation.kind === "design" && Array.isArray(operation.ports) && operation.ports.length) throw new Error("A new design cannot contain component ports.");
    if (operation.kind === "design" && operation.systemverilog != null) throw new Error("Initial SystemVerilog behavior is supported only for components.");
    const names = Array.isArray(operation.ports) ? operation.ports.map(port => isObject(port) ? String(port.name ?? "") : "") : [];
    if (new Set(names).size !== names.length) throw new Error("Initial component port names must be unique.");
    if (typeof operation.systemverilog === "string") validateSystemverilog(operation.systemverilog);
  }
  if (operation.type === "upsert_connection" && isObject(operation.connection)) {
    const connection = operation.connection;
    const count = (Array.isArray(connection.port_endpoints) ? connection.port_endpoints.length : 0) + (Array.isArray(connection.external_ports) ? connection.external_ports.length : 0);
    if (connection.kind === "ad_hoc" && count < 2) throw new Error("An ad-hoc connection requires at least two endpoints.");
    if (connection.kind === "interface" && (!Array.isArray(connection.interface_endpoints) || connection.interface_endpoints.length < 2)) throw new Error("An interface connection requires at least two endpoints.");
  }
  if (operation.type === "upsert_component_port" && isObject(operation.port) && operation.port.family === "transactional") {
    const custom = typeof operation.port.custom_kind === "string" && operation.port.custom_kind.trim() !== "";
    if ((operation.port.kind === "custom") !== custom) throw new Error("custom_kind is required exactly when transactional kind is custom.");
  }
  if (operation.type === "upsert_entity_section" && isObject(operation.payload) && typeof operation.payload.content === "string") {
    validateSystemverilog(operation.payload.content);
  }
  if (operation.type === "upsert_narrative_block") validateNarrativeBlock(operation.block, "block");
}

function validateSystemverilog(content: string): void {
  if (content.length > 262_144) throw new Error("SystemVerilog section content exceeds 262,144 characters.");
  if (/\b(module|endmodule)\b|`(?:include|line)\b/.test(content)) throw new Error("SystemVerilog sections accept module-body content only.");
}

function validateNarrativeBlock(value: unknown, path: string): void {
  if (!isObject(value)) throw new Error(`${path} must be a narrative block object.`);
  exactKeys(value, ["block_id", "type", "text", "inlines", "children", "ordered", "rows", "asset_id", "alt_text", "caption", "entity_refs", "renderer_id", "options"], path);
  if (typeof value.block_id !== "string" || !["paragraph", "section", "list", "table", "image", "entity_link", "live_view"].includes(String(value.type))) throw new Error(`${path} has invalid narrative identity or type.`);
  for (const field of ["text", "asset_id", "alt_text", "caption", "renderer_id"]) if (typeof value[field] !== "string") throw new Error(`${path}.${field} must be a string.`);
  if (typeof value.ordered !== "boolean" || !Array.isArray(value.rows) || !Array.isArray(value.inlines) || !Array.isArray(value.children) || !Array.isArray(value.entity_refs) || !Array.isArray(value.options)) throw new Error(`${path} has invalid narrative collection fields.`);
  value.children.forEach((child, index) => validateNarrativeBlock(child, `${path}.children[${index}]`));
  value.inlines.forEach((inline, index) => {
    if (!isObject(inline)) throw new Error(`${path}.inlines[${index}] must be an object.`);
    exactKeys(inline, ["type", "text", "href", "entity_ref"], `${path}.inlines[${index}]`);
    if (!["text", "emphasis", "strong", "code", "link"].includes(String(inline.type)) || typeof inline.text !== "string" || typeof inline.href !== "string" || (inline.entity_ref !== null && !isObject(inline.entity_ref))) throw new Error(`${path}.inlines[${index}] is invalid.`);
  });
  value.options.forEach((option, index) => {
    if (!isObject(option)) throw new Error(`${path}.options[${index}] must be an object.`);
    exactKeys(option, ["key", "value"], `${path}.options[${index}]`);
    if (typeof option.key !== "string" || !["string", "number", "boolean"].includes(typeof option.value)) throw new Error(`${path}.options[${index}] is invalid.`);
  });
}

function exactKeys(value: Record<string, unknown>, keys: string[], path: string): void {
  const expected = new Set(keys);
  const unexpected = Object.keys(value).filter(key => !expected.has(key));
  const missing = keys.filter(key => !Object.hasOwn(value, key));
  if (unexpected.length || missing.length) throw new Error(`${path} fields mismatch; missing=${missing.join(",") || "none"}, unexpected=${unexpected.join(",") || "none"}.`);
}

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
