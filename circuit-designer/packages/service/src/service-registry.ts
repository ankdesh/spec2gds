/** Circuit service adapter for the shared Node resolver. */
import { resolve } from "node:path";
import { resolveConfig, serviceDirectory, type ServiceConfig } from "../../../../runtime/service-config.mjs";

type LogLevel = "info" | "debug";
export interface ServiceLocation { service_url: string; ui_url: string }
export interface PublicServiceDirectory {
  schema_version: 2;
  services: { spec_editor: ServiceLocation; circuit_designer: ServiceLocation; ai_assistant: ServiceLocation };
  logging: { enabled: boolean; level: LogLevel };
}
export const loadServiceRegistry = resolveConfig;
export function resolvedCircuitPreferencesPath(path?: string): string {
  return process.env.CIRCUIT_DESIGNER_PREFERENCES_FILE
    ? resolve(process.env.CIRCUIT_DESIGNER_PREFERENCES_FILE) : resolveConfig(path).circuit_designer.preferences_file;
}
export function resolvedServiceDirectory(config: ServiceConfig = resolveConfig()): PublicServiceDirectory {
  const enabledOverride = process.env.SPEC2GDS_LOGGING?.toLowerCase();
  if (enabledOverride !== undefined && !["on", "off"].includes(enabledOverride)) throw new Error("SPEC2GDS_LOGGING must be ON or OFF.");
  const level = (process.env.SPEC2GDS_LOG_LEVEL ?? config.logging.level).toLowerCase();
  if (level !== "info" && level !== "debug") throw new Error("SPEC2GDS_LOG_LEVEL must be info or debug.");
  return { schema_version: 2, services: serviceDirectory(config), logging: {
    enabled: enabledOverride === undefined ? config.logging.enabled : enabledOverride === "on", level,
  } };
}
export const resolvedPublicHost = () => resolveConfig().public_host;
