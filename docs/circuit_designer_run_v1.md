# Running Independent Circuit Designer v1

Node.js 24 is the supported runtime.

```bash
cd circuit-designer
npm install
npm run generate:check
npm test
npm run dev
```

Open <http://127.0.0.1:4180>. Unlock creates a private draft. Use Save to commit
the draft atomically or Cancel to discard it. The default app uses the browser
backend and has no Python, SpecIR, IP-XACT, or `.spec` dependency.

Run the reference Node/SQLite service with:

```bash
cd circuit-designer
CIRCUIT_DESIGNER_DATABASE=./circuit-designer.sqlite npm run service
```

It listens on `127.0.0.1:4100` by default. Override
`CIRCUIT_DESIGNER_HOST`, `CIRCUIT_DESIGNER_PORT`, and
`CIRCUIT_DESIGNER_DATABASE` as needed. The REST root is
`/api/circuit-designer/v1`.

Useful checks:

```bash
npm run generate
npm run generate:check
npm run build
TMPDIR=/tmp npm test
```

The explicit `TMPDIR` is helpful when a Linux shell inherits a non-existent
Windows temporary-directory path.
