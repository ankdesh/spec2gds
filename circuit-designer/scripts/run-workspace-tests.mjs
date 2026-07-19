import { spawnSync } from "node:child_process";

const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
const environment = { ...process.env };
if (process.platform !== "win32") {
  environment.TMPDIR = "/tmp";
  environment.TMP = "/tmp";
  environment.TEMP = "/tmp";
}
const result = spawnSync(npmCommand, ["run", "test", "--workspaces", "--if-present"], {
  env: environment,
  stdio: "inherit",
});
process.exit(result.status ?? 1);
