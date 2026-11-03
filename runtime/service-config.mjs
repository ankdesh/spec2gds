/** ESM entry for the shared resolver, also used by CommonJS test adapters. */
import resolver from "./service-config.cjs";
export const { defaultConfigPath, primaryIPv4, validatePort, resolveConfig, listenerOverrides,
  localHost, endpointUrl, parseLaunchArgs, serviceDirectory } = resolver;
