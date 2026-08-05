import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
type LogLevel = "info" | "debug";

interface EndpointConfig {
  scheme: "http" | "https";
  host: string;
  port: number;
  base_path: string;
}

interface HostedServiceConfig {
  service: EndpointConfig;
  ui: EndpointConfig;
}

interface RegistryConfig {
  schema_version: 2;
  logging: { enabled: boolean; level: LogLevel };
  spec_editor: HostedServiceConfig;
  circuit_designer: HostedServiceConfig;
  ai_assistant: HostedServiceConfig;
}

export interface ServiceLocation {
  service_url: string;
  ui_url: string;
}

export interface PublicServiceDirectory {
  schema_version: 2;
  services: {
    spec_editor: ServiceLocation;
    circuit_designer: ServiceLocation;
    ai_assistant: ServiceLocation;
  };
  logging: { enabled: boolean; level: LogLevel };
}

export function loadServiceRegistry(
  path = process.env.SPEC2GDS_SERVICE_CONFIG ?? defaultRegistryPath(),
): RegistryConfig {
  const value = JSON.parse(readFileSync(path, "utf8")) as RegistryConfig;
  if (value.schema_version !== 2) throw new Error("Service registry schema_version must be 2.");
  return value;
}

export function resolvedServiceDirectory(): PublicServiceDirectory {
  const value = loadServiceRegistry();
  const directory: PublicServiceDirectory = {
    schema_version: 2,
    services: {
      spec_editor: location(value.spec_editor),
      circuit_designer: location(value.circuit_designer),
      ai_assistant: location(value.ai_assistant),
    },
    logging: publicLogging(value),
  };
  directory.services.spec_editor.service_url = stripTrailingSlash(
    process.env.SPEC_EDITOR_SERVICE_URL ?? directory.services.spec_editor.service_url,
  );
  directory.services.circuit_designer.service_url = stripTrailingSlash(
    process.env.CIRCUIT_DESIGNER_SERVICE_URL ?? directory.services.circuit_designer.service_url,
  );
  directory.services.circuit_designer.ui_url = stripTrailingSlash(
    process.env.CIRCUIT_DESIGNER_UI_URL ?? directory.services.circuit_designer.ui_url,
  );
  const assistantOverride = process.env.AI_ASSISTANT_URL;
  if (assistantOverride) {
    const assistant = stripTrailingSlash(assistantOverride);
    directory.services.ai_assistant.service_url = assistant;
    directory.services.ai_assistant.ui_url = assistant;
  }
  return directory;
}

function publicLogging(value: RegistryConfig): { enabled: boolean; level: LogLevel } {
  const logging = value.logging;
  const enabledOverride = process.env.SPEC2GDS_LOGGING;
  const normalized = enabledOverride?.toLowerCase();
  if (normalized !== undefined && normalized !== "on" && normalized !== "off") {
    throw new Error("SPEC2GDS_LOGGING must be ON or OFF.");
  }
  const level = String(process.env.SPEC2GDS_LOG_LEVEL ?? logging?.level ?? "info").toLowerCase();
  if (level !== "info" && level !== "debug") throw new Error("SPEC2GDS_LOG_LEVEL must be info or debug.");
  return { enabled: normalized === undefined ? logging.enabled : normalized === "on", level };
}

function defaultRegistryPath(): string {
  return resolve(
    dirname(fileURLToPath(import.meta.url)),
    "../../../../config/services.json",
  );
}

function location(value: HostedServiceConfig): ServiceLocation {
  return { service_url: endpointUrl(value.service), ui_url: endpointUrl(value.ui) };
}

function endpointUrl(value: EndpointConfig): string {
  const path = value.base_path ? `/${value.base_path.replace(/^\/+|\/+$/g, "")}` : "";
  return `${value.scheme}://${value.host}:${value.port}${path}`;
}

function stripTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}
