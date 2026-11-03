import { spawn } from "node:child_process";
import { createConnection } from "node:net";
import { mkdirSync, writeFileSync } from "node:fs";
import { randomUUID } from "node:crypto";
import { resolveConfig, parseLaunchArgs, listenerOverrides, localHost } from "../../runtime/service-config.mjs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const { options, rest } = parseLaunchArgs(process.argv.slice(2), ["ui-host", "ui-port"]);
if (rest.includes("--help")) {
  console.log("Circuit Designer: [--service-config PATH] [--host HOST] [--port PORT] [--ui-host HOST] [--ui-port PORT] [--public-host HOST]. Other options go to Vite.");
  process.exit(0);
}
const overrides = listenerOverrides("circuit_designer", options);
overrides.circuit_designer.ui = Object.fromEntries([["host", options["ui-host"]], ["port", options["ui-port"]]].filter(([, value]) => value !== undefined));
if (options["public-host"] !== undefined) overrides.public_host = options["public-host"];
const serviceConfig = resolveConfig(options["service-config"], overrides);
const directory = resolve(dirname(fileURLToPath(import.meta.url)), "../../TEMP_serve-all", `circuit_${randomUUID()}`);
mkdirSync(directory, { recursive: true });
const configPath = resolve(directory, "services.json");
writeFileSync(configPath, JSON.stringify(serviceConfig, null, 2));
const circuitService = serviceConfig.circuit_designer.service;

const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
const children = [];
let stopping = false;

function stop(signal = "SIGTERM") {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    if (!child.killed) child.kill(signal);
  }
}

function start(script, args = []) {
  const child = spawn(npmCommand, ["run", script, "--", "--service-config", configPath, ...args], { stdio: "inherit" });
  children.push(child);
  child.once("exit", (code, signal) => {
    if (stopping) return;
    process.exitCode = code ?? (signal ? 1 : 0);
    stop();
  });
  return child;
}

function waitForService(timeoutMs = 15_000) {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    const connect = () => {
      if (stopping) return reject(new Error("Circuit Designer service stopped during startup."));
      const socket = createConnection({
        host: localHost(circuitService.host),
        port: circuitService.port,
      });
      socket.once("connect", () => {
        socket.destroy();
        resolve();
      });
      socket.once("error", () => {
        socket.destroy();
        if (Date.now() >= deadline) reject(new Error("Timed out waiting for the Circuit Designer service."));
        else setTimeout(connect, 100);
      });
    };
    connect();
  });
}

process.once("SIGINT", () => stop("SIGINT"));
process.once("SIGTERM", () => stop("SIGTERM"));

start("service");
try {
  await waitForService();
  if (!stopping) start("dev:standalone", rest);
} catch (reason) {
  console.error(reason instanceof Error ? reason.message : String(reason));
  process.exitCode = 1;
  stop();
}
