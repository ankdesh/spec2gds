# Embedding Circuit Designer

Circuit Designer now has a host-neutral React application package:
`@spec2gds/circuit-app-react`. The standalone browser application is a thin
composition layer around that package; Spec Editor source synchronization and
the AI Assistant are integrations rather than requirements of the shell.

## Build and import

The package is private to this monorepo and publishes compiled JavaScript,
declarations, source maps, and scoped CSS under `dist/`.

```bash
cd circuit-designer
npm run build --workspace @spec2gds/circuit-app-react
```

```tsx
import { CircuitDesignerApp } from "@spec2gds/circuit-app-react";
import "@xyflow/react/dist/style.css";
import "@spec2gds/circuit-react/styles.css";
import "@spec2gds/circuit-app-react/styles.css";

export function EmbeddedCircuitEditor() {
  return <CircuitDesignerApp
    backend={backend}
    events={events}
    files={files}
    launch={{ kind: "document", documentId: "soc-top" }}
    preferences={preferences}
    source={optionalSource}
    telemetry={telemetry}
    tools={hostTools}
  />;
}
```

The host container must have a definite height. The shell fills that container
and adapts its inspector at 960 px; it does not set global `body`, `button`, or
input styles.

## Host adapters

| Prop | Responsibility | Required |
| --- | --- | --- |
| `backend` | Canonical documents, leases, operations, proposals, hierarchy, and exports | yes |
| `files` | Open and write circuit JSON/SVG/PNG using browser, desktop, or host storage | yes |
| `preferences` | Load, save, and optionally cache the shared action profile | yes |
| `events` | Subscribe to live document/proposal changes | no |
| `source` | Load, commit, and reload an authoritative external source | no |
| `telemetry` | Receive structured UI events and global errors | no |
| `tools` | Add host-owned tools such as an assistant | no |
| `launch` | Start with a new document or an existing document ID | no |
| `theme` | Supply a semantic `CircuitThemeDefinition` | no |
| `onLaunchChange` | Let the host synchronize routing/history | no |

The shell never discovers neighboring services and never assumes that an
external source is a `.spec` package. The standalone composition in
`apps/standalone/src` maps the existing HTTP source-binding protocol to the
generic source adapter and contributes the optional Assistant tool.

## Service discovery

The Circuit service can boot with only its own environment variables:

```bash
CIRCUIT_DESIGNER_PORT=6011 npm run service
```

`GET /api/circuit-designer/v1/capabilities` reports portable capabilities and
enabled integrations. The legacy `/services` response is available only when
the host explicitly supplies the shared v2 service directory. Callback hosts
are loopback-only by default; add trusted hosts with the comma-separated
`CIRCUIT_DESIGNER_PROVIDER_ALLOWLIST` variable.

## Ownership rule

Generic circuit semantics remain in `circuit-core`; React canvas behavior is in
`circuit-react`; the reusable application shell is in `circuit-app-react`.
Browser downloads, URL routing, Spec synchronization labels, service URLs, and
Assistant launch behavior belong in an application composition layer.

In npm commands, `--workspace @spec2gds/circuit-app-react` selects the npm package.
