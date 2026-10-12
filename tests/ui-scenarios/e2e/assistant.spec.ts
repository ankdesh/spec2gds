/** Additional native-shell cases use the real Harness and a scripted model. */
import { spawn } from "node:child_process";
import { once } from "node:events";
import { createWriteStream } from "node:fs";
import { test, expect } from "@playwright/test";
import { root, stop } from "./fixtures.js";

for (const mode of ["automatic", "restricted"]) {
  test(`native ${mode} saving preserves a large proposal on disk and checks its receipt`, async ({}, info) => {
    test.setTimeout(660_000);
    const output = info.outputPath("native");
    const log = createWriteStream(info.outputPath("native.log"));
    const child = spawn(process.execPath, ["--import", "tsx", "runner/run_scenario.ts", "--scenario", mode,
      "--large-proposal", "--assistant-presentation-checks", "--output", output], {
      cwd: `${root}/tests/ui-scenarios`, env: process.env, detached: true, stdio: ["ignore", "pipe", "pipe"],
    });
    child.stdout?.pipe(log, { end: false }); child.stderr?.pipe(log, { end: false });
    const timeout = setTimeout(() => void stop(child), 600_000);
    try {
      const [code, signal] = await once(child, "exit");
      expect(signal, "Native flow was interrupted").toBeNull();
      expect(code, `See native.log and the saved source evidence in ${output}`).toBe(0);
    } finally { clearTimeout(timeout); await stop(child); log.end(); }
  });
}
