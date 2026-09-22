import { access, mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { calculateMetrics, parseJsonLines } from "../lib/eval-metrics.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const option = name => {
  const index = args.indexOf(name);
  return index >= 0 ? args[index + 1] : undefined;
};
const corpusRoot = resolve(option("--corpus") || resolve(root, "evals"));
const outputRoot = resolve(option("--output") || "/tmp/spec2gds-assistant-eval");
const manifest = JSON.parse(await readFile(resolve(corpusRoot, "manifest.json"), "utf8"));
if (manifest.schema_version !== "spec2gds.assistant-eval-manifest.v1" || !Array.isArray(manifest.cases)) {
  throw new Error("Unsupported evaluation manifest.");
}
const results = [];
for (const id of manifest.cases) {
  const value = JSON.parse(await readFile(resolve(corpusRoot, "cases", id, "case.json"), "utf8"));
  const required = ["schema_version", "id", "domain", "binding", "initial_fixture", "intent", "allowed_outcomes", "semantic_assertions", "safety"];
  const missing = required.filter(key => !(key in value));
  if (value.schema_version !== "spec2gds.assistant-eval.v1" || value.id !== id || missing.length) {
    throw new Error(`Invalid evaluation case ${id}; missing ${missing.join(",") || "none"}.`);
  }
  if (!["spec", "circuit"].includes(value.domain) || !Array.isArray(value.allowed_outcomes) || !value.allowed_outcomes.length) {
    throw new Error(`Evaluation case ${id} has invalid domain or outcomes.`);
  }
  if (!Array.isArray(value.semantic_assertions) || !value.semantic_assertions.length
    || value.semantic_assertions.some(assertion => typeof assertion !== "string" || !assertion.trim())) {
    throw new Error(`Evaluation case ${id} must define semantic assertions.`);
  }
  if (value.safety?.no_mutation_before_action !== true || value.safety?.max_model_steps !== 3
    || !Array.isArray(value.safety?.forbidden_completion_claims)) {
    throw new Error(`Evaluation case ${id} has an incomplete safety contract.`);
  }
  await access(resolve(corpusRoot, "cases", id, value.initial_fixture));
  results.push({
    id,
    status: "catalogued",
    domain: value.domain,
    allowed_outcomes: value.allowed_outcomes,
    semantic_assertions: value.semantic_assertions,
    safety: value.safety,
  });
}
const sessionPath = option("--session");
const events = sessionPath ? parseJsonLines(await readFile(resolve(sessionPath), "utf8")) : [];
const metrics = calculateMetrics(events, results.length);
await mkdir(outputRoot, { recursive: true });
await Promise.all([
  writeFile(resolve(outputRoot, "events.jsonl"), events.map(value => JSON.stringify(value)).join("\n") + (events.length ? "\n" : "")),
  writeFile(resolve(outputRoot, "results.json"), `${JSON.stringify({ schema_version: "spec2gds.assistant-eval-results.v1", results }, null, 2)}\n`),
  writeFile(resolve(outputRoot, "metrics.json"), `${JSON.stringify({ schema_version: "spec2gds.assistant-metrics.v1", metrics }, null, 2)}\n`),
]);
console.log(`Validated ${results.length} evaluation cases; wrote ${outputRoot}.`);
