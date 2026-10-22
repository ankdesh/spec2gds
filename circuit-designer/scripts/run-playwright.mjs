import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
const environment = { ...process.env };
environment.PLAYWRIGHT_BROWSERS_PATH ||= fileURLToPath(new URL("../.playwright-browsers", import.meta.url));
if (process.platform !== "win32") {
  environment.TMPDIR ||= "/tmp";
  environment.TMP ||= environment.TMPDIR;
  environment.TEMP ||= environment.TMPDIR;
}
const result = spawnSync(
  npmCommand,
  ["exec", "playwright", "test", "--", ...process.argv.slice(2)],
  { env: environment, stdio: "inherit" },
);
process.exit(result.status ?? 1);
