/** Submit one non-interactive spec2gds request through the DSH headless profile. */
import { createHash } from "node:crypto";
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
import { parseLaunchArgs } from "../../runtime/service-config.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const options = {};
const task = [];
let passthrough = false;
for (let index = 0; index < args.length; index += 1) {
  const value = args[index];
  if (passthrough) { task.push(value); continue; }
  if (value === "--") { passthrough = true; continue; }
  if (value === "--json") { options.json = true; continue; }
  if (["--service-config", "--public-host", "--domain", "--service-url", "--document-id", "--document-name", "--entity-name", "--owner-document-key", "--scope", "--entity-kind", "--entity-id", "--session-id"].includes(value)) {
    const next = args[++index];
    if (!next) throw new Error(`${value} requires a value`);
    options[value.slice(2)] = next;
    continue;
  }
  task.push(value);
}
if (options["service-config"]) options["service-config"] = parseLaunchArgs(["--service-config", options["service-config"]]).options["service-config"];
if (!task.length) throw new Error("Usage: npm run request -- [binding options] -- <one-off request>");
const state = resolve(process.env.ASSISTANT_STATE || resolve(root, ".dev"));
const scratchRoot = resolve(process.env.SPEC2GDS_SCRATCH_ROOT || resolve(state, "workspaces"));
const env = {
  ...process.env,
  ASSISTANT_PROFILE: process.env.ASSISTANT_PROFILE || "spec2gds-headless",
  ASSISTANT_STATE: state,
  SPEC2GDS_SCRATCH_ROOT: scratchRoot,
  SPEC_DOCUMENT_ROOT: resolve(process.env.SPEC_DOCUMENT_ROOT || resolve(state, "spec-documents")),
};
const headless = [];
if (options.json) headless.push("--json");
if (options["session-id"]) {
  headless.push("--session-id", options["session-id"]);
} else {
  const domain = options.domain;
  if (domain !== "spec" && domain !== "circuit") throw new Error("A fresh request requires --domain spec|circuit.");
  if (!options["service-url"] || (!options["document-id"] && !options["document-name"])) throw new Error("A fresh request requires --service-url and --document-name (or a technical document ID).");
  if (options["document-name"] || options["entity-name"]) {
    const query = new URLSearchParams();
    if (options["document-name"]) query.set("name", options["document-name"]);
    if (domain === "spec") {
      if (options["document-id"]) query.set("document_id", options["document-id"]);
      if (options["owner-document-key"]) query.set("owner_document_key", options["owner-document-key"]);
      if (options["entity-name"]) query.set("entity_name", options["entity-name"]);
      if (options["entity-kind"]) query.set("entity_kind", options["entity-kind"]);
    } else if (options["entity-name"]) throw new Error("Circuit requests select a whole named document.");
    const response = await fetch(`${options["service-url"].replace(/\/$/, "")}/documents/resolve?${query}`);
    const selected = await response.json();
    if (!response.ok) throw new Error(typeof selected.detail === "string" ? selected.detail : selected.detail?.message || selected.error?.message || "The owner could not resolve this name.");
    if (typeof selected.document_id !== "string" || !selected.document_id) throw new Error("The service returned no document identity for this name.");
    if (options["document-id"] && options["document-id"] !== selected.document_id) throw new Error("The name and technical identity select different documents.");
    if (options["owner-document-key"] && options["owner-document-key"] !== selected.owner_document_key) throw new Error("The name and package binding select different documents.");
    if (options["entity-name"] && (typeof selected.entity_id !== "string" || !selected.entity_id || typeof selected.entity_kind !== "string")) throw new Error("The service returned no target identity for this name.");
    if (options["entity-id"] && selected.entity_id && options["entity-id"] !== selected.entity_id) throw new Error("The name and technical identity select different targets.");
    options["document-id"] = selected.document_id;
    if (selected.owner_document_key) options["owner-document-key"] = selected.owner_document_key;
    if (selected.entity_id) { options["entity-id"] = selected.entity_id; options["entity-kind"] = selected.entity_kind; options.scope = "entity"; }
  }
  const binding = {
    domain,
    serviceBaseUrl: options["service-url"],
    documentId: options["document-id"],
    ...(options["owner-document-key"] ? { serviceDocumentKey: options["owner-document-key"] } : {}),
    scope: domain === "circuit" ? "document" : options.scope || "document",
    ...(options["entity-kind"] ? { entityKind: options["entity-kind"] } : {}),
    ...(options["entity-id"] ? { entityId: options["entity-id"] } : {}),
  };
  env.SPEC2GDS_BINDING_JSON = JSON.stringify(binding);
  const service = new URL(binding.serviceBaseUrl);
  service.pathname = domain === "spec" ? "/" : service.pathname.replace(/\/$/, "");
  let workspaceIdentity = { domain, serviceUrl: process.env.SPEC2GDS_CLI_WORKSPACE_IDENTITY || service.toString().replace(/\/$/, ""), documentId: binding.documentId,
    ...(domain === "spec" && binding.serviceDocumentKey && !process.env.SPEC2GDS_CLI_WORKSPACE_IDENTITY ? { serviceDocumentKey: binding.serviceDocumentKey } : {}) };
  if (domain === "circuit") {
    try {
      const response = await fetch(`${workspaceIdentity.serviceUrl}/documents/${encodeURIComponent(binding.documentId)}/source-binding`);
      if (response.ok) {
        const source = await response.json();
        if (source && typeof source.source_service_url === "string" && typeof source.source_document_id === "string") {
          workspaceIdentity = { domain: "spec", serviceUrl: source.source_service_url.replace(/\/$/, ""), documentId: source.source_document_id, ...(source.source_owner_document_key ? { serviceDocumentKey: source.source_owner_document_key } : {}) };
        }
      }
    } catch { /* The Circuit binding remains independently grouped when its optional source metadata is unavailable. */ }
  }
  const workspaceKey = createHash("sha256").update(JSON.stringify(workspaceIdentity)).digest("hex");
  env.DSH_PRODUCT_RUN_CWD = resolve(scratchRoot, "design-sources", workspaceKey);
  mkdirSync(env.DSH_PRODUCT_RUN_CWD, { recursive: true, mode: 0o700 });
}
headless.push(task.join(" "));
const child = spawn(process.execPath, [resolve(root, "scripts/dev.mjs"), ...["service-config", "public-host"].flatMap(key => options[key] ? [`--${key}`, options[key]] : []), ...headless], { cwd: env.DSH_PRODUCT_RUN_CWD || root, env, stdio: "inherit" });
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
child.on("exit", (code, signal) => { process.exitCode = code ?? (signal ? 1 : 0); });
