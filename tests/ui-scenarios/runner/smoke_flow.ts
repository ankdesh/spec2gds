/** Three bounded live checks use real browser controls, services, and saved Specs. */
import assert from "node:assert/strict";
import { expect, type Page } from "@playwright/test";

export const smokeCases = ["description", "wire-range", "restricted-description"] as const;
export type SmokeCase = typeof smokeCases[number];

interface SmokeContext {
  caseId: SmokeCase;
  serviceUrl: string;
  assistantUrl: string;
  packagePath: string;
  documentId: string;
  conversation: Page;
  editor: Page;
  records: unknown[];
  json: (url: string, body?: unknown) => Promise<any>;
  openEditor: (page: Page, serviceUrl: string, path: string) => Promise<void>;
  prompt: (page: Page, message: string) => Promise<void>;
  savedSnapshot: (path: string) => any;
}

/** Seed through public transactions, then assert live changes and disk identity. */
export async function runSmoke(context: SmokeContext): Promise<void> {
  const { caseId, serviceUrl, assistantUrl, packagePath, documentId,
    conversation, editor, records, json, openEditor, prompt, savedSnapshot } = context;
  const restricted = caseId === "restricted-description";
  const created = await json(`${serviceUrl}/documents/create`, {
    path: packagePath, document_id: documentId, title: "Live smoke",
  });
  const key = created.owner_document_key;
  const scoped = (path: string) => `${serviceUrl}${path}?owner_document_key=${encodeURIComponent(key)}`;
  const transaction = async (snapshot: any, operations: unknown[]) =>
    (await json(scoped("/transactions"), {
      expected_source_revision_hash: snapshot.source_revision_hash, operations,
    })).snapshot;
  const componentOnly = await transaction(created, [
    { type: "create_entity", kind: "component", name: "smoke_core" },
  ]);
  const reference = componentOnly.components[0].ref;
  await transaction(componentOnly, [
    { type: "set_entity_metadata", entity: reference, display_name: "Smoke core",
      description: "Baseline smoke description." },
    { type: "add_component_port", component: reference,
      port: { name: "irq", family: "wire", direction: "out", range: "7:0",
        description: "Smoke check output." } },
  ]);
  const readSnapshot = () => json(scoped("/documents/snapshot"));
  const marker = restricted ? "Restricted live smoke saved." : "Automatic live smoke saved.";
  await openEditor(editor, serviceUrl, packagePath);
  // Opening applies the service's name normalisation. Compare subsequent model
  // edits against that authoritative revision, not the pre-open seed revision.
  const baseline = await readSnapshot();
  const query = new URLSearchParams({ service_base_url: serviceUrl, document_id: documentId,
    owner_document_key: key });
  await conversation.goto(`${assistantUrl}/launch/spec-document?${query}`);
  const request = caseId === "wire-range"
    ? "Change only smoke_core's existing irq output range to 15:0. Preserve its name, direction, description, display names, and all other content. Do not add RTL or new Components or Designs."
    : `Change only smoke_core's Component description to exactly '${marker}'. Preserve the display name 'Smoke core', every port, ID, and all other content. Do not add RTL or new Components or Designs.`;
  const evidence: Record<string, unknown> = { case: caseId, request, baseline,
    approval: restricted ? "review" : "automatic", evidence: "live-model/real-services" };
  records.push(evidence);
  await prompt(conversation, request);
  const architectureApprovals = new Set<string>();
  await expect.poll(async () => {
    assert.equal(await conversation.locator("[data-s2g-source-creation]").count(), 0,
      "A refinement of the bound Spec must not start creation of a new Spec.");
    assert.equal(await conversation.getByRole("heading", { name: "Spec creation unavailable", exact: true }).isVisible(), false,
      "The model attempted Spec creation instead of refining the bound Spec.");
    const pending = conversation.locator('[data-s2g-architecture-review="pending"]').last();
    if (await pending.isVisible()) {
      const id = await pending.getAttribute("data-s2g-architecture-review-id");
      assert.equal(typeof id, "string", "A review must expose its stable decision ID.");
      if (!architectureApprovals.has(id)) {
        assert.ok(architectureApprovals.size < 2, "A short live check permits at most two architecture decisions.");
        architectureApprovals.add(id);
        evidence.architectureApprovals = [...architectureApprovals];
        await pending.getByRole("button", { name: "Approve architecture", exact: true }).click();
      }
    }
    const failure = conversation.locator('[data-s2g-flow-status="failed"]');
    if (await failure.count()) throw new Error("The flow failed: " + await failure.getAttribute("data-s2g-flow-error"));
    if (restricted) {
      assert.equal((await readSnapshot()).source_revision_hash, baseline.source_revision_hash,
        "A restricted proposal must not change saved source before Save to Spec.");
      assert.equal(await conversation.getByRole("button", { name: "Save to Spec", exact: true }).count(), 0, "Spec decisions belong to Spec Editor.");
      return conversation.getByRole("link", { name: "Review in Spec Editor", exact: true }).isVisible();
    }
    return (await readSnapshot()).source_revision_hash !== baseline.source_revision_hash;
  }, { timeout: 90_000 }).toBe(true);
  if (restricted) {
    const link = conversation.getByRole("link", { name: "Review in Spec Editor", exact: true });
    await editor.goto(await link.getAttribute("href") || "");
    await editor.getByRole("button", { name: "Approve", exact: true }).click();
  }
  await expect.poll(async () => (await readSnapshot()).source_revision_hash,
    { timeout: 30_000 }).not.toBe(baseline.source_revision_hash);
  const result = await readSnapshot();
  evidence.result = result;
  evidence.architectureApprovals = [...architectureApprovals];
  assert.equal(result.components.length, 1);
  assert.equal(result.components[0].ref.entity_id, reference.entity_id);
  assert.deepEqual(result.designs, baseline.designs);
  assert.deepEqual(result.entity_sections, baseline.entity_sections);
  assert.deepEqual(result.narrative, baseline.narrative);
  if (caseId === "wire-range") {
    const expected = structuredClone(baseline.components);
    expected[0].ports[0].range = "15:0";
    expected[0].ports[0].width = "[15:0]";
    assert.deepEqual(result.components, expected, "Only the requested wire range may change.");
  } else {
    assert.deepEqual(result.components, baseline.components, "Description changes must preserve interfaces.");
  }
  await openEditor(editor, serviceUrl, packagePath);
  const component = editor.locator(`#component-${reference.entity_id.replaceAll("_", "-")}`);
  if (caseId === "wire-range") await expect(component).toContainText("15:0");
  else await expect(component.getByText(marker, { exact: true })).toBeVisible();
  const disk = savedSnapshot(packagePath);
  assert.equal(disk.source_revision_hash, result.source_revision_hash, "The accepted revision must be on disk.");
  assert.deepEqual(disk.components, result.components);
  evidence.disk = disk;
}
