"""Centralized configuration values and constants for Testplan Service."""

from __future__ import annotations

# Service networking defaults
DEFAULT_SERVICE_HOST: str = "0.0.0.0"
DEFAULT_SERVICE_PORT: int = 6016
DEFAULT_SERVICE_NAME: str = "testplan-service"
DEFAULT_SERVICE_VERSION: str = "0.1.0"
SERVICE_CAPABILITIES: tuple[str, ...] = (
    "hierarchical_testplan",
    "coverage_taxonomy",
    "crud_nodes",
    "assistant_proposals",
    "batch_operations",
    "export_import",
)

# API Prefixes and Paths
API_V1_PREFIX: str = "/api/v1"
ASSISTANT_PREFIX: str = "/assistant"
DOCUMENTS_PREFIX: str = "/documents"

# Data constraints
MAX_TREE_DEPTH: int = 10
MAX_TITLE_LENGTH: int = 256
MAX_DESCRIPTION_LENGTH: int = 32768
MAX_TAGS_COUNT: int = 50
MAX_NODES_PER_PLAN: int = 2000

# Assistant Proposal Actions
ACTION_ADD_NODE: str = "add_node"
ACTION_UPDATE_NODE: str = "update_node"
ACTION_DELETE_NODE: str = "delete_node"
ACTION_MOVE_NODE: str = "move_node"
VALID_PROPOSAL_ACTIONS: frozenset[str] = frozenset({
    ACTION_ADD_NODE,
    ACTION_UPDATE_NODE,
    ACTION_DELETE_NODE,
    ACTION_MOVE_NODE,
})

# Storage defaults
DEFAULT_STORAGE_DIR: str = ".testplans"
DEFAULT_STORAGE_FILENAME: str = "testplans.json"
