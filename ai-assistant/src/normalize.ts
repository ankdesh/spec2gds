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

export function normalizeSpecOperations(input: unknown[], proposalId?: string): Record<string, unknown>[] {
  return input.map((item, index) => {
    if (!isRecord(item) || typeof item.type !== "string") {
      throw new Error(`Spec operation ${index} must be an object with a type.`);
    }
    const operation = structuredClone(item);
    const generatedId = (field: string) => proposalId ? createHash("sha256").update(`${proposalId}:${index}:${field}`).digest("hex").slice(0, 32) : randomUUID().replaceAll("-", "");
    if (typeof operation.operation_id !== "string" || !operation.operation_id) {
      operation.operation_id = `operation_${index + 1}_${generatedId("operation")}`;
    }
    if (operation.type === "create_entity") {
      const kind = typeof operation.kind === "string" ? operation.kind : "entity";
      const name = typeof operation.name === "string" ? operation.name.replace(/[^A-Za-z0-9_.-]+/g, "_") : "new";
      operation.entity_id = `${kind}_${name}_${generatedId("entity")}`;
      if (operation.instances === undefined) operation.instances = [];
      if (kind === "component" && Array.isArray(operation.ports)) {
        for (const port of operation.ports) {
          if (isRecord(port) && port.family === "wire" && typeof port.range === "string") {
            port.range = compactWireRange(port.range);
          }
        }
      }
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
