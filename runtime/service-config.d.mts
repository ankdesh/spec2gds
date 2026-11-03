export interface Endpoint { scheme: "http" | "https"; host: string; port: number; base_path: string }
export interface HostedService { service: Endpoint; ui: Endpoint }
export interface ServiceConfig {
  schema_version: 2; public_host: string;
  spec_editor: HostedService & { dev_ui: Endpoint };
  circuit_designer: HostedService & { preferences_file: string; provider_allowlist?: string[] };
  ai_assistant: HostedService; verification_planner: HostedService;
  logging: { enabled: boolean; level: "info" | "debug"; file: string; max_bytes: number; viewer: Endpoint };
  activities: { scratch_root: string; extension_modules: string[] };
}
export function defaultConfigPath(): string;
export function primaryIPv4(): string;
export function validatePort(value: number): number;
export function resolveConfig(path?: string, overrides?: object): ServiceConfig;
export function listenerOverrides(name: string, fields?: { host?: string; port?: number }): object;
export function localHost(host: string): string;
export function endpointUrl(value: Endpoint, publicHost: string, options?: { local?: boolean; origin?: boolean }): string;
export function parseLaunchArgs(args: string[], extra?: string[]): { options: Record<string, any>; rest: string[] };
export function serviceDirectory(config: ServiceConfig): Record<"spec_editor" | "circuit_designer" | "ai_assistant", { service_url: string; ui_url: string }>;
