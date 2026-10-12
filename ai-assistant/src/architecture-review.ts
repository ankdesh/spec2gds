/** Durable architecture approval is separate from the service content policy. */

import { defaultInstructions } from "./instructions.js";
import { compactWireRange } from "./normalize.js";
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
    const expected = grouped?.ports;
    if (!expected) continue;
    const ports = Array.isArray(operation.ports) ? operation.ports : [];
    if (ports.length !== expected.length) throw new Error(`Component ${String(operation.name)} ports differ from its approved interface.`);
    for (const descriptor of expected) {
      if (!isRecord(descriptor) || typeof descriptor.name !== "string") throw new Error("Approved port descriptors require names.");
      const port = ports.find(item => isRecord(item) && item.name === descriptor.name);
      if (!isRecord(port) || (descriptor.direction !== undefined && descriptor.direction !== port.direction)) throw new Error(`Port ${String(operation.name)}.${descriptor.name} differs from its approved interface.`);
      if (!Object.hasOwn(descriptor, "range") || (typeof descriptor.description !== "string" || !descriptor.description.trim()) || Object.hasOwn(descriptor, "width")) throw new Error("Prepare a new interface review with exact ranges and descriptions.");
      if (compactWireRange(port.range ?? null) !== compactWireRange(descriptor.range) || port.description !== descriptor.description) throw new Error(`Port ${String(operation.name)}.${descriptor.name} differs from its approved exact range or description.`);

    }
  }
}

export const ARCHITECTURE_PROMPT = defaultInstructions.text("architecture");
