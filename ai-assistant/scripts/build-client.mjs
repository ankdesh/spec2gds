import { copyFileSync, mkdirSync, rmSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
// A pre-migration build wrote its browser entry point into the server output.
// Remove that ignored artifact so npm packaging cannot accidentally ship it.
rmSync(resolve(root, "lib/client.js"), { force: true });
mkdirSync(resolve(root, "bundles/web/lib"), { recursive: true });
copyFileSync(resolve(root, "client/index.js"), resolve(root, "bundles/web/lib/client.js"));
copyFileSync(resolve(root, "client/host.js"), resolve(root, "bundles/web/lib/index.js"));
