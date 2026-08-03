# spec2gds

`spec2gds` is a specification-first hardware design workspace. It combines a
structured specification editor, an independent circuit editor, and an
optional review-oriented assistant.

The repository no longer ships a gallery of demos or benchmark corpora. New
sample applications are developed one at a time through the complete system,
then kept only when they remain useful and reproducible.

## System at a glance

```mermaid
flowchart LR
    User["Designer"] --> SpecUI["Specification editor"]
    SpecUI --> SpecAPI["Spec API"]
    SpecAPI --> Package[".spec package<br/>IP-XACT + narrative + assets"]
    SpecAPI -->|"source-owned projection"| CircuitAPI["Circuit service"]
    CircuitUI["Circuit Designer"] --> CircuitAPI
    CircuitAPI --> CircuitFile[".circuit.json<br/>client-owned file"]
    User --> CircuitUI
    Assistant["Optional assistant"] -->|"reviewed proposals"| SpecAPI
    Assistant -->|"reviewed proposals"| CircuitAPI
```

The two editors have different source-of-truth rules:

- A `.spec` package is owned and saved by the Spec API.
- A local circuit is owned by its client and saved as `.circuit.json`.
- A circuit projected from a specification is read-only in Circuit Designer;
  changes return to the specification source.
- Assistant changes are proposals until a user accepts them.

See [the documentation index](docs/README.md) for the architecture and flow
details.

## Run the specification editor

Python development uses `uv` and the repository virtual environment.

```bash
uv sync
uv run spec2gds-server
```

Open <http://127.0.0.1:8000/editor>. Use **File → New Specification** or
**File → Open Specification** and enter a server-local `.spec` path. The File
menu can also refresh the active package from disk; accepted changes are saved
automatically. **New Specification** refuses to replace an existing path.

The **Circuit** menu lists available designs and components. Eligible document
sections also expose **Options → Open circuit** beside their headings, while
**Options → More actions** opens the entity action workflow. The server exposes
interactive API docs at <http://127.0.0.1:8000/docs>.

For frontend work:

```bash
# terminal 1
uv run spec2gds-server --reload

# terminal 2
cd circuit-designer
npm install
npm run dev:editor
```

Open <http://127.0.0.1:4190>. Rebuild the Python-packaged editor with
`npm run build:editor` before committing UI changes.

## Run Circuit Designer

Node.js 24 or newer is required.

```bash
cd circuit-designer
npm install
npm run dev
```

Open <http://127.0.0.1:4180>. The app starts with an empty circuit. Use
**Unlock** to edit it, **Save** to accept the draft and download a canonical
file, or **Open file** to load an existing `.circuit.json`.

To use **Open circuit** from the specification editor, run both services. The
default Spec API (`8000`) and Circuit service (`4100`) already use compatible
settings.

## Optional assistant

```bash
cd external-assistant
uv sync
cd web && npm install && cd ..
export OPENAI_API_KEY="..."
uv run spec2gds-external-assistant
```

The assistant is optional and does not sit on either editor's critical path.
See [external-assistant/README.md](external-assistant/README.md).

## Verify changes

```bash
uv run python -m pytest -q

cd circuit-designer
npm run generate:check
npm test
npm run test:e2e          # Circuit Designer only
npm run test:e2e:editor   # specification editor only

cd ../external-assistant
uv run python -m pytest -q
cd web && npm run build
```

Detailed source locations and focused commands are in
[docs/development.md](docs/development.md).
