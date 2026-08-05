/** Small browser event client; failures are intentionally silent to avoid recursion. */
export type BrowserLogLevel = "info" | "debug";
export type BrowserSeverity = "debug" | "info" | "warning" | "error";

export interface PublicLoggingConfig { enabled: boolean; level: BrowserLogLevel }

export class BrowserLogger {
  readonly sessionId = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
  constructor(private readonly endpoint: string, private readonly config: PublicLoggingConfig) {}

  event(component: string, event: string, message: string, severity: BrowserSeverity = "info", details?: unknown): void {
    if (!this.config.enabled || (severity === "debug" && this.config.level !== "debug")) return;
    const payload = JSON.stringify({
      session_id: this.sessionId,
      events: [{ timestamp: new Date().toISOString(), component, event, message, severity, details }],
    });
    try {
      if (navigator.sendBeacon) navigator.sendBeacon(this.endpoint, new Blob([payload], { type: "application/json" }));
      else void fetch(this.endpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: payload, keepalive: true }).catch(() => undefined);
    } catch { /* Observability must never interrupt the user interface. */ }
  }

  captureGlobalErrors(): () => void {
    const onError = (event: ErrorEvent) => this.event("window", "uncaught_error", event.message, "error", { filename: event.filename, line: event.lineno, column: event.colno, error: String(event.error ?? "") });
    const onRejection = (event: PromiseRejectionEvent) => this.event("window", "unhandled_rejection", "Unhandled promise rejection", "error", { reason: String(event.reason) });
    window.addEventListener("error", onError); window.addEventListener("unhandledrejection", onRejection);
    return () => { window.removeEventListener("error", onError); window.removeEventListener("unhandledrejection", onRejection); };
  }
}
