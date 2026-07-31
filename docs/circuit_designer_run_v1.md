# Running Independent Circuit Designer v1

Node.js 24 is the supported runtime.

Read [Circuit Designer v1 Design and Architecture](circuit_designer_architecture_v1.md)
before embedding the service in another application. The service keeps active
sessions in memory; it is not a file server or durable database.

## Start the complete development system

```bash
cd circuit-designer
npm install
npm run generate:check
npm test
npm run dev
```

`npm run dev` starts:

- the ephemeral REST service on `127.0.0.1:4100`;
- the Vite/React web client on `127.0.0.1:4180`.

Open <http://127.0.0.1:4180>. Vite proxies `/api` requests to the REST service.
Stopping or restarting the service discards every active circuit session.

To run the processes separately:

```bash
# terminal 1
npm run service

# terminal 2
npm run dev:standalone
```

Only `CIRCUIT_DESIGNER_HOST` and `CIRCUIT_DESIGNER_PORT` configure the service.
There is no database configuration.

The browser uses `/api/circuit-designer/v1` by default. Set
`VITE_CIRCUIT_DESIGNER_API_BASE` when the browser build must call a different
same-origin or reverse-proxied base path.

## Open and save circuit files

1. Select **Open file** and choose a UTF-8 `.json` or `.circuit.json` file
   containing one canonical `CircuitDocument`.
2. Invalid JSON or an invalid circuit is reported without replacing the
   current document.
3. Unlock to create a private draft.
4. **Save** commits the draft and downloads the accepted document.
5. **Download file** downloads the current committed document without editing.

Every saved file is named `<document_id>.circuit.json`. The browser does not
overwrite files in place and the app does not use IndexedDB.

SVG and PNG remain explicit exports derived from the active committed design.

## Service-only use

SpecIR translators, chat-agent hosts, and automation do not use React. Start
`npm run service` and call the REST root directly:

```text
http://127.0.0.1:4100/api/circuit-designer/v1
```

The caller must reload its durable source after a service restart.

## Production composition

Build the workspace with `npm run build`, serve
`apps/standalone/dist/` as static content, and reverse-proxy
`/api/circuit-designer/v1` to the Node service. The reference service is
loopback-only and unauthenticated by default; authentication and remote
deployment policy are outside v1.

## Useful checks

```bash
npm run generate
npm run generate:check
npm run build
TMPDIR=/tmp npm test
npm run test:e2e
```

The explicit `TMPDIR` is helpful when a Linux shell inherits a non-existent
Windows temporary-directory path.
