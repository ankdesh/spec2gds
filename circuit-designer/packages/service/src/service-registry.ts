import { readFileSync } from "node:fs";
import { hostname, networkInterfaces } from "node:os";
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
  public_host?: string;
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
  const publicHost = resolvePublicHost(value);
  const directory: PublicServiceDirectory = {
    schema_version: 2,
    services: {
      spec_editor: location(value.spec_editor, publicHost),
      circuit_designer: location(value.circuit_designer, publicHost),
      ai_assistant: location(value.ai_assistant, publicHost),
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

function location(value: HostedServiceConfig, publicHost: string): ServiceLocation {
  return {
    service_url: endpointUrl(value.service, publicHost),
    ui_url: endpointUrl(value.ui, publicHost),
  };
}

function endpointUrl(value: EndpointConfig, publicHost: string): string {
  const path = value.base_path ? `/${value.base_path.replace(/^\/+|\/+$/g, "")}` : "";
  const authority = publicHost.includes(":") ? `[${publicHost}]` : publicHost;
  return `${value.scheme}://${authority}:${value.port}${path}`;
}

export function resolvedPublicHost(): string {
  return resolvePublicHost(loadServiceRegistry());
}

function resolvePublicHost(value: RegistryConfig): string {
  const configured = (process.env.SPEC2GDS_PUBLIC_HOST ?? value.public_host ?? "auto").trim();
  if (configured.toLowerCase() !== "auto") {
    if (!configured || configured.includes("://") || configured.includes("/")) {
      throw new Error("public_host must be auto, an IP address, or a hostname.");
    }
    return configured;
  }
  for (const addresses of Object.values(networkInterfaces())) {
    for (const address of addresses ?? []) {
      if (address.family === "IPv4" && !address.internal) return address.address;
    }
  }
  return hostname();
}

function stripTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}
