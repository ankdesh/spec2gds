import { createHash, randomUUID } from "node:crypto";
import { isRecord } from "./types.js";

function entriesToMap(value: unknown): unknown {
  if (!Array.isArray(value)) return value;
  const output: Record<string, unknown> = {};
  for (const item of value) {
    if (!isRecord(item) || typeof item.name !== "string" || !("value" in item)) {
      return value;
    }
    if (Object.hasOwn(output, item.name)) throw new Error(`Duplicate map entry: ${item.name}`);
    output[item.name] = item.value;
  }
  return output;
}

function normalizeNarrativeBlock(value: unknown): void {
  if (!isRecord(value)) return;
  if (Array.isArray(value.options)) {
    const options: Record<string, unknown> = {};
    for (const item of value.options) {
      if (!isRecord(item) || typeof item.key !== "string" || !("value" in item)) {
        throw new Error("Narrative options must contain key/value entries.");
      }
      if (Object.hasOwn(options, item.key)) throw new Error(`Duplicate narrative option: ${item.key}`);
      options[item.key] = item.value;
    }
    value.options = options;
  }
  if (Array.isArray(value.children)) value.children.forEach(normalizeNarrativeBlock);
}

/** HDL-style brackets are common in model output; the Spec API stores compact ranges. */
export function compactWireRange(value: unknown): unknown {
  if (typeof value !== "string") return value;
  const bracketed = /^\[\s*([^\[\]]+?)\s*\]$/.exec(value.trim());
  const range = bracketed ? bracketed[1]!.trim() : value.trim();
  return range.replace(/\s*:\s*/g, ":");
}

/** Only remove presentation fences; never erase HDL declarations or directives. */
export function cleanSystemVerilogBody(value: unknown): unknown {
  if (typeof value !== "string") return value;
  const fence = /^\s*```(?:verilog|systemverilog|v|sv)?\s*\r?\n([\s\S]*?)\r?\n```\s*$/i.exec(value);
  const body = fence ? fence[1]! : value;
  const code = body.replace(/\/\*[\s\S]*?\*\/|\/\/[^\n]*|"(?:\\.|[^"\\])*"/g, match => match.replace(/[^\r\n]/g, " "));
  if (/\b(?:module|endmodule)\b/.test(code)) throw new Error("SystemVerilog must be module-body text. Reauthor the body using the component's stored ports; module wrappers cannot be discarded safely.");
  if (/`(?:include|line)\b/.test(code)) throw new Error("SystemVerilog cannot contain external include or user line directives. Supply self-contained module-body text.");
  return body;
}

/** Formatting admission resolves local aliases and bound references without allocating persistent IDs. */
export function normalizeSpecFormatting(input: unknown[], documentId?: string): Record<string, unknown>[] {
  const operations = input.map((item, index) => {
    if (!isRecord(item) || typeof item.type !== "string") {
      throw new Error(`Spec operation ${index} must be an object with a type.`);
    }
    const operation = structuredClone(item);
    try {
      if (operation.operation_id === undefined) operation.operation_id = `operation_${index + 1}`;
      if (operation.type === "create_entity") {
        if (operation.entity_id === undefined) operation.entity_id = operation.operation_id;
        if (operation.instances === undefined) operation.instances = [];
        // A false entry flag has no effect on components; only designs can be entries.
        if (operation.kind === "component" && operation.entry_design === false) delete operation.entry_design;
        if (operation.kind === "component" && Array.isArray(operation.instances) && operation.instances.length) {
          throw new Error("Only designs contain instances. Create a component-owned internal design instead of placing instances on a component.");
        }
        if (operation.kind === "design" && operation.systemverilog != null) {
          throw new Error("Designs define composition. Remove systemverilog from this Design; put behavioral SV only in the approved Component.");
        }
        if (operation.kind === "component" && typeof operation.systemverilog === "string" && !operation.systemverilog.trim()) {
          throw new Error("systemverilog is empty. Author the requested functional module-body RTL and its set_entity_metadata.description before submitting. For an explicitly interface-only Component, omit systemverilog or use null; do not describe an empty body as implemented.");
        }
        if (operation.systemverilog !== undefined) operation.systemverilog = cleanSystemVerilogBody(operation.systemverilog);
        if (operation.kind === "component" && Array.isArray(operation.ports)) operation.ports.forEach(port => normalizePort(port, true));
      }
      if (operation.type === "upsert_component_port") normalizePort(operation.port, false);
      if (operation.type === "upsert_entity_section" && operation.section_type === "sv" && isRecord(operation.payload)) operation.payload.content = cleanSystemVerilogBody(operation.payload.content);
      if (operation.type === "set_entity_metadata" && Array.isArray(operation.clear_fields)) {
        if (operation.clear_fields.some(field => typeof field !== "string" || !["display_name", "short_description", "description"].includes(field))) throw new Error("Metadata clear_fields contains an invalid field.");
        for (const field of operation.clear_fields) if (typeof field === "string") {
          if (operation[field] !== undefined && operation[field] !== null) throw new Error(`Cannot set and clear metadata field ${field} in the same operation.`);
          operation[field] = null;
        }
        delete operation.clear_fields;
      }
      if (operation.type === "update_bus_definition" && isRecord(operation.properties)) {
        const properties = operation.properties;
        if (Array.isArray(properties.clear_fields)) {
          if (properties.clear_fields.some(field => typeof field !== "string")) throw new Error("Bus clear_fields must contain field names.");
          for (const field of properties.clear_fields) if (typeof field === "string") {
            if (properties[field] !== undefined && properties[field] !== null) throw new Error(`Cannot set and clear bus field ${field} in the same operation.`);
            properties[field] = null;
          }
          delete properties.clear_fields;
        }
      }
      if (operation.type === "upsert_narrative_block") normalizeNarrativeBlock(operation.block);
      return operation;
    } catch (error) {
      const target = operation.name ? ` ${String(operation.kind ?? "")} ${String(operation.name)}` : "";
      throw new Error(`Spec operation ${index + 1} (${operation.type}${target}): ${error instanceof Error ? error.message : String(error)}`);
    }
  });
  const aliases = new Set<string>();
  for (const operation of operations) {
    if (operation.type !== "create_entity" || typeof operation.entity_id !== "string") continue;
    if (aliases.has(operation.entity_id)) throw new Error(`Duplicate creation alias: ${operation.entity_id}`);
    aliases.add(operation.entity_id);
  }
  const bindReferences = (value: unknown): void => {
    if (Array.isArray(value)) { value.forEach(bindReferences); return; }
    if (!isRecord(value)) return;
    if (documentId !== undefined && value.document_id === undefined
      && typeof value.entity_id === "string" && typeof value.entity_kind === "string") value.document_id = documentId;
    Object.values(value).forEach(bindReferences);
  };
  operations.forEach(bindReferences);
  return operations;
}

function normalizePort(value: unknown, creating: boolean): void {
  if (!isRecord(value)) return;
  if (value.family !== undefined && typeof value.family !== "string") throw new Error("Port family must be a string.");
  if (value.family === undefined && (creating || typeof value.range === "string")
    && ["in", "out", "inout"].includes(String(value.direction))
    && !["initiative", "kind", "custom_kind", "bus_width"].some(key => key in value)) value.family = "wire";
  if (value.family === "wire" && typeof value.range === "string") value.range = compactWireRange(value.range);
}

export function normalizeSpecOperations(input: unknown[], proposalId?: string, documentId?: string): Record<string, unknown>[] {
  const operations = normalizeSpecFormatting(input, documentId);
  const aliases = new Map<string, { id: string; kind: unknown }>();
  operations.forEach((operation, index) => {
    const generatedId = (field: string) => proposalId ? createHash("sha256").update(`${proposalId}:${index}:${field}`).digest("hex").slice(0, 32) : randomUUID().replaceAll("-", "");
    if (!isRecord(input[index]) || !input[index].operation_id) operation.operation_id = `operation_${index + 1}_${generatedId("operation")}`;
    if (operation.type !== "create_entity") return;
    const name = typeof operation.name === "string" ? operation.name.replace(/[^A-Za-z0-9_.-]+/g, "_") : "new";
    const entityId = `${operation.kind}_${name}_${generatedId("entity")}`;
    if (typeof operation.entity_id === "string") {
      if (aliases.has(operation.entity_id)) throw new Error(`Duplicate creation alias: ${operation.entity_id}`);
      aliases.set(operation.entity_id, { id: entityId, kind: operation.kind });
    }
    operation.entity_id = entityId;
  });
  const remap = (value: unknown): void => {
    if (Array.isArray(value)) { value.forEach(remap); return; }
    if (!isRecord(value)) return;
    if (typeof value.document_id === "string" && typeof value.entity_id === "string"
      && (documentId === undefined || value.document_id === documentId)) {
      const alias = aliases.get(value.entity_id);
      if (alias) {
        if (value.entity_kind !== alias.kind) throw new Error(`Creation alias ${value.entity_id} has a different entity kind.`);
        value.entity_id = alias.id;
      }
    }
    Object.values(value).forEach(remap);
  };
  operations.forEach(remap);
  return operations;
}

export function normalizeCircuitOperations(input: unknown[]): Record<string, unknown>[] {
  return input.map((item, index) => {
    if (!isRecord(item) || typeof item.type !== "string") {
      throw new Error(`Circuit operation ${index} must be an object with a type.`);
    }
    const operation = structuredClone(item);
    if (typeof operation.operation_id !== "string" || !operation.operation_id) {
      operation.operation_id = `operation_${index + 1}_${randomUUID().replaceAll("-", "")}`;
    }
    const component = isRecord(operation.component) ? operation.component : null;
    if (component && isRecord(component.appearance)) {
      component.appearance.properties = entriesToMap(component.appearance.properties);
    }
    const instance = isRecord(operation.instance) ? operation.instance : null;
    if (instance) instance.parameter_values = entriesToMap(instance.parameter_values);
    return operation;
  });
}
