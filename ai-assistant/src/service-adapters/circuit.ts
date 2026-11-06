import { ServiceAdapter } from "./metadata.js";
/** Known circuit service API actions. This adapter grants no capabilities. */
export const circuitActions = {
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
    "path": "/capabilities",
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
  "resolve_document": {
    "method": "GET",
    "path": "/documents/resolve",
    "parameters": {
      "path": [],
      "query": [
        "name"
      ],
      "body": []
    },
    "response_kind": "object"
  },
  "create_document": {
    "method": "POST",
    "path": "/documents/empty",
    "parameters": {
      "path": [],
      "query": [],
      "body": [
        "document_id",
        "label",
        "request_id"
      ]
    },
    "response_kind": "object"
  },
  "context_document": {
    "method": "GET",
    "path": "/documents/{document_id}",
    "parameters": {
      "path": [
        "document_id"
      ],
      "query": [],
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
        "scope"
      ],
      "body": []
    },
    "response_kind": "object"
  },
  "source_binding": {
    "method": "GET",
    "path": "/documents/{document_id}/source-binding",
    "parameters": {
      "path": [
        "document_id"
      ],
      "query": [],
      "body": []
    },
    "response_kind": "object"
  },
  "preview_proposal": {
    "method": "POST",
    "path": "/documents/{document_id}/operations/preview",
    "parameters": {
      "path": [
        "document_id"
      ],
      "query": [],
      "body": [
        "request_id",
        "expected_revision",
        "operations"
      ]
    },
    "response_kind": "object"
  },
  "send_proposal": {
    "method": "POST",
    "path": "/documents/{document_id}/proposals",
    "parameters": {
      "path": [
        "document_id"
      ],
      "query": [],
      "body": [
        "proposal_id",
        "document_id",
        "base_revision",
        "title",
        "summary",
        "rationale",
        "assumptions",
        "batch"
      ]
    },
    "response_kind": "object"
  },
  "list_proposals": {
    "method": "GET",
    "path": "/documents/{document_id}/proposals",
    "parameters": {
      "path": [
        "document_id"
      ],
      "query": [],
      "body": []
    },
    "response_kind": "object"
  },
  "export_svg": {
    "method": "POST",
    "path": "/documents/{document_id}/exports",
    "parameters": {
      "path": [
        "document_id"
      ],
      "query": [],
      "body": [
        "format"
      ]
    },
    "response_kind": "svg"
  },
  "source_renew": {
    "method": "POST",
    "path": "/documents/{document_id}/source/renew",
    "parameters": {
      "path": [
        "document_id"
      ],
      "query": [],
      "body": []
    },
    "response_kind": "object"
  }
} as const;

export const circuitAdapter = new ServiceAdapter("circuit", circuitActions);
