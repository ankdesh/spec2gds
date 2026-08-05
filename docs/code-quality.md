# Code-quality conventions

First-party production modules explain their ownership boundary, public
contracts, invariants, security decisions, and non-obvious algorithms through
module documentation, Python docstrings, TSDoc, or focused inline comments.
Comments should explain why a constraint exists rather than repeat syntax.
Generated bundles, generated schemas, dependencies, and routine test setup are
not hand-commented.

Python code must pass Ruff's unused/import checks and Vulture's high-confidence
dead-code scan:

```bash
uv run ruff check spec2gds runtime/src
uv run vulture spec2gds runtime/src --min-confidence 90

cd ai-assistant
uv run python -m ruff check src
uv run python -m vulture src --min-confidence 90
```

TypeScript enables `noUnusedLocals` and `noUnusedParameters` in both UI
workspaces. Workspace builds are therefore the unused-code gate. Dynamic HTTP
routes, package exports, and CLI entrypoints are removed only after tests or
their declared entrypoint prove they are no longer required.

Compatibility aliases are not retained. The supported public contracts use the
current AI Assistant name and discriminated port-family inputs. Unsupported old
formats remain rejected by generic validation rather than being normalized by
adapters.
