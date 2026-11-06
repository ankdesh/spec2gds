/** Shared address resolution for Node launchers, services, Vite, and releases. */
const { readFileSync, existsSync } = require("node:fs");
const { dirname, resolve } = require("node:path");
const { execFileSync } = require("node:child_process");
const { hostname, homedir } = require("node:os");
const { isIP } = require("node:net");

const defaultsPath = resolve(__dirname, "src/spec2gds_runtime/service-defaults.json");
const defaultConfigPath = () => {
  const path = resolve(__dirname, "../config/services.json");
  return existsSync(path) ? path : defaultsPath;
};
const names = ["spec_editor", "circuit_designer", "ai_assistant", "verification_planner", "spec_catalog"];
const shared = ["spec_editor", "ai_assistant", "verification_planner", "spec_catalog"];
function merge(base, supplied) {
  const result = structuredClone(base);
  for (const [key, item] of Object.entries(supplied)) {
    result[key] = item && typeof item === "object" && !Array.isArray(item) && result[key] && typeof result[key] === "object"
      ? merge(result[key], item) : structuredClone(item);
  }
  return result;
}
function primaryIPv4() {
  try {
    return execFileSync(process.execPath, ["--input-type=module", "-e",
      'import dgram from "node:dgram"; const s=dgram.createSocket("udp4"); s.on("error",()=>process.exit(1)); s.connect(9,"192.0.2.1",()=>{process.stdout.write(s.address().address);s.close()})'],
    { encoding: "utf8", timeout: 2000, stdio: ["ignore", "pipe", "ignore"] }).trim() || hostname();
  } catch { return hostname(); }
}
function host(value, name) {
  if (typeof value !== "string" || !value.trim() || /[\/\\?#@\s]/.test(value)) throw new Error(`${name} must be an IP address or a hostname.`);
  const result = value.replace(/^\[|\]$/g, "");
  if ((result.includes(":") && isIP(result.split("%")[0]) !== 6) || /[\[\]]/.test(result)) throw new Error(`${name} must be an IP address or a hostname.`);
  return result;
}
function validatePort(port) {
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error("port must be between 1 and 65535.");
  return port;
}
function endpoint(value, name) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${name} must be an object.`);
  if (!["http", "https"].includes(value.scheme)) throw new Error(`${name}.scheme must be http or https.`);
  value.host = host(value.host, `${name}.host`);
  validatePort(value.port);
  if (typeof value.base_path !== "string" || /[?#]/.test(value.base_path)) throw new Error(`${name}.base_path must be a URL path.`);
}
function resolveConfig(path = defaultConfigPath(), overrides = {}) {
  path = resolve(path.replace(/^~(?=\/)/, homedir()));
  const supplied = JSON.parse(readFileSync(path, "utf8"));
  if (!supplied || typeof supplied !== "object" || Array.isArray(supplied) || (supplied.schema_version ?? 2) !== 2) throw new Error("Service registry schema_version must be 2.");
  if (supplied.activities?.workspace_root && supplied.activities.scratch_root === undefined) supplied.activities.scratch_root = supplied.activities.workspace_root;
  const value = merge(merge(JSON.parse(readFileSync(defaultsPath, "utf8")), supplied), overrides);
  value.public_host = host(typeof value.public_host === "string" && value.public_host.toLowerCase() === "auto" ? primaryIPv4() : value.public_host, "public_host");
  for (const name of names) {
    if (!value[name] || typeof value[name] !== "object" || Array.isArray(value[name])) throw new Error(`${name} must be an object.`);
    for (const surface of name === "spec_editor" ? ["service", "ui", "dev_ui"] : ["service", "ui"]) endpoint(value[name][surface], `${name}.${surface}`);
  }
  for (const name of shared) {
    if (["scheme", "host", "port"].some(key => value[name].service[key] !== value[name].ui[key])) throw new Error(`${name}.service and ui must use the same listener.`);
  }
  endpoint(value.logging?.viewer, "logging.viewer");
  for (const [section, field] of [["spec_editor", "spec_root"], ["logging", "file"], ["activities", "scratch_root"], ["circuit_designer", "preferences_file"], ["spec_catalog", "catalog_root"], ["spec_catalog", "state_dir"]]) {
    const file = value[section]?.[field];
    if (typeof file !== "string" || !file.trim()) throw new Error(`${section}.${field} must be a non-empty string.`);
    value[section][field] = resolve(dirname(path), file.replace(/^~(?=\/)/, homedir()));
  }
  if (!Array.isArray(value.activities.extension_modules) || value.activities.extension_modules.some(item => typeof item !== "string" || !item.trim())) throw new Error("activities.extension_modules must contain non-empty strings.");
  return value;
}
function listenerOverrides(name, { host, port } = {}) {
  const fields = Object.fromEntries(Object.entries({ host, port }).filter(([, item]) => item !== undefined));
  return { [name]: Object.fromEntries((shared.includes(name) ? ["service", "ui"] : ["service"]).map(surface => [surface, { ...fields }])) };
}
const localHost = host => ({ "0.0.0.0": "127.0.0.1", "::": "::1" })[host] ?? host;
function endpointUrl(value, publicHost, { local = false, origin = false } = {}) {
  const selected = local ? localHost(value.host) : ["0.0.0.0", "::"].includes(value.host) ? publicHost : value.host;
  const path = origin ? "" : value.base_path.replace(/^\/+|\/+$/g, "");
  return `${value.scheme}://${selected.includes(":") ? `[${selected}]` : selected}:${value.port}${path ? `/${path}` : ""}`;
}
/** Consume only launch options. All other arguments stay in their original order. */
function parseLaunchArgs(args, extra = []) {
  const options = {}, rest = [];
  const supported = new Set(["service-config", "host", "port", "public-host", ...extra]);
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--") { rest.push(...args.slice(i)); break; }
    const [flag, inline] = args[i].split(/=(.*)/s);
    const key = flag.replace(/^--/, "");
    if (!flag.startsWith("--") || !supported.has(key)) { rest.push(args[i]); continue; }
    const value = inline ?? args[++i];
    if (!value || value.startsWith("--")) throw new Error(`${flag} requires a value.`);
    options[key] = key.endsWith("port") ? validatePort(Number(value))
      : key === "service-config" ? resolve(process.env.INIT_CWD || process.cwd(), value.replace(/^~(?=\/)/, homedir())) : value;
  }
  return { options, rest };
}
function serviceDirectory(config) {
  return Object.fromEntries(names.filter(name => name !== "verification_planner").map(name => [name, {
    service_url: endpointUrl(config[name].service, config.public_host),
    ui_url: endpointUrl(config[name].ui, config.public_host),
  }]));
}

module.exports = { defaultConfigPath, primaryIPv4, validatePort, resolveConfig, listenerOverrides, localHost, endpointUrl, parseLaunchArgs, serviceDirectory };
