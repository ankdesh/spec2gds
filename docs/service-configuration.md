# Service configuration

The three applications share the tracked registry at
[`config/services.json`](../config/services.json). It is the single default
source for bind addresses, API base paths, and browser UI locations.

Each application has a `service` endpoint and a `ui` endpoint. Spec Editor and
AI Assistant serve their UI from the same listener as their API. Circuit
Designer uses two listeners: its REST service defaults to port `4100` and its
Vite UI defaults to port `4180`.

Edit the complete JSON file when an address changes. A service restart is
required afterward. Frontend development servers also read the file when they
start. Set `SPEC2GDS_SERVICE_CONFIG` to use another absolute JSON file without
modifying the tracked local defaults.

Existing per-service environment variables remain higher-priority overrides:

- `AGENT_SPEC_HOST`, `AGENT_SPEC_PORT`, and `SPEC_EDITOR_SERVICE_URL`
- `CIRCUIT_DESIGNER_HOST`, `CIRCUIT_DESIGNER_PORT`,
  `CIRCUIT_DESIGNER_SERVICE_URL`, and `CIRCUIT_DESIGNER_UI_URL`
- `ASSISTANT_HOST`, `ASSISTANT_PORT`, and `AI_ASSISTANT_URL`

The Assistant derives its Spec and Circuit allowlists from the resolved
registry. `SPEC_SERVICE_ALLOWLIST` and `CIRCUIT_SERVICE_ALLOWLIST` can further
override those values. This permits a configured LAN IP while still rejecting
an arbitrary URL supplied by a browser request.

## Discovery and direct launch

- Spec Editor exposes `GET /services`.
- Circuit Designer exposes `GET /api/circuit-designer/v1/services` and
  `/health`.
- AI Assistant exposes `GET /api/services`, probes both owning services, and
  reports `Available` or `Not detected` in its workspace chooser.

The **AI Assistant ↗** button in Spec Editor opens the Assistant with the Spec
workspace selected. Entity-level **Explore with AI Assistant** remains the
recommended route because it can bind the exact IP-XACT entity.

The same button in Circuit Designer sends the active document ID and configured
Circuit API URL to `/launch/circuit`; the Assistant validates the document and
opens a new circuit-bound chat directly.
