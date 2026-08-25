# Service configuration

The three applications share the tracked registry at
[`config/services.json`](../config/services.json). It is the single default
source for bind addresses, API base paths, and browser UI locations.

`public_host` controls the hostname or IP address advertised to browsers.
`"auto"` selects the machine's preferred LAN IPv4 address; set
`SPEC2GDS_PUBLIC_HOST` to a resolvable hostname or explicit address when a WSL,
VPN, container, or multi-interface host needs a different value. Endpoint
`host` values are bind addresses and default to `0.0.0.0`.

Each application has a `service` endpoint and a `ui` endpoint. Spec Editor and
AI Assistant serve their UI from the same listener as their API. Circuit
Designer uses two listeners: its REST service defaults to port `6011` and its
Vite UI defaults to port `6012`.

`circuit_designer.preferences_file` selects the shared Circuit Designer JSON
preference profile and is resolved relative to this configuration file. The
tracked value resolves to `generated/circuit-designer/preferences.json`.
`CIRCUIT_DESIGNER_PREFERENCES_FILE` overrides it with an absolute or
working-directory-relative path. See
[Circuit Designer preferences](circuit-designer-preferences.md).

The default allocation is Spec Editor `6010`, Circuit API `6011`, Circuit UI
`6012`, AI Assistant `6013`, and Log Viewer `6014`. Development-only Vite UIs
use `6015` and `6016`. The schema also contains the unified logging policy.
Logging has only two environment overrides:

- `SPEC2GDS_LOGGING=ON|OFF`
- `SPEC2GDS_LOG_LEVEL=info|debug`

The file path, maximum size, and viewer port are configuration-file-only. The
single active file retains its newest complete entries when it reaches the
limit; the logger does not create backup files.

## Activity host

The `activities` object configures the Spec Editor's background Activity host:

```json
{
  "activities": {
    "workspace_root": "../generated",
    "extension_modules": []
  }
}
```

`workspace_root` is resolved relative to the configuration file. Generated RTL
and SystemC projects are published below this root. The host also owns
`.spec2gds/activity-jobs.sqlite3` and `.spec2gds/snapshots/` there; keep those
files when restarting the service so queued and interrupted jobs can resume.
Only one Activity executes at a time to serialize generators that may own the
same output directory.

`extension_modules` is an explicit list of `module:callable` registrations.
Each callable receives the product Activity registry. Import and registration
failures appear in `GET /activities` and in the Spec Editor launch dialog; they
do not prevent the built-in `rtl.generate` and
`systemc.generate_at_skeleton` Activities from loading. A service restart is
required after changing either setting.

Edit the complete JSON file when an address changes. A service restart is
required afterward. Frontend development servers also read the file when they
start. Set `SPEC2GDS_SERVICE_CONFIG` to use another absolute JSON file without
modifying the tracked local defaults.

Existing per-service environment variables remain higher-priority overrides:

- `AGENT_SPEC_HOST`, `AGENT_SPEC_PORT`, and `SPEC_EDITOR_SERVICE_URL`
- `CIRCUIT_DESIGNER_HOST`, `CIRCUIT_DESIGNER_PORT`,
  `CIRCUIT_DESIGNER_SERVICE_URL`, `CIRCUIT_DESIGNER_UI_URL`, and
  `CIRCUIT_DESIGNER_PREFERENCES_FILE`
- `ASSISTANT_HOST`, `ASSISTANT_PORT`, and `AI_ASSISTANT_URL`

`SPEC2GDS_PUBLIC_HOST` is the shared advertised-host override. Bind overrides
and URL overrides remain separate so a wildcard listener is never emitted as a
browser destination.

The Assistant derives its Spec and Circuit allowlists from the resolved
registry. `SPEC_SERVICE_ALLOWLIST` and `CIRCUIT_SERVICE_ALLOWLIST` can further
override those values. This permits a configured LAN IP while still rejecting
an arbitrary URL supplied by a browser request.

## Discovery and direct launch

- Spec Editor exposes `GET /services`.
- Spec Editor exposes `GET /activities`, entity-scoped availability endpoints,
  durable execution endpoints, and `GET /activity-events` for live status.
- Circuit Designer exposes `GET /api/circuit-designer/v1/services` and
  `/health`.
- AI Assistant exposes `GET /api/services`, probes both owning services, and
  reports `Available` or `Not detected` in its workspace chooser.

The **AI Assistant ↗** button in Spec Editor opens the Assistant with the Spec
workspace selected. Entity-level **Explore with AI Assistant** remains the
recommended route because it can bind the exact IP-XACT entity.

Circuit Designer's **Tools → AI Assistant** command sends the active document
ID and configured Circuit API URL to `/launch/circuit`; the Assistant validates
the document and opens a new circuit-bound chat directly.

The combined `scripts/serve-all.sh` launcher starts services with these
resolved settings, but its printed links and its untracked-listener cleanup are
limited to the tracked default ports. When using a custom registry, use that
registry's URLs and stop any custom-port listener through its owning process if
it is not represented by a launcher PID file.

For LAN use, allow the selected ports through the server's host firewall and
open the advertised URLs from the other systems.
