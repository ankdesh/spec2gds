# Code-quality conventions

First-party production modules explain their ownership boundary, public
contracts, invariants, security decisions, and non-obvious algorithms through
module documentation, Python docstrings, TSDoc, or focused inline comments.
Comments should explain why a constraint exists rather than repeat syntax.
Generated bundles, generated schemas, dependencies, and routine test setup are
not hand-commented.

Every production Python module starts with a module docstring that tells a new
reader what boundary the file owns. Public services and non-obvious algorithms
also carry docstrings. Large collections of data-only Pydantic models may use
section comments and a module-level reading guide instead of repeating each
field name in a class docstring; the actual field declarations and `model_config` remain the
authoritative wire contract. Some Planner models deliberately ignore extra
fields; comments must not claim strict recursive validation where it is absent.

Python code must pass Ruff's unused/import checks and Vulture's high-confidence
dead-code scan:

```bash
uv run ruff check spec2gds runtime/src
uv run vulture spec2gds runtime/src --min-confidence 90

cd ai-assistant
npm run typecheck
npm test
```

TypeScript enables `noUnusedLocals` and `noUnusedParameters` in both UI
workspaces. Workspace builds are therefore the unused-code gate. Dynamic HTTP
routes, package exports, and CLI entrypoints are removed only after tests or
their declared entrypoint prove they are no longer required.

## Reviewer comments

Explain the mutation owner, authored revision, claim/replay ordering, crash window,
capability ceiling and meaning of a returned receipt near the relevant code.
Document algorithms at their input/output boundary and keep explicit limitations
beside partial validators. A plugin output writer is not process isolation; a
checkpoint digest is not a signature; inbox acceptance is not completed work.

Comment substantial functions and module reading paths, not every assignment.
Avoid hand-editing generated bundles/types, copied dependencies or fixture output.
When consolidating comments, verify the source behavior remains unchanged with
Python AST/TypeScript token comparison and relevant test/build commands. Prompt
text changes need their own contract checks because they affect model behavior.

Planner source currently has pre-existing import/unused lint findings; do not
claim its package passes the root-only Ruff/Vulture commands above. Its acceptance
suite is invoked separately with `uv run python -m pytest testplan-service/tests -q`.
