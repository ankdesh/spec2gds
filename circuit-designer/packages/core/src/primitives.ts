import type {
  ComponentDefinition,
  ParameterDefinition,
  ParameterValue,
  TerminalDefinition,
} from "./types.generated";

export type PrimitiveTemplateKey =
  | "generic"
  | "buffer"
  | "not"
  | "and"
  | "nand"
  | "or"
  | "nor"
  | "xor"
  | "xnor"
  | "mux"
  | "register"
  | "constant"
  | "splitter"
  | "combiner";

export const primitiveTemplateKeys: PrimitiveTemplateKey[] = [
  "generic", "buffer", "not", "and", "nand", "or", "nor", "xor", "xnor",
  "mux", "register", "constant", "splitter", "combiner",
];

const positiveInteger = (value: ParameterValue | undefined, fallback: number): number =>
  typeof value === "number" && Number.isInteger(value) && value > 0 ? value : fallback;

function terminal(id: string, direction: "input" | "output", width: number): TerminalDefinition {
  return { id, label: id, direction, width, category: "port" };
}

function inputTerminals(count: number, width: number, prefix = "in"): TerminalDefinition[] {
  return Array.from({ length: count }, (_, index) => terminal(`${prefix}${index}`, "input", width));
}

function widthParameter(width: number): ParameterDefinition {
  return { id: "width", label: "Width", type: "number", default: width, minimum: 1 };
}

export function isPrimitiveTemplate(value: string): value is PrimitiveTemplateKey {
  return primitiveTemplateKeys.includes(value as PrimitiveTemplateKey);
}

export function createPrimitiveComponent(
  key: PrimitiveTemplateKey,
  id: string,
  label: string,
  parameters: Record<string, ParameterValue> = {},
): ComponentDefinition {
  const width = positiveInteger(parameters.width, 1);
  const inputCount = positiveInteger(parameters.input_count, key === "mux" ? 2 : 2);
  let terminals: TerminalDefinition[];
  let definitions: ParameterDefinition[] = [widthParameter(width)];
  if (key === "generic") terminals = [];
  else if (key === "buffer" || key === "not") terminals = [terminal("in", "input", width), terminal("out", "output", width)];
  else if (["and", "nand", "or", "nor", "xor", "xnor"].includes(key)) {
    terminals = [...inputTerminals(inputCount, width), terminal("out", "output", width)];
    definitions.push({ id: "input_count", label: "Input count", type: "number", default: inputCount, minimum: 2 });
  } else if (key === "mux") {
    const selectWidth = Math.max(1, Math.ceil(Math.log2(inputCount)));
    terminals = [...inputTerminals(inputCount, width, "data"), terminal("select", "input", selectWidth), terminal("out", "output", width)];
    definitions.push({ id: "input_count", label: "Input count", type: "number", default: inputCount, minimum: 2 });
  } else if (key === "register") {
    terminals = [
      terminal("clock", "input", 1),
      terminal("data", "input", width),
      terminal("enable", "input", 1),
      terminal("out", "output", width),
    ];
  } else if (key === "constant") {
    terminals = [terminal("out", "output", width)];
    definitions.push({ id: "value", label: "Value", type: "string", default: String(parameters.value ?? "0") });
  } else if (key === "splitter") {
    terminals = [terminal("in", "input", width), ...inputTerminals(inputCount, 1, "out").map((item) => ({ ...item, direction: "output" as const }))];
    definitions.push({ id: "output_count", label: "Output count", type: "number", default: inputCount, minimum: 2 });
  } else {
    terminals = [...inputTerminals(inputCount, 1), terminal("out", "output", width)];
    definitions.push({ id: "input_count", label: "Input count", type: "number", default: inputCount, minimum: 2 });
  }
  return {
    id,
    label,
    origin: "builtin",
    editable: false,
    terminals,
    parameters: definitions,
    appearance: { renderer_key: key, properties: {} },
  };
}

export function builtInPrimitiveCatalog(): ComponentDefinition[] {
  return primitiveTemplateKeys.map((key) => createPrimitiveComponent(key, `primitive_${key}`, key.replaceAll("_", " ")));
}
