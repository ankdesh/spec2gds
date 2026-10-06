/** Durable architecture approval is separate from the service content policy. */

import { defaultInstructions } from "./instructions.js";
import { isRecord } from "./types.js";

/** Bind creation to the names and concrete interfaces the human reviewed. */
export function validateArchitectureOperations(plan: Record<string, any>, operations: readonly unknown[]): void {
  for (const operation of operations) {
    if (!isRecord(operation) || operation.type !== "create_entity" || !["component", "design"].includes(String(operation.kind))) continue;
    const entities = operation.kind === "component" ? plan.components : plan.designs;
    const approved = entities.find((entity: unknown) => isRecord(entity) && entity.name === operation.name);
    if (!approved) throw new Error(`Creation of ${String(operation.kind)} ${String(operation.name)} was not included in the approved architecture. Prepare a revised architecture review.`);
    if (operation.kind !== "component") continue;
    const grouped = plan.interfaces.find((item: unknown) => isRecord(item) && item.component === operation.name && Array.isArray(item.ports));
    const expected = grouped?.ports ?? (plan.components.length === 1 && plan.interfaces.every((item: unknown) => isRecord(item) && typeof item.name === "string") ? plan.interfaces : null);
    if (!expected) continue;
    const ports = Array.isArray(operation.ports) ? operation.ports : [];
    if (ports.length !== expected.length) throw new Error(`Component ${String(operation.name)} ports differ from its approved interface.`);
    for (const descriptor of expected) {
      if (!isRecord(descriptor) || typeof descriptor.name !== "string") throw new Error("Approved port descriptors require names.");
      const port = ports.find(item => isRecord(item) && item.name === descriptor.name);
      if (!isRecord(port) || (descriptor.direction !== undefined && descriptor.direction !== port.direction)) throw new Error(`Port ${String(operation.name)}.${descriptor.name} differs from its approved interface.`);
      if (descriptor.width !== undefined) {
        const range = typeof port.range === "string" ? /^(\d+):(\d+)$/.exec(port.range) : null;
        const width = range ? Math.abs(Number(range[1]) - Number(range[2])) + 1 : port.range === undefined || port.range === null ? 1 : null;
        if (width !== descriptor.width) throw new Error(`Port ${String(operation.name)}.${descriptor.name} width differs from its approved concrete configuration.`);
      }
    }
  }
}

export const ARCHITECTURE_PROMPT = defaultInstructions.text("architecture");

export { registerArchitectureTool } from "./tools/prepare_architecture_review.js";
