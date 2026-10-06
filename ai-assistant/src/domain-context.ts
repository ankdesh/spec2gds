import { defaultInstructions, type InstructionBundle } from "./instructions.js";
/** Owner-specific prompt sections around immutable source identity and context.
 * Keep product instruction order separate from untrusted rendered owner content.
 * The prompt explains capabilities; native tool guards and owner validation
 * enforce them even when a model ignores those instructions. */
import type { PromptSection } from "@deepseek-ai/dsh-system-prompt";
import type { SessionBinding } from "./types.js";
import { isRecord } from "./types.js";

const json = (value: unknown, pretty = false): string => JSON.stringify(canonical(value), null, pretty ? 2 : 0);

type DomainPromptSection = Pick<PromptSection, "name" | "order"> & { readonly text: string };

export interface BoundPromptCatalog {
  bind(
    ref: { id: string; version: string },
    variables: Readonly<Record<string, string>>,
  ): { readonly sections: readonly { readonly id: string; readonly order: number; readonly text: string }[] };
}

export function promptSectionsFor(binding: SessionBinding, instructions: InstructionBundle = defaultInstructions): readonly DomainPromptSection[] {
  return catalogPromptSectionsFor(instructions, binding);
}

/** Bind the deployment catalog's exact service prompt bundle for one immutable target. */
export function catalogPromptSectionsFor(
  catalog: BoundPromptCatalog,
  binding: SessionBinding,
): readonly DomainPromptSection[] {
  const owner = binding.domain === "spec" ? "Spec service" : "Circuit service";
  const target = binding.scope === "entity"
    ? `${binding.entityKind ?? "entity"} ${binding.entityId ?? "(missing id)"}`
    : "the complete document";
  const bound = catalog.bind(
    { id: `spec2gds.${binding.domain}`, version: "1.0.0" },
    {
      "binding.owner": owner,
      "binding.document_id": binding.documentId,
      "binding.scope": binding.scope,
      "binding.target": target,
    },
  );
  const sections = bound.sections.map(section => ({
    name: `spec2gds:${section.id}`,
    order: section.order,
    text: section.text,
  }));
  const expected = ["domain-persona", "binding-context", "operation-constraints", "output-contract"];
  if (sections.length !== expected.length || sections.some((section, index) => section.name !== `spec2gds:${expected[index]}`)) {
    throw new Error(`Prompt bundle spec2gds.${binding.domain}@1.0.0 does not expose the required ordered sections.`);
  }
  return sections;
}

export function shapeBoundContext(binding: SessionBinding, context: Record<string, unknown>, svg?: string, instructions: InstructionBundle = defaultInstructions): { text: string; warnings: string[] } {
  return binding.domain === "spec" ? shapeSpecContext(binding, context, instructions) : shapeCircuitContext(context, svg, instructions);
}

function shapeSpecContext(binding: SessionBinding, value: Record<string, unknown>, instructions: InstructionBundle): { text: string; warnings: string[] } {
  const documentId = expectString(value.document_id, "Spec context document_id");
  const revision = expectString(value.source_revision_hash, "Spec context source_revision_hash");
  if (documentId !== binding.documentId) throw new Error("Spec service context does not match the bound document.");
  const scope = value.scope === "document" ? "document" : "entity";
  if (scope !== binding.scope) throw new Error("Spec service context scope does not match the conversation binding.");
  const diagnostics = Array.isArray(value.diagnostics) ? value.diagnostics.map(String) : [];
  if (scope === "document") {
    if (!isRecord(value.rendered_context) || value.rendered_context.document_id !== documentId || value.rendered_context.source_revision_hash !== revision || value.rendered_context.target !== null || typeof value.rendered_context.text !== "string") {
      throw new Error("Rendered document context identity does not match its binding.");
    }
    return { warnings: diagnostics, text: [
      `Spec document: ${documentId}`, `Source revision: ${revision}`, "Scope: complete specification",
      instructions.text("context.45"),
      instructions.text("context.46"),
      "WRITABLE CONTRACT:", json(value.writable ?? {}, true),
      "", value.rendered_context.text, "", "EXISTING REFERENCES (copy exact identities and VLNV values):", json(value.available_references ?? {}, true),
    ].join("\n") };
  }
  if (!isRecord(value.target) || !isRecord(value.writable) || !isRecord(value.read_only)) throw new Error("Entity Spec context is missing target or writable/read-only sections.");
  if (value.target.entity_id !== binding.entityId || value.target.entity_kind !== binding.entityKind) throw new Error("Spec service context target does not match the bound entity.");
  return { warnings: diagnostics, text: [
    `Spec document: ${documentId}`, `Source revision: ${revision}`,
    `Selected target: ${json(value.target)}`, "",
    "WRITABLE BOUNDARY (operations must stay inside these refs):", json(value.writable.entity_refs ?? [], true), "",
    "WRITABLE SEMANTIC IR:", json(value.writable.entity ?? null, true), "",
    "WRITABLE OWNED INTERNAL DESIGN:", json(value.writable.owned_internal_design ?? null, true), "",
    "WRITABLE RENDERED SECTIONS:", json(value.writable.sections ?? [], true), "",
    "WRITABLE LINKED NARRATIVE:", json(value.writable.linked_narrative ?? [], true), "",
    "READ-ONLY SURROUNDING CONTEXT (never target with operations):", json(value.read_only, true), "",
    "EXISTING REFERENCES ALLOWED IN TYPED OPERATIONS:", json(value.available_references ?? {}, true), "",
    instructions.text("context.47"),
    instructions.text("context.48"),
    instructions.text("context.49"),
    instructions.text("context.50"),
    instructions.text("context.51"),
    instructions.text("context.52"),
  ].join("\n") };
}

function shapeCircuitContext(snapshot: Record<string, unknown>, svg: string | undefined, instructions: InstructionBundle): { text: string; warnings: string[] } {
  const revision = expectString(snapshot.revision, "Circuit snapshot revision");
  if (!isRecord(snapshot.document)) throw new Error("Circuit snapshot is missing document.");
  const document = snapshot.document;
  const documentId = expectString(document.document_id, "Circuit document_id");
  const components = Array.isArray(document.components) ? document.components.filter(isRecord) : [];
  const design = isRecord(document.design) ? document.design : null;
  if (!design) throw new Error("Circuit document is missing design.");
  const instances = Array.isArray(design.instances) ? design.instances.filter(isRecord) : [];
  const terminals = Array.isArray(design.boundary_terminals) ? design.boundary_terminals.filter(isRecord) : [];
  const nets = Array.isArray(design.nets) ? design.nets.filter(isRecord) : [];
  const componentById = new Map(components.map(component => [String(component.id), component]));
  const lines = [
    `Circuit document: ${documentId}`, `Revision: ${revision}`, `Label: ${String(document.label ?? documentId)}`,
    `Design: ${String(design.id ?? "")} (${String(design.label ?? design.id ?? "")})`, "",
    "CIRCUIT OBJECT MODEL:",
    instructions.text("context.53"),
    instructions.text("context.54"),
    instructions.text("context.55"), "",
    "COMPONENT DEFINITIONS (copy the complete object when updating):",
  ];
  for (const component of components) {
    lines.push(`- ${String(component.id)}: ${String(component.label ?? "")} (origin=${String(component.origin)}, editable=${String(component.editable)})`);
    lines.push(`  complete definition: ${json(component)}`);
    if (isRecord(component.appearance) && isRecord(component.appearance.properties)) {
      const properties = Object.entries(component.appearance.properties).sort(([left], [right]) => left.localeCompare(right)).map(([name, value]) => ({ name, value }));
      lines.push(`  model-output appearance.properties: ${json(properties)}`);
    }
  }
  if (!components.length) lines.push(instructions.text("context.56"));
  lines.push("", "INSTANCES (copy complete object when updating):");
  for (const instance of instances) {
    lines.push(`- ${String(instance.id)}: ${json(instance)}`);
    if (isRecord(instance.parameter_values)) {
      const parameters = Object.entries(instance.parameter_values).sort(([left], [right]) => left.localeCompare(right)).map(([name, value]) => ({ name, value }));
      lines.push(`  model-output parameter_values: ${json(parameters)}`);
    }
  }
  if (!instances.length) lines.push(instructions.text("context.56"));
  lines.push("", "BOUNDARY TERMINALS / TOP-LEVEL PORTS:");
  for (const terminal of terminals) lines.push(`- ${String(terminal.id)}: ${json(terminal)}`);
  if (!terminals.length) lines.push(instructions.text("context.56"));
  lines.push("", "NETS AND ENDPOINTS:");
  for (const net of nets) lines.push(`- ${String(net.id)}: ${json(net)}`);
  if (!nets.length) lines.push(instructions.text("context.56"));
  lines.push("", "VALID ENDPOINT CATALOG (use only these exact existing IDs):");
  let endpointCount = 0;
  for (const instance of instances) {
    const component = componentById.get(String(instance.component_id));
    const componentTerminals = component && Array.isArray(component.terminals) ? component.terminals.filter(isRecord) : [];
    for (const terminal of componentTerminals) {
      endpointCount += 1;
      lines.push(`- ${String(instance.id)}.${String(terminal.id)} direction=${String(terminal.direction)} width=${String(terminal.width)} payload=${json({ kind: "instance", instance_id: instance.id, terminal_id: terminal.id, slice: null })}`);
    }
  }
  for (const terminal of terminals) {
    endpointCount += 1;
    lines.push(`- boundary ${String(terminal.id)} direction=${String(terminal.direction)} width=${String(terminal.width)} payload=${json({ kind: "boundary", terminal_id: terminal.id, slice: null })}`);
  }
  if (!endpointCount) lines.push(instructions.text("context.57"));
  lines.push("", "SEMANTIC EDITING FACTS:",
    instructions.text("context.58"),
    instructions.text("context.59"),
    instructions.text("context.60"),
    instructions.text("context.61"),
    instructions.text("context.62"),
    instructions.text("context.63"));
  const warnings: string[] = [];
  lines.push("", "CIRCUIT DESIGNER SVG:");
  if (svg) {
    const root = svg.match(/<svg\b([^>]*)>/i)?.[1] ?? "";
    const attribute = (name: string): string => root.match(new RegExp(`${name}=["']([^"']*)["']`, "i"))?.[1] ?? "unspecified";
    const instances = [...svg.matchAll(/data-instance-id=["']([^"']+)["']/gi)].map(match => match[1]!).filter((item, index, values) => values.indexOf(item) === index).sort();
    const svgNets = [...svg.matchAll(/data-net-id=["']([^"']+)["']/gi)].map(match => match[1]!).filter((item, index, values) => values.indexOf(item) === index).sort();
    lines.push(`- rendered SVG viewBox=${attribute("viewBox")}, width=${attribute("width")}, height=${attribute("height")}`);
    lines.push(`- instance ids=${json(instances)}; net ids=${json(svgNets)}`);
    lines.push(instructions.text("context.64"));
  } else {
    warnings.push("Circuit SVG export was unavailable.");
    lines.push(instructions.text("context.65"));
  }
  return { text: lines.join("\n"), warnings };
}

function expectString(value: unknown, name: string): string {
  if (typeof value !== "string" || !value) throw new Error(`${name} is required.`);
  return value;
}

function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  if (!isRecord(value)) return value;
  return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
}
