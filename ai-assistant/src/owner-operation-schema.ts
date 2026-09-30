import type { ValueSchemaSpec } from "@deepseek-ai/dsh-tools";

type Node = Record<string, unknown>;

export class OwnerContractError extends Error {
  constructor(message: string) { super(message); this.name = "OwnerContractError"; }
}

export interface OwnerOperationContract {
  schema_version: 1;
  digest: string;
  operation_schema: Node;
  tool_schema: ValueSchemaSpec;
}

function object(value: unknown): value is Node {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function resolved(node: Node, defs: Node, depth = 0): Node {
  if (depth > 32) throw new Error("Owner operation schema is too deeply nested.");
  if (typeof node.$ref !== "string") return node;
  if (!node.$ref.startsWith("#/$defs/")) throw new Error("Owner schema has a non-local reference.");
  const target = defs[node.$ref.slice("#/$defs/".length)];
  if (!object(target)) throw new Error("Owner schema has an unknown reference.");
  return resolved(target, defs, depth + 1);
}

function flattened(node: Node, defs: Node): Node {
  const current = resolved(node, defs);
  if (!Array.isArray(current.allOf)) return current;
  const pieces = current.allOf.map(piece => {
    if (!object(piece)) throw new Error("Owner schema has an invalid allOf branch.");
    return flattened(piece, defs);
  });
  if (!pieces.every(piece => piece.type === "object")
    || pieces.some(piece => object(piece.additionalProperties))) throw new Error("Owner schema has unsupported allOf.");
  const allProperties = Object.assign({}, ...pieces.map(piece => piece.properties ?? {})) as Node;
  if (pieces.some(piece => piece.additionalProperties === false
    && Object.keys(allProperties).some(name => !object(piece.properties) || !(name in piece.properties)))) {
    throw new Error("Owner schema has an allOf object whose closed branch excludes sibling properties.");
  }
  return {
    type: "object",
    properties: allProperties,
    required: [...new Set(pieces.flatMap(piece => Array.isArray(piece.required) ? piece.required : []))],
    additionalProperties: pieces.some(piece => piece.additionalProperties === false) ? false : true,
  };
}

const supported = new Set([
  "$schema", "$defs", "$ref", "type", "oneOf", "allOf", "properties", "required", "additionalProperties",
  "items", "const", "enum", "description", "title", "default", "minLength", "pattern",
  "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "minItems", "uniqueItems",
]);

function assertKeywords(node: Node): void {
  for (const key of Object.keys(node)) if (!supported.has(key)) throw new Error(`Unsupported owner schema keyword: ${key}`);
}

function toolSchema(node: Node, defs: Node, depth = 0): ValueSchemaSpec {
  if (depth > 32) throw new Error("Owner operation schema is too deeply nested.");
  const current = flattened(node, defs);
  assertKeywords(current);
  if (Array.isArray(current.oneOf)) {
    const branches = current.oneOf.map(item => {
      if (!object(item)) throw new Error("Invalid owner schema union.");
      return toolSchema(item, defs, depth + 1);
    });
    if (branches.length === 1) return branches[0]!;
    if (branches.length < 2) throw new Error("Owner operation schema has no choices.");
    return { oneOf: branches as [ValueSchemaSpec, ValueSchemaSpec, ...ValueSchemaSpec[]] };
  }
  if (Array.isArray(current.type)) {
    const branches = current.type.map(type => toolSchema({ ...current, type }, defs, depth + 1));
    return { oneOf: branches as [ValueSchemaSpec, ValueSchemaSpec, ...ValueSchemaSpec[]] };
  }
  if (!current.type && current.const !== undefined) {
    const inferred = current.const === null ? "null" : typeof current.const;
    return toolSchema({ ...current, type: inferred }, defs, depth + 1);
  }
  if (!current.type && Array.isArray(current.enum) && current.enum.length) {
    const inferred = current.enum[0] === null ? "null" : typeof current.enum[0];
    if (current.enum.every(value => (value === null ? "null" : typeof value) === inferred)) {
      return toolSchema({ ...current, type: inferred }, defs, depth + 1);
    }
  }
  if (!current.type) return { type: "json" };
  if (current.type === "object") {
    const rawProperties = current.properties === undefined ? {} : current.properties;
    if (!object(rawProperties)) throw new Error("Invalid owner object schema.");
    if (object(current.additionalProperties)) {
      toolSchema(current.additionalProperties, defs, depth + 1);
      for (const value of Object.values(rawProperties)) {
        if (!object(value)) throw new Error("Invalid owner property schema.");
        toolSchema(value, defs, depth + 1);
      }
      return { type: "json" };
    }
    const required = new Set(Array.isArray(current.required) ? current.required : []);
    const properties: Record<string, ValueSchemaSpec & { required?: true }> = {};
    for (const [name, value] of Object.entries(rawProperties)) {
      if (!object(value)) throw new Error("Invalid owner property schema.");
      properties[name] = { ...toolSchema(value, defs, depth + 1), ...(required.has(name) ? { required: true as const } : {}) };
    }
    return { type: "object", properties, additionalProperties: current.additionalProperties !== false };
  }
  if (current.type === "array") {
    if (!object(current.items)) throw new Error("Owner array schema has no items.");
    return { type: "array", items: toolSchema(current.items, defs, depth + 1) };
  }
  if (["string", "number", "integer", "boolean", "null"].includes(String(current.type))) {
    return { type: current.type, ...(current.enum ? { enum: current.enum } : {}), ...(current.const !== undefined ? { const: current.const } : {}) } as ValueSchemaSpec;
  }
  throw new Error(`Unsupported owner schema type: ${String(current.type)}`);
}

export function parseOwnerOperationContract(value: unknown): OwnerOperationContract {
  if (!object(value) || value.schema_version !== 1 || typeof value.digest !== "string"
    || !/^sha256:[a-f0-9]{64}$/.test(value.digest) || !object(value.operation_schema)) {
    throw new Error("Owner returned an invalid operation schema contract.");
  }
  const schema = value.operation_schema;
  if (schema.$schema !== "https://json-schema.org/draft/2020-12/schema") throw new Error("Owner operation schema must use JSON Schema 2020-12.");
  const defs = object(schema.$defs) ? schema.$defs : {};
  return { schema_version: 1, digest: value.digest, operation_schema: schema, tool_schema: toolSchema(schema, defs) };
}

function equal(a: unknown, b: unknown): boolean { return JSON.stringify(a) === JSON.stringify(b); }

function matches(input: unknown, node: Node, defs: Node, depth = 0): boolean {
  if (depth > 32) return false;
  const schema = flattened(node, defs);
  if (Array.isArray(schema.oneOf)) return schema.oneOf.filter(item => object(item) && matches(input, item, defs, depth + 1)).length === 1;
  if (Array.isArray(schema.type)) return schema.type.some(type => matches(input, { ...schema, type }, defs, depth + 1));
  if (schema.const !== undefined && !equal(input, schema.const)) return false;
  if (Array.isArray(schema.enum) && !schema.enum.some(value => equal(value, input))) return false;
  switch (schema.type) {
    case "object": {
      if (!object(input)) return false;
      const properties = object(schema.properties) ? schema.properties : {};
      if (Array.isArray(schema.required) && schema.required.some(key => typeof key === "string" && !(key in input))) return false;
      if (schema.additionalProperties === false && Object.keys(input).some(key => !(key in properties))) return false;
      return Object.entries(input).every(([key, value]) => key in properties
        ? object(properties[key]) && matches(value, properties[key], defs, depth + 1)
        : !object(schema.additionalProperties) || matches(value, schema.additionalProperties, defs, depth + 1));
    }
    case "array":
      return Array.isArray(input) && (!schema.minItems || input.length >= Number(schema.minItems))
        && (!schema.uniqueItems || new Set(input.map(item => JSON.stringify(item))).size === input.length)
        && input.every(item => object(schema.items) && matches(item, schema.items, defs, depth + 1));
    case "string":
      return typeof input === "string" && (!schema.minLength || input.length >= Number(schema.minLength))
        && (!schema.pattern || new RegExp(String(schema.pattern)).test(input));
    case "integer":
    case "number":
      return typeof input === "number" && Number.isFinite(input) && (schema.type !== "integer" || Number.isInteger(input))
        && (schema.minimum === undefined || input >= Number(schema.minimum))
        && (schema.maximum === undefined || input <= Number(schema.maximum))
        && (schema.exclusiveMinimum === undefined || input > Number(schema.exclusiveMinimum))
        && (schema.exclusiveMaximum === undefined || input < Number(schema.exclusiveMaximum));
    case "boolean": return typeof input === "boolean";
    case "null": return input === null;
    default: return true;
  }
}

export function validateOwnerOperations(contract: OwnerOperationContract, operations: unknown[]): void {
  const defs = object(contract.operation_schema.$defs) ? contract.operation_schema.$defs : {};
  for (const [index, operation] of operations.entries()) {
    if (!matches(operation, contract.operation_schema, defs)) {
      throw new Error(`Operation ${index + 1} does not match the owner's published schema.`);
    }
  }
}

export function verifyOwnerOperationContract(current: OwnerOperationContract, latest: unknown): void {
  let refreshed: OwnerOperationContract;
  try { refreshed = parseOwnerOperationContract(latest); }
  catch (error) { throw new OwnerContractError(error instanceof Error ? error.message : String(error)); }
  if (refreshed.digest !== current.digest) {
    throw new OwnerContractError("The owner operation schema changed. Read get_bound_context again to refresh proposal tools in this conversation.");
  }
}
