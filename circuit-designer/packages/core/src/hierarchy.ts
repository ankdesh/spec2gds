import type {
  CircuitDocument,
  ComponentDefinition,
  Diagnostic,
  ProviderCommitRequest,
  ProviderCommitResult,
  ResolvedComponentDesign,
} from "./types.generated";
import type { ComponentDesignProvider } from "./backend";

export function validateComponentDesignBoundary(
  component: ComponentDefinition,
  child: CircuitDocument,
): Diagnostic[] {
  const diagnostics: Diagnostic[] = [];
  const expected = new Map(component.terminals.map((terminal) => [terminal.id, terminal]));
  const actual = new Map(child.design.boundary_terminals.map((terminal) => [terminal.id, terminal]));
  for (const [id, terminal] of expected) {
    const boundary = actual.get(id);
    if (!boundary) {
      diagnostics.push({
        severity: "error",
        code: "missing_child_boundary",
        message: `Child design is missing boundary terminal ${id}.`,
        element_key: component.id,
      });
      continue;
    }
    if (boundary.direction !== terminal.direction || boundary.width !== terminal.width) {
      diagnostics.push({
        severity: "error",
        code: "incompatible_child_boundary",
        message: `Child boundary ${id} does not match direction and width of component ${component.id}.`,
        element_key: component.id,
      });
    }
  }
  for (const id of actual.keys()) {
    if (!expected.has(id)) {
      diagnostics.push({
        severity: "error",
        code: "unexpected_child_boundary",
        message: `Child design has boundary terminal ${id} that is not present on component ${component.id}.`,
        element_key: component.id,
      });
    }
  }
  return diagnostics;
}

export async function resolveHierarchy(
  provider: ComponentDesignProvider,
  parent: CircuitDocument,
  component: ComponentDefinition,
  ancestry: string[] = [],
): Promise<{ result: ResolvedComponentDesign; diagnostics: Diagnostic[] }> {
  if (ancestry.includes(component.id)) {
    return {
      result: { status: "unavailable", message: `Hierarchy cycle: ${[...ancestry, component.id].join(" -> ")}` },
      diagnostics: [{
        severity: "error",
        code: "hierarchy_cycle",
        message: `Resolving ${component.id} would create a hierarchy cycle.`,
        element_key: component.id,
      }],
    };
  }
  const result = await provider.resolveComponentDesign(component, {
    parent_document_id: parent.document_id,
    ancestry,
  });
  if (result.status !== "available" || !result.document) return { result, diagnostics: [] };
  const diagnostics = validateComponentDesignBoundary(component, result.document);
  const childComponentIds = new Set(result.document.design.instances.map((instance) => instance.component_id));
  const cycleIds = [...ancestry, component.id].filter((id) => childComponentIds.has(id));
  if (cycleIds.length) {
    diagnostics.push({
      severity: "error",
      code: "hierarchy_cycle",
      message: `Child design for ${component.id} instantiates hierarchy ancestor ${cycleIds[0]}.`,
      element_key: component.id,
    });
  }
  return {
    result: diagnostics.some((item) => item.severity === "error")
      ? { status: "unavailable", message: "Provider child boundary is incompatible." }
      : result,
    diagnostics,
  };
}

export async function commitProviderDocument(
  provider: ComponentDesignProvider,
  request: ProviderCommitRequest,
): Promise<ProviderCommitResult> {
  if (!provider.commitComponentDesign) {
    return {
      accepted: false,
      provider_revision: request.base_provider_revision,
      diagnostics: [{
        severity: "error",
        code: "provider_read_only",
        message: "The component design provider is read-only.",
        element_key: request.component.id,
      }],
    };
  }
  const result = await provider.commitComponentDesign(request);
  if (result.accepted && result.document) {
    const boundaryDiagnostics = validateComponentDesignBoundary(request.component, result.document);
    if (boundaryDiagnostics.some((item) => item.severity === "error")) {
      return {
        accepted: false,
        provider_revision: result.provider_revision,
        diagnostics: [...result.diagnostics, ...boundaryDiagnostics],
      };
    }
  }
  return result;
}
