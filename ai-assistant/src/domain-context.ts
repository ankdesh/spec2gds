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

const SPEC_PERSONA = `DOMAIN PERSONA
You are a hardware specification design partner. Explore the user's idea using immutable semantic specification context. Explain concrete implications, alternatives, and open assumptions. Create a formal operation proposal only when the user asks for a concrete change.`;

const CIRCUIT_PERSONA = `DOMAIN PERSONA
You are a Circuit Designer editing planner. Discuss the existing logical circuit and prepare safe, reviewable operations only when the user requests a concrete change.`;

const SPEC_OPERATION_CONSTRAINTS = `OPERATION CONSTRAINTS
For proposals, stay strictly inside the WRITABLE BOUNDARY; surrounding and shared context is read-only. Reuse exact entity IDs, VLNV values, instance names, interface names, port names, and narrative block IDs. Never change vendor/library/name/version or edit assets. Proposal operations must not create or delete a top-level source document; new contentful packages require an approved architecture review before the creation card. Explicitly empty packages can use empty=true.

Document scope supports the owner-published editing vocabulary throughout its bound package, including refining existing entities, ports, parameters, sections, instances, connections, and narratives. Entity scope retains its narrower writable boundary. A component creation uses kind=component and instances=[]. Creation entity IDs are proposal-local aliases; dependent references and narrative links must use those aliases with full document/entity-kind references. New components need set_entity_metadata.description in the same proposal. Designs use entry_design=false for internal composition; the default true preserves entry designs. Numeric endpoint slices use {lsb,width}; unsliced boundary endpoints can remain strings. Parameterized RTL generation is deferred; use concrete approved widths and depths. Design instances need unique names and exact component_vlnv references. Wire port ranges use compact text such as 2:0, without square brackets; omit the range for scalar ports. Copy the revision read by get_bound_context into the required base_source_revision_hash; reread context after stale diagnostics. Valid Spec submissions are applied and saved automatically when approval_policy is automatic; record defaults as assumptions and ask only for genuinely missing input. Report the saved revision returned by the tool. With approval_policy=review, prepare a pending proposal for explicit approval.

Entity scope mappings: on a component, add a port means upsert_component_port; on a design, add a component means upsert_instance using an existing component_vlnv; connect ports means upsert_connection. Physical wiring is kind=ad_hoc with port_endpoints and external_ports only. Bus-interface wiring is kind=interface with interface_endpoints and hierarchy_interfaces only. Connections require at least two compatible endpoints. If context lacks compatible named endpoints, return supported=false.

Replacement values are complete: preserve unchanged component ports, interfaces, instances, connections, bus-definition properties, and SystemVerilog sections. Port name/family are immutable; ports on components owning internal designs are read-only. Nullable fields not changing remain null; clear metadata or bus fields only through clear_fields. SystemVerilog content is module-body text only, with no module/endmodule, include, or line directive. Narrative options are {key,value} entries.`;

const CIRCUIT_OPERATION_CONSTRAINTS = `OPERATION CONSTRAINTS
Intent mapping: create a component type/definition -> add_component; place a component -> add_instance using an existing component_id; add a pin -> update_component with the complete current definition plus the terminal; add a top-level port -> add_boundary_terminal; connect A to B -> create_net with all endpoints, or connect_endpoint for an existing net.

New components are local and editable. Updates are complete replacements. Use cascade=false unless the user explicitly requests dependent instances/connections be removed. Instance parameter_values and appearance properties use {name,value} lists in model output. Endpoints are exactly an instance or boundary endpoint with slice=null, unless the user explicitly requests a numeric {lsb,width} subrange. Use only IDs in the VALID ENDPOINT CATALOG or IDs introduced by an earlier operation in the same proposal. Order dependent operations and prefer the fewest atomic operations.

Never author geometry, routes, labels, or layout. Reuse exact IDs for existing objects and unique lowercase slug-like IDs for new objects. Do not invent terminal or component IDs.`;

const SPEC_OUTPUT_CONTRACT = `OUTPUT CONTRACT
Do not emit XML or claim that a change was applied without an applied owner receipt. Report the actual saved revision for automatic submissions; pending reviews still require explicit approval. List every material assumption. If a change is outside the typed vocabulary or writable boundary, return supported=false with an empty operations list and a concise reason.`;

const CIRCUIT_OUTPUT_CONTRACT = `OUTPUT CONTRACT
Never claim a proposal was applied or sent. List every material assumption. If the request is unsupported, return supported=false with an empty operations list and a concise unsupported_reason.`;

function bindingContext(binding: SessionBinding): string {
  const owner = binding.domain === "spec" ? "Spec Editor" : "Circuit Designer";
  const target = binding.scope === "entity"
    ? `${binding.entityKind ?? "entity"} ${binding.entityId ?? "(missing id)"}`
    : "the complete document";
  return `BOUND CONVERSATION
- Owner: ${owner}
- Document ID: ${binding.documentId}
- Scope: ${binding.scope}
- Selected target: ${target}

This binding is immutable for the lifetime of the conversation. References such as "this document", "this component", "the design", or "the components" mean the bound target above. Never ask the user which document or design they mean.

Explicit requests to create a separate specification package use prepare_spec_document_creation when available, after approval of an architecture review. This creates a new document chat and preserves this binding. A creation receipt means the new package already exists; fulfill its requested contents without creating another package.

For every message about the current specification or circuit, you MUST call get_bound_context before answering, including explanation, description, comparison, and change requests. Do not rely on a previous turn's context because owner revisions can change. Answer only after the tool returns. If the context read fails, explain that the bound owner is unavailable instead of asking the user to restate the design.`;
}

export function promptSectionsFor(binding: SessionBinding): readonly DomainPromptSection[] {
  const spec = binding.domain === "spec";
  return [
    { name: "spec2gds:domain-persona", order: 100, text: spec ? SPEC_PERSONA : CIRCUIT_PERSONA },
    { name: "spec2gds:binding-context", order: 150, text: bindingContext(binding) },
    { name: "spec2gds:operation-constraints", order: 200, text: spec ? SPEC_OPERATION_CONSTRAINTS : CIRCUIT_OPERATION_CONSTRAINTS },
    { name: "spec2gds:output-contract", order: 300, text: spec ? SPEC_OUTPUT_CONTRACT : CIRCUIT_OUTPUT_CONTRACT },
  ];
}

/** Bind the deployment catalog's exact service prompt bundle for one immutable target. */
export function catalogPromptSectionsFor(
  catalog: BoundPromptCatalog,
  binding: SessionBinding,
): readonly DomainPromptSection[] {
  const owner = binding.domain === "spec" ? "Spec Editor" : "Circuit Designer";
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

export function shapeBoundContext(binding: SessionBinding, context: Record<string, unknown>, svg?: string): { text: string; warnings: string[] } {
  return binding.domain === "spec" ? shapeSpecContext(binding, context) : shapeCircuitContext(context, svg);
}

function shapeSpecContext(binding: SessionBinding, value: Record<string, unknown>): { text: string; warnings: string[] } {
  const documentId = expectString(value.document_id, "Spec context document_id");
  const revision = expectString(value.source_revision_hash, "Spec context source_revision_hash");
  if (documentId !== binding.documentId) throw new Error("Spec owner context does not match the bound document.");
  const scope = value.scope === "document" ? "document" : "entity";
  if (scope !== binding.scope) throw new Error("Spec owner context scope does not match the conversation binding.");
  const diagnostics = Array.isArray(value.diagnostics) ? value.diagnostics.map(String) : [];
  if (scope === "document") {
    if (!isRecord(value.rendered_context) || value.rendered_context.document_id !== documentId || value.rendered_context.source_revision_hash !== revision || value.rendered_context.target !== null || typeof value.rendered_context.text !== "string") {
      throw new Error("Rendered document context identity does not match its binding.");
    }
    return { warnings: diagnostics, text: [
      `Spec document: ${documentId}`, `Source revision: ${revision}`, "Scope: complete specification",
      "WRITABLE BOUNDARY: supported operations throughout this bound package. Composite boundary ports and assets remain protected.",
      "Refine existing entities using exact identities and VLNV references. Copy the authored revision into every proposal.",
      "WRITABLE CONTRACT:", json(value.writable ?? {}, true),
      "", value.rendered_context.text, "", "EXISTING REFERENCES (copy exact identities and VLNV values):", json(value.available_references ?? {}, true),
    ].join("\n") };
  }
  if (!isRecord(value.target) || !isRecord(value.writable) || !isRecord(value.read_only)) throw new Error("Entity Spec context is missing target or writable/read-only sections.");
  if (value.target.entity_id !== binding.entityId || value.target.entity_kind !== binding.entityKind) throw new Error("Spec owner context target does not match the bound entity.");
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
    "PLAIN-LANGUAGE TASK MAPPING:",
    "- Component add port -> upsert_component_port.",
    "- Design add component -> upsert_instance using an available component reference.",
    "- Design connect ports/nets -> upsert_connection; physical wires use kind=ad_hoc.",
    "- Use only listed port/interface names; never invent endpoints.",
    "- Creating a top-level component/design requires document scope.",
  ].join("\n") };
}

function shapeCircuitContext(snapshot: Record<string, unknown>, svg?: string): { text: string; warnings: string[] } {
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
    "- A component definition is a reusable type; an instance is one placed use.",
    "- A component terminal is a pin on each instance; a boundary terminal is a top-level port.",
    "- A net connects instance terminals and/or boundary terminals.", "",
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
  if (!components.length) lines.push("- (none)");
  lines.push("", "INSTANCES (copy complete object when updating):");
  for (const instance of instances) {
    lines.push(`- ${String(instance.id)}: ${json(instance)}`);
    if (isRecord(instance.parameter_values)) {
      const parameters = Object.entries(instance.parameter_values).sort(([left], [right]) => left.localeCompare(right)).map(([name, value]) => ({ name, value }));
      lines.push(`  model-output parameter_values: ${json(parameters)}`);
    }
  }
  if (!instances.length) lines.push("- (none)");
  lines.push("", "BOUNDARY TERMINALS / TOP-LEVEL PORTS:");
  for (const terminal of terminals) lines.push(`- ${String(terminal.id)}: ${json(terminal)}`);
  if (!terminals.length) lines.push("- (none)");
  lines.push("", "NETS AND ENDPOINTS:");
  for (const net of nets) lines.push(`- ${String(net.id)}: ${json(net)}`);
  if (!nets.length) lines.push("- (none)");
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
  if (!endpointCount) lines.push("- (none; add a terminal first)");
  lines.push("", "SEMANTIC EDITING FACTS:",
    "- Existing IDs are authoritative; new IDs must be unique lowercase slugs.",
    "- Adding a definition does not place it; add_instance places one use.",
    "- Adding a component pin uses update_component with the full definition.",
    "- parameter_values and appearance.properties are {name,value} lists in model output.",
    "- Whole-terminal endpoint slice is null; numeric slices use {lsb,width}.",
    "- Boundary input is a source into the design.");
  const warnings: string[] = [];
  lines.push("", "CIRCUIT DESIGNER SVG:");
  if (svg) {
    const root = svg.match(/<svg\b([^>]*)>/i)?.[1] ?? "";
    const attribute = (name: string): string => root.match(new RegExp(`${name}=["']([^"']*)["']`, "i"))?.[1] ?? "unspecified";
    const instances = [...svg.matchAll(/data-instance-id=["']([^"']+)["']/gi)].map(match => match[1]!).filter((item, index, values) => values.indexOf(item) === index).sort();
    const svgNets = [...svg.matchAll(/data-net-id=["']([^"']+)["']/gi)].map(match => match[1]!).filter((item, index, values) => values.indexOf(item) === index).sort();
    lines.push(`- rendered SVG viewBox=${attribute("viewBox")}, width=${attribute("width")}, height=${attribute("height")}`);
    lines.push(`- instance ids=${json(instances)}; net ids=${json(svgNets)}`);
    lines.push("- SVG is a visual aid; the semantic circuit document is authoritative.");
  } else {
    warnings.push("Circuit SVG export was unavailable.");
    lines.push("- no SVG rendering was supplied");
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
