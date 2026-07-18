"""IP-XACT-centered hardware specification tooling.

The public implementation lives in :mod:`spec2gds.agent_spec.spec_format`.
Keeping this package initializer free of eager imports is intentional: callers
can use the source model, CLI, or API independently without loading the web
stack or creating hidden compatibility ties to the removed ODT prototype.
"""

__all__: list[str] = []
