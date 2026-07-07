# Coding Guidelines

These guidelines capture repository-specific expectations for future work.

## Python Environment

- Use `uv` for dependency management and command execution.
- Use the project virtual environment created by `uv`; do not document ad hoc
  global Python installs.
- Prefer commands in this form:

```bash
uv run python -m pytest -q
```

For restricted environments, keep uv state local to the repository:

```bash
UV_CACHE_DIR="$PWD/.uv-cache" \
UV_PYTHON_INSTALL_DIR="$PWD/.uv-python" \
uv run python -m pytest -q
```

## Documentation

- Keep durable project notes in `docs/`.
- Update `README.md` when setup, run, or usage commands change.
- Keep architecture docs focused on the current system.
- Put future plans and open questions in roadmap docs, not in current
  architecture docs.
- Keep vocabulary terms aligned with code names and user-facing labels.

## Code Style

- Follow existing package boundaries before adding new abstractions.
- Use Pydantic models for API and persistence contracts that cross module
  boundaries.
- Keep public contracts and non-obvious logic documented with useful docstrings
  or short comments.
- Prefer explicit errors and diagnostics over silent fallback when saving or
  mutating `.spec` documents.
- Preserve user data and custom `spec_data/` package entries unless the caller
  explicitly asks to delete them.

## Testing

- Add focused tests for changes to archive persistence, document parsing,
  graph projection, action contracts, run/writeback behavior, and editor save
  flow.
- Use the existing test layout under `tests/agent_spec/`.
- Keep generated benchmark artifacts intentional and documented when they are
  checked in.

## Documentation Ownership

| Topic | File |
| --- | --- |
| Project overview and commands | `README.md` |
| Current component architecture | `docs/agent_spec_architecture.md` |
| Action/run/writeback contracts | `docs/agent_spec_action_contract.md` |
| Shared terms | `docs/agent_spec_vocabulary.md` |
| Current setup and tests | `docs/agent_spec_v1_setup.md` |
| Roadmap and open questions | `docs/agent_spec_roadmap_questions.md` |
| Code layout | `docs/agent_spec_code_organization.md` |
