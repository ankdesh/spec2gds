import { compileFromFile } from "json-schema-to-typescript";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const workspace = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const schemaPath = path.join(workspace, "schema", "circuit-designer.v1.schema.json");
const outputPath = path.join(workspace, "packages", "core", "src", "types.generated.ts");
const bundledSchemaPath = path.join(workspace, "packages", "core", "src", "protocol.schema.json");
const source = await compileFromFile(schemaPath, {
  bannerComment: "/* Generated from circuit-designer.v1.schema.json. Do not edit. */",
  cwd: workspace,
  format: true,
  style: { singleQuote: false, semi: true },
  unknownAny: false,
});
await mkdir(path.dirname(outputPath), { recursive: true });
await writeFile(outputPath, source, "utf8");
const schema = JSON.parse(await readFile(schemaPath, "utf8"));
await writeFile(bundledSchemaPath, `${JSON.stringify(schema, null, 2)}\n`, "utf8");
