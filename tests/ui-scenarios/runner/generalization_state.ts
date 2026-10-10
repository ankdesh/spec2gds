/** Resolve evaluation state from the saved creation receipt, never the active Spec. */
import assert from "node:assert/strict";
import { resolve } from "node:path";

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
