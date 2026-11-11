import assert from "node:assert/strict";
import test from "node:test";
import { expectedBrowserFailure } from "./browser_failures.js";

test("only unload cancellation is expected for Spec edit release", () => {
  const context = { stopping: false, serviceUrl: "http://127.0.0.1:6010", scenario: "smoke" };
  const path = "/documents/edit-access/release?owner_document_key=spec_test";
  assert.equal(expectedBrowserFailure("network", context.serviceUrl + path, "net::ERR_ABORTED", context), true);
  assert.equal(expectedBrowserFailure("network", context.serviceUrl + path, "net::ERR_FAILED", context), false);
  assert.equal(expectedBrowserFailure("network", "http://other.test" + path, "net::ERR_ABORTED", context), false);
  assert.equal(expectedBrowserFailure("network", context.serviceUrl + "/documents/edit-access/renew?x=1", "net::ERR_ABORTED", context), false);
});

const context = { stopping: false, serviceUrl: "http://127.0.0.1:1234", scenario: "automatic" };
test("local blob download cancellation does not hide service failures", () => {
  const url = `blob:${context.serviceUrl}/download`;
  assert.equal(expectedBrowserFailure("network", url, "net::ERR_ABORTED", context), true);
  assert.equal(expectedBrowserFailure("network", url, "net::ERR_FAILED", context), false);
  assert.equal(expectedBrowserFailure("network", "blob:http://foreign.invalid/download", "net::ERR_ABORTED", context), false);
});
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

for (const endpoint of ["/assistant/history", "/documents/view"]) test(`bound ${endpoint} cancellation requires an observed main-document navigation`, () => {
  const path = `${endpoint}?limit=25&owner_document_key=spec_test`;
  const navigated = { ...context, documentChanged: true };
  assert.equal(expectedBrowserFailure("network", context.serviceUrl + path, "net::ERR_ABORTED", navigated), true);
  assert.equal(expectedBrowserFailure("network", context.serviceUrl + path, "net::ERR_ABORTED", context), false);
  assert.equal(expectedBrowserFailure("network", context.serviceUrl + path, "net::ERR_FAILED", navigated), false);
  assert.equal(expectedBrowserFailure("network", "http://foreign.invalid" + path, "net::ERR_ABORTED", navigated), false);
  assert.equal(expectedBrowserFailure("network", context.serviceUrl + endpoint + "?limit=25", "net::ERR_ABORTED", navigated), false);
  assert.equal(expectedBrowserFailure("network", context.serviceUrl + "/transactions?owner_document_key=spec_test", "net::ERR_ABORTED", navigated), false);
  assert.equal(expectedBrowserFailure("console", context.serviceUrl + path, "500 Internal Server Error", navigated), false);
});
