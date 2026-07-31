# spec2gds External Assistant

An independent local assistant-ui application that explores and proposes
reviewable Circuit Designer and Spec Editor changes through one A2A service.

The project is optional: Circuit Designer and Spec Editor continue to build and
run without it.

## Development setup

Requirements:

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Node.js 24+ and npm
- A running Circuit Designer and/or Spec Editor service

```bash
cd external-assistant
uv sync
cd web
npm install
```

Set the OpenAI API key:

```bash
export OPENAI_API_KEY="..."
```

`OPENAI_MODEL` defaults to `gpt-4o-mini`.

Run the backend:

```bash
cd external-assistant
uv run spec2gds-external-assistant
```

Run the frontend development server in another terminal:

```bash
cd external-assistant/web
npm run dev
```

Open `http://127.0.0.1:4201`. The frontend proxies local API and A2A requests
to FastAPI on port `4200`.

For a single-process local run, build the frontend first:

```bash
cd external-assistant/web
npm run build
cd ..
uv run spec2gds-external-assistant
```

Then open `http://127.0.0.1:4200`. FastAPI serves `web/dist` when it exists.

For Circuit work, create a chat and connect it to:

```text
http://127.0.0.1:4100/api/circuit-designer/v1
```

and the current Circuit Designer document ID. Each request sends the current
semantic snapshot and SVG to the A2A agent. PNG context is opt-in.

For Spec work, start the Spec API on port 8000 and use **Explore with
assistant** on a component, design, bus definition, abstraction definition, or
narrative block. The editor opens `/launch/spec`; every launch creates a new
chat permanently bound to that document and entity. Exploration remains
conversational until **Prepare proposal** is selected or the user explicitly
asks for a proposal.

The external UI previews current and proposed `DocumentSection` projections.
Approval immediately asks the Spec API to revalidate, atomically update the
active `.spec`, and store the accepted decision. The open Spec Editor then shows
a refresh banner without replacing its current snapshot.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | none | Required when generating proposals |
| `OPENAI_MODEL` | `gpt-4o-mini` | Structured-output model |
| `ASSISTANT_HOST` | `127.0.0.1` | FastAPI bind host |
| `ASSISTANT_PORT` | `4200` | FastAPI port |
| `ASSISTANT_DATABASE_PATH` | `data/assistant.db` | Chat, review, and A2A SQLite database |
| `ASSISTANT_WEB_DIST_PATH` | `web/dist` | Optional production web bundle |
| `CIRCUIT_REQUEST_TIMEOUT_SECONDS` | `30` | Circuit Designer request timeout |
| `SPEC_REQUEST_TIMEOUT_SECONDS` | `30` | Spec Editor request timeout |
| `SPEC_SERVICE_ALLOWLIST` | `http://127.0.0.1:8000,http://localhost:8000` | Spec service origins permitted for server-side requests |

Circuit Designer URLs are restricted to loopback HTTP endpoints. Spec URLs must
be loopback HTTP and exactly match the allowlist. The reference service has no
user authentication and is intended for a trusted local environment.

The Spec service launch response also uses:

| Variable | Default | Purpose |
| --- | --- | --- |
| `EXTERNAL_ASSISTANT_URL` | `http://127.0.0.1:4200` | External assistant origin opened by Spec Editor |
| `SPEC_EDITOR_SERVICE_URL` | `http://127.0.0.1:8000` | Spec API origin permanently bound to a launched chat |

## Tests

```bash
cd external-assistant
uv run pytest
cd web
npm run build
```

See [docs/architecture.md](docs/architecture.md) for the data flow and
[docs/protocol.md](docs/protocol.md) for the proposal contract. Verification
details are in [docs/testing.md](docs/testing.md). The complete Spec ownership,
preview, apply, provenance, and refresh design is documented in
[`../docs/spec-assistant-integration.md`](../docs/spec-assistant-integration.md).
