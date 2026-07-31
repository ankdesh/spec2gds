import { spawn } from "node:child_process";
import { createConnection } from "node:net";

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

function start(script) {
  const child = spawn(npmCommand, ["run", script], { stdio: "inherit" });
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
      const socket = createConnection({ host: "127.0.0.1", port: 4100 });
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
  if (!stopping) start("dev:standalone");
} catch (reason) {
  console.error(reason instanceof Error ? reason.message : String(reason));
  process.exitCode = 1;
  stop();
}
