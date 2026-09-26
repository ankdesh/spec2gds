/** Proposal-envelope checks shared by all owner domains. Domain shape belongs to the owner. */
export function validateProposalEnvelope(supported: boolean, reason: string | null, operations: unknown[]): void {
  if (supported && operations.length === 0) throw new Error("A supported proposal must contain at least one operation.");
  if (!supported && operations.length !== 0) throw new Error("An unsupported request cannot contain operations.");
  if (!supported && !reason?.trim()) throw new Error("An unsupported request must include unsupported_reason.");
  if (supported && reason !== null) throw new Error("A supported proposal must use unsupported_reason=null.");
  const ids = new Set<string>();
  for (const [index, value] of operations.entries()) {
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`Operation ${index + 1} must be an object.`);
    const id = (value as Record<string, unknown>).operation_id;
    if (typeof id !== "string" || !id.trim()) throw new Error(`Operation ${index + 1} requires operation_id.`);
    if (ids.has(id)) throw new Error(`Duplicate operation_id: ${id}`);
    ids.add(id);
  }
}
