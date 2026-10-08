import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
const editorRoot = fileURLToPath(new URL("../", import.meta.url));
const environment = { ...process.env };
environment.PLAYWRIGHT_BROWSERS_PATH ||= fileURLToPath(
  new URL("../../../.playwright-browsers", import.meta.url),
);
if (process.platform !== "win32") {
  environment.TMPDIR = "/tmp";
  environment.TMP = "/tmp";
  environment.TEMP = "/tmp";
}
const result = spawnSync(
  npmCommand,
  ["exec", "playwright", "test", "--", "--config", "playwright.config.ts", ...process.argv.slice(2)],
  { cwd: editorRoot, env: environment, stdio: "inherit" },
);
process.exit(result.status ?? 1);
