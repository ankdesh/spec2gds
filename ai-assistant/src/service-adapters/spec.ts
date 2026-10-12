import { ServiceAdapter } from "./metadata.js";
/** Known Spec service API actions. This adapter grants no capabilities. */
export const specActions = {
  "health": {
    "method": "GET",
    "path": "/health",
    "parameters": {
      "path": [],
      "query": [],
      "body": []
    },
    "response_kind": "object"
  },
  "capabilities": {
    "method": "GET",
    "path": "/assistant/capabilities",
    "parameters": {
      "path": [],
      "query": [],
      "body": []
    },
    "response_kind": "object"
  },
  "list_documents": {
    "method": "GET",
    "path": "/documents",
    "parameters": {
      "path": [],
      "query": [],
      "body": []
    },
    "response_kind": "object"
  },
  "create_document": {
    "method": "POST",
    "path": "/documents/create",
    "parameters": {
      "path": [],
      "query": [],
      "body": [
        "path",
        "document_id",
        "title",
        "request_id",
        "derive_named_path"
      ]
    },
    "response_kind": "object"
  },
  "resolve_document": {
    "method": "GET",
    "path": "/documents/resolve",
    "parameters": {
      "path": [],
      "query": [
        "name",
        "document_id",
        "owner_document_key"
      ],
      "body": []
    },
    "response_kind": "object"
  },
  "snapshot": {
    "method": "GET",
    "path": "/documents/snapshot",
    "parameters": {
      "path": [],
      "query": [
        "owner_document_key"
      ],
      "body": []
    },
    "response_kind": "object"
  },
  "names": {
    "method": "GET",
    "path": "/documents/names",
    "parameters": {
      "path": [],
      "query": [
        "document_id",
        "entity_kind",
        "entity_id",
        "owner_document_key"
      ],
      "body": []
    },
    "response_kind": "object"
  },
  "context_entity": {
    "method": "GET",
    "path": "/assistant/context",
    "parameters": {
      "path": [],
      "query": [
        "document_id",
        "entity_kind",
        "entity_id",
        "owner_document_key",
        "paged",
        "cursor",
        "entity_ids"
      ],
      "body": []
    },
    "response_kind": "object"
  },
  "context_document": {
    "method": "GET",
    "path": "/assistant/context/document",
    "parameters": {
      "path": [],
      "query": [
        "document_id",
        "owner_document_key",
        "paged",
        "cursor",
        "entity_ids"
      ],
      "body": []
    },
    "response_kind": "object"
  },
  "operation_schema": {
    "method": "GET",
    "path": "/assistant/operation-schema",
    "parameters": {
      "path": [],
      "query": [
        "document_id",
        "scope",
        "entity_kind",
        "entity_id",
        "owner_document_key"
      ],
      "body": []
    },
    "response_kind": "object"
  },
  "preview_proposal": {
    "method": "POST",
    "path": "/assistant/proposals/preview",
    "parameters": {
      "path": [],
      "query": [
        "owner_document_key"
      ],
      "body": [
        "schema_version",
        "kind",
        "proposal_id",
        "document_id",
        "scope",
        "target",
        "base_source_revision_hash",
        "title",
        "summary",
        "rationale",
        "assumptions",
        "operations"
      ]
    },
    "response_kind": "object"
  },
  "stage_proposal": {
    "method": "POST",
    "path": "/assistant/proposals/stage",
    "parameters": {
      "path": [],
      "query": [
        "owner_document_key",
        "session_id"
      ],
      "body": [
        "schema_version",
        "kind",
        "proposal_id",
        "document_id",
        "scope",
        "target",
        "base_source_revision_hash",
        "title",
        "summary",
        "rationale",
        "assumptions",
        "operations"
      ]
    },
    "response_kind": "object"
  },
  "submit_proposal": {
    "method": "POST",
    "path": "/assistant/proposals/submit",
    "parameters": {
      "path": [],
      "query": [
        "owner_document_key",
        "session_id"
      ],
      "body": [
        "schema_version",
        "kind",
        "proposal_id",
        "document_id",
        "scope",
        "target",
        "base_source_revision_hash",
        "title",
        "summary",
        "rationale",
        "assumptions",
        "operations"
      ]
    },
    "response_kind": "object"
  },
  "apply_proposal": {
    "method": "POST",
    "path": "/assistant/proposals/apply",
    "parameters": {
      "path": [],
      "query": [
        "owner_document_key"
      ],
      "body": [
        "schema_version",
        "kind",
        "proposal_id",
        "document_id",
        "scope",
        "target",
        "base_source_revision_hash",
        "title",
        "summary",
        "rationale",
        "assumptions",
        "operations"
      ]
    },
    "response_kind": "object"
  },
  "proposal_receipt": {
    "method": "GET",
    "path": "/assistant/proposals/{proposal_id}",
    "parameters": {
      "path": [
        "proposal_id"
      ],
      "query": [
        "owner_document_key"
      ],
      "body": []
    },
    "response_kind": "object"
  },
  "approve_proposal": {
    "method": "POST",
    "path": "/assistant/proposals/{proposal_id}/approve",
    "parameters": {
      "path": [
        "proposal_id"
      ],
      "query": [
        "owner_document_key"
      ],
      "body": []
    },
    "response_kind": "object"
  },
  "reject_proposal": {
    "method": "POST",
    "path": "/assistant/proposals/{proposal_id}/reject",
    "parameters": {
      "path": [
        "proposal_id"
      ],
      "query": [
        "owner_document_key"
      ],
      "body": []
    },
    "response_kind": "object"
  },
  "changes": {
    "method": "GET",
    "path": "/assistant/changes",
    "parameters": {
      "path": [],
      "query": [
        "owner_document_key"
      ],
      "body": []
    },
    "response_kind": "object"
  },
  "resolve_interface": {
    "method": "POST",
    "path": "/assistant/resolve-interface",
    "parameters": {
      "path": [],
      "query": [],
      "body": [
        "ports",
        "parameters",
        "systemverilog",
        "overrides"
      ]
    },
    "response_kind": "object"
  }
} as const;

export const specAdapter = new ServiceAdapter("spec", specActions);
