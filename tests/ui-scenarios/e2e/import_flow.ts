import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { test, expect, root, openSpec } from "./fixtures.js";

function available(): boolean {
  return spawnSync(join(root, ".venv/bin/python"), ["-c", "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('docling') else 1)"]).status === 0;
}

export function documentImports(): void {
  test.describe("Real document imports", () => {
  test.skip(!available(), "Docling document-import dependencies are not installed; real import is unverified.");
  for (const extension of ["pdf", "docx", "odt"]) {
    test(`real ${extension.toUpperCase()} document import retains source and opens in Spec Editor`, async ({ page, stack }) => {
      const input = join(root, `tests/ui-scenarios/fixtures/document-import/common.${extension}`);
      const output = stack.path(`imported-${extension}.spec`);
      const result = spawnSync(join(root, ".venv/bin/spec2gds-import-document"), [input, "--output", output, "--no-ocr"],
        { cwd: root, env: stack.env, encoding: "utf8", timeout: 90_000 });
      expect(result.status, result.stderr).toBe(0);
      const report = JSON.parse(result.stdout);
      expect(report.block_count).toBeGreaterThan(0);
      if (extension !== "pdf") {
        expect(report.table_count).toBeGreaterThan(0);
        expect(report.image_count).toBeGreaterThan(0);
      }
      const retained = spawnSync(join(root, ".venv/bin/python"), ["-c",
        "import sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); assert z.read('annotations/document_import/source.'+sys.argv[3])==open(sys.argv[2],'rb').read()", output, input, extension], { encoding: "utf8" });
      expect(retained.status, retained.stderr).toBe(0);
      await openSpec(page, stack, output);
      await expect(page.locator(".spec-paper")).toContainText("A reset clears the count.");
      const saved = await stack.snapshot();
      await stack.restart("spec");
      await openSpec(page, stack, output);
      expect((await stack.snapshot()).source_revision_hash).toBe(saved.source_revision_hash);
    });
  }
  test("real corrupt and unsupported imports leave no partial output", async ({ stack }) => {
    for (const extension of ["pdf", "unknown"]) {
      const input = stack.path(`corrupt.${extension}`);
      const output = stack.path(`rejected-${extension}.spec`);
      writeFileSync(input, "invalid document content");
      const result = spawnSync(join(root, ".venv/bin/spec2gds-import-document"), [input, "--output", output, "--no-ocr"],
        { cwd: root, env: stack.env, encoding: "utf8", timeout: 90_000 });
      expect(result.status, result.stderr).toBe(2);
      expect(existsSync(output)).toBe(false);
      expect(readFileSync(input, "utf8")).toBe("invalid document content");
    }
  });
  });
}
