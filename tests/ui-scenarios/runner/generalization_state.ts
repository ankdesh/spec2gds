/** Resolve evaluation state from the saved creation receipt, never the active Spec. */
import assert from "node:assert/strict";
import { resolve } from "node:path";

/** A completed empty Spec cannot satisfy a hardware creation evaluation. */
export function assertEvaluationCreationFlow(definition: string | null, status: string | null, error: string | null): void {
  if (!definition) return;
  assert.equal(definition, "spec2gds.create_spec_with_component", `Evaluation selected the wrong flow: ${definition}`);
  assert.ok(!["failed", "needs-reconcile", "cancelled"].includes(status || ""), `Evaluation creation flow ${status}: ${error || "no diagnostic"}`);
}

export function assertEvaluationInterface(plan: any, ports: { name: string; direction: string; width: number }[], elaborations: any[] = []): void {
  assert.equal(plan.components.length, 1, "Evaluation requires one approved leaf Component.");
  assert.equal(plan.designs.length, 0, "Evaluation uses the published leaf creation flow.");
  const groups = plan.interfaces.filter((item: any) => item.component === plan.components[0].name);
  assert.equal(groups.length, 1, "Evaluation requires one complete approved interface.");
  const ordered = (items: typeof ports) => items.map(({ name, direction, width }) => ({ name, direction, width })).sort((a, b) => a.name.localeCompare(b.name));
  const actual = groups[0].ports.map((port: any) => {
    const bounds = port.range === null ? null : /^(-?\d+):(-?\d+)$/.exec(port.range);
    const evaluated = elaborations.find(group => group.component === groups[0].component && group.status === "resolved")?.ports.find((item: any) => item.name === port.name);
    assert.ok(port.range === null || bounds || evaluated, `The evaluation interface needs resolved bounds for ${port.name}.`);
    return { name: port.name, direction: port.direction, width: evaluated?.width ?? (bounds ? Math.abs(Number(bounds[1]) - Number(bounds[2])) + 1 : 1) };
  });
  assert.deepEqual(ordered(actual), ordered(ports), "Approved ports differ from the declared testbench contract.");
}

export function generatedSpecReceipt(receipts: any[], destination: string, reviewId: string): any | null {
  const matches = receipts.filter(item => typeof item.destination === "string"
    && resolve(item.destination) === resolve(destination) && item.architectureReviewId === reviewId);
  assert.ok(matches.length <= 1, "The generated .spec file must have one creation receipt.");
  const receipt = matches[0];
  if (!receipt || !["created", "reserved", "bound"].includes(receipt.status)) return null;
  assert.ok(typeof receipt.serviceDocumentKey === "string" && receipt.serviceDocumentKey,
    "The creation receipt must identify the exact Spec service document.");
  assert.ok(typeof receipt.documentId === "string" && receipt.documentId);
  return receipt;
}

/** A mistyped or duplicate case selection must not silently reduce live coverage. */
export function selectedEvaluationCases<T extends { id: string }>(cases: T[], selection: string): T[] {
  if (!selection) return cases;
  const ids = selection.split(",");
  assert.ok(ids.every(id => id.trim() === id && id.length), "--case needs nonempty case IDs without whitespace.");
  assert.equal(new Set(ids).size, ids.length, "Duplicate --case selections are not allowed.");
  return ids.map(id => {
    const item = cases.find(item => item.id === id);
    assert.ok(item, `Unknown --case: ${id}`);
    return item;
  });
}
