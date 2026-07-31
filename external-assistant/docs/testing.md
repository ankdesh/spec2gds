# External Assistant Testing

## Python

The Python project uses a uv-managed virtual environment:

```bash
cd external-assistant
uv sync
uv run pytest
```

The tests cover Circuit and Spec context conversion, structured OpenAI output
wiring, SQLite migration and summary rollover, immutable bindings, Circuit
preview-before-send, Spec preview-before-apply, agent-card discovery, and a
complete A2A message/artifact exchange. They mock OpenAI and editor APIs.

## Web application

```bash
cd external-assistant/web
npm install
npm run build
```

The production build performs TypeScript checking and bundles assistant-ui,
the A2A runtime, Circuit Designer's React renderer, and the shared Spec
`DocumentSection` renderer.

## Circuit Designer compatibility

```bash
cd circuit-designer
npm run generate:check
npm run build --workspace @spec2gds/circuit-react
npm run test --workspace @spec2gds/circuit-core
npm run test --workspace @spec2gds/circuit-react
npm run test --workspace @spec2gds/circuit-service
```

Use Node.js 24 as required by the Circuit Designer workspace.

## Spec Editor compatibility

```bash
uv run python -m pytest tests/agent_spec/spec_format/test_v1_api.py -q
cd circuit-designer
TMPDIR=/tmp npm run test --workspace @spec2gds/document-core -- --run
npm run build:editor
```

## Manual smoke test

1. Start Circuit Designer and load or create a document.
2. Start the external assistant backend and frontend.
3. Create a chat and bind it to the Circuit Designer REST root and document ID.
4. Ask for an instance or connectivity change.
5. Confirm that the proposal shows a before/after circuit and exact operations.
6. Confirm that Circuit Designer has not received a proposal yet.
7. Choose **Send to Circuit Designer**.
8. Open Circuit Designer's proposal list and Accept or Reject the pending item.

For Spec, open a supported entity's **Explore with assistant** action. Explore
without creating a draft, choose **Prepare proposal**, inspect both rendered
sections and diagnostics, then approve. Confirm the `.spec` is saved and the
already-open editor displays a refresh banner without refreshing automatically.
