import assert from "node:assert/strict";
import test from "node:test";
import { expectedBrowserFailure } from "./browser_failures.js";

const context = { stopping: false, serviceUrl: "http://127.0.0.1:1234", scenario: "automatic" };
test("binding failures remain fatal for both bound and unbound conversations and review subresources", () => {
  for (const origin of [context.serviceUrl, "http://foreign.invalid"]) {
    for (const path of ["/bindings/session-unbound", "/bindings/session-bound", "/bindings/session-bound/reviews", "/bindings/session-bound/execution"]) {
      assert.equal(expectedBrowserFailure("console", origin + path, "404 Not Found", context), false);
      assert.equal(expectedBrowserFailure("network", origin + path, "net::ERR_FAILED", context), false);
    }
  }
});
test("real transport failures are distinct from event-stream cancellation", () => {
  assert.equal(expectedBrowserFailure("network", context.serviceUrl + "/events", "net::ERR_FAILED", context), false);
  assert.equal(expectedBrowserFailure("network", context.serviceUrl + "/events", "net::ERR_ABORTED", context), true);
  assert.equal(expectedBrowserFailure("console", context.serviceUrl + "/transactions", "409 Conflict", context), false);
  assert.equal(expectedBrowserFailure("console", context.serviceUrl + "/transactions", "409 Conflict", { ...context, scenario: "live" }), true);
});
