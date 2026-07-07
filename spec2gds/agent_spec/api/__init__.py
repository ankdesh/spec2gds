"""FastAPI surfaces for the agent-spec local server."""

import spec2gds.agent_spec.api.app as app
import spec2gds.agent_spec.api.document_app as document_app

__all__ = ["app", "document_app"]
