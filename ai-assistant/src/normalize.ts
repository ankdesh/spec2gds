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
  return bracketed ? bracketed[1]!.trim() : value;
}

/** Clean model-generated SystemVerilog into body-only text without fences or module wrappers. */
export function cleanSystemVerilogBody(value: unknown): unknown {
  if (typeof value !== "string") return value;
  let text = value.trim();

  // Strip markdown code fences e.g. ```verilog ... ``` or ```systemverilog ... ``` or ```
  const fenceMatch = /^```(?:verilog|systemverilog|v|sv)?\s*\r?\n([\s\S]*?)\r?\n```\s*$/i.exec(text);
  if (fenceMatch) {
    text = fenceMatch[1]!.trim();
  }

  // If the model wrapped code in module ... endmodule, extract the inner body
  const moduleMatch = /^\s*module\s+[A-Za-z0-9_]+(?:\s*#\s*\([\s\S]*?\))?\s*(?:\([\s\S]*?\))?\s*;([\s\S]*?)\bendmodule\s*$/i.exec(text);
  if (moduleMatch) {
    text = moduleMatch[1]!.trim();
  }

  // Strip user `include or user `line directives that the backend forbids
  text = text.replace(/^\s*`(?:include|line)\b.*$/gm, "").trim();

  return text;
}

export function normalizeSpecOperations(input: unknown[]): Record<string, unknown>[] {
  return input.map((item, index) => {
    if (!isRecord(item) || typeof item.type !== "string") {
      throw new Error(`Spec operation ${index} must be an object with a type.`);
    }
    const operation = structuredClone(item);
    if (typeof operation.operation_id !== "string" || !operation.operation_id) {
      operation.operation_id = `operation_${index + 1}_${createHash("sha256").update(JSON.stringify(item)).digest("hex").slice(0, 16)}`;
    }
    if (operation.type === "create_entity") {
      const kind = typeof operation.kind === "string" ? operation.kind : "entity";
      const name = typeof operation.name === "string" ? operation.name.replace(/[^A-Za-z0-9_.-]+/g, "_") : "new";
      if (typeof operation.systemverilog === "string") {
        operation.systemverilog = cleanSystemVerilogBody(operation.systemverilog);
      }
      const expectedPrefix = `${kind}_${name}`;
      if (typeof operation.entity_id === "string" && (operation.entity_id === expectedPrefix || operation.entity_id.startsWith(`${expectedPrefix}_`))) {
        // preserve caller or fixture-provided identifier with matching prefix
      } else {
        const signature = createHash("sha256").update(JSON.stringify({ kind, name, ports: operation.ports, instances: operation.instances, sv: operation.systemverilog })).digest("hex").slice(0, 16);
        operation.entity_id = `${expectedPrefix}_${signature}`;
      }
      if (kind === "component") {
        operation.instances = [];
      } else if (operation.instances === undefined) {
        operation.instances = [];
      }
      if (kind === "component" && Array.isArray(operation.ports)) {
        for (const port of operation.ports) {
          if (isRecord(port)) {
            if (!port.family || typeof port.family !== "string") {
              port.family = "wire";
            }
            if (port.family === "wire" && typeof port.range === "string") {
              port.range = compactWireRange(port.range);
            }
          }
        }
      }
    }
    if (operation.type === "upsert_component_port" && isRecord(operation.port)) {
      if (!operation.port.family || typeof operation.port.family !== "string") {
        operation.port.family = "wire";
      }
      if (operation.port.family === "wire" && typeof operation.port.range === "string") {
        operation.port.range = compactWireRange(operation.port.range);
      }
    }
    if (operation.type === "upsert_entity_section" && operation.section_type === "sv" && isRecord(operation.payload) && typeof operation.payload.content === "string") {
      operation.payload.content = cleanSystemVerilogBody(operation.payload.content);
    }
    if (operation.type === "set_entity_metadata" && Array.isArray(operation.clear_fields)) {
      for (const field of operation.clear_fields) if (typeof field === "string") operation[field] = null;
      delete operation.clear_fields;
    }
    if (operation.type === "update_bus_definition" && isRecord(operation.properties)) {
      const properties = operation.properties;
      if (Array.isArray(properties.clear_fields)) {
        for (const field of properties.clear_fields) if (typeof field === "string") properties[field] = null;
        delete properties.clear_fields;
      }
    }
    if (operation.type === "upsert_narrative_block") normalizeNarrativeBlock(operation.block);
    return operation;
  });
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
