"""Centralized configuration constants for Verification Planner service."""

from __future__ import annotations

import os

# Service identification & networking defaults
DEFAULT_SERVICE_NAME: str = "verification-planner"
DEFAULT_PRODUCT_TITLE: str = "Verification Planner"
DEFAULT_SERVICE_VERSION: str = "1.0.0"
DEFAULT_SERVICE_HOST: str = "127.0.0.1"
DEFAULT_SERVICE_PORT: int = 6016
DEFAULT_STORAGE_DIR: str = os.getenv("VERIFICATION_STORAGE_DIR", "verification-data")
LEGACY_STORAGE_DIR: str = ".testplans"

# API Paths
API_BASE_PATH: str = "/api/verification/v1"

# Schema Versions
SCHEMA_VERSION_PLAN: str = "verification.plan.v1"
SCHEMA_VERSION_COVERAGE: str = "verification.coverage.v1"
SCHEMA_VERSION_TEST_IR: str = "verification.test-ir.v1"
SCHEMA_VERSION_PRODUCER: str = "verification.producer.v1"
SCHEMA_VERSION_GENERATION_REQUEST: str = "verification.generation-request.v1"
SCHEMA_VERSION_GENERATION_RESULT: str = "verification.generation-result.v1"
SCHEMA_VERSION_RESULTS: str = "verification.results.v1"
SCHEMA_VERSION_REPORT: str = "verification.evidence-report.v1"
SCHEMA_VERSION_BUNDLE: str = "verification.bundle.v1"
ACTIVITY_SNAPSHOT_SCHEMA: str = "spec2gds.activity-snapshot.v1"
ACTIVITY_SNAPSHOT_MIMETYPE: str = "application/vnd.spec2gds.activity-snapshot.v1+zip"

# Data constraints and limits
MAX_HIERARCHY_DEPTH: int = 32
MAX_INTENTS_LIMIT: int = 10000
MAX_REQUIREMENTS_LIMIT: int = 20000
MAX_OBJECTIVES_LIMIT: int = 20000
MAX_BINS_PER_PLAN: int = 100000
MAX_BINS_PER_ACTION: int = 1000
MAX_OPERATIONS_PER_BATCH: int = 500
MAX_PAYLOAD_SIZE_BYTES: int = 2 * 1024 * 1024  # 2 MiB
MAX_SOURCE_UPLOAD_BYTES: int = 100 * 1024 * 1024  # 100 MiB
MAX_EXPANDED_SOURCE_BYTES: int = 500 * 1024 * 1024  # 500 MiB
MAX_ARCHIVE_ENTRIES: int = 10000
MAX_TITLE_LENGTH: int = 200
MAX_TEXT_LENGTH: int = 16000
MAX_TAGS_COUNT: int = 20
MAX_TAG_LENGTH: int = 40

# Generation & Execution limits
DEFAULT_MAX_SIMULATED_EDGES: int = 100_000
DEFAULT_MAX_EVALUATED_STEPS: int = 1_000_000
DEFAULT_EXTERNAL_RUNTIME_TIMEOUT_SECONDS: int = 60
MAX_GENERATION_OUTPUT_BYTES: int = 512 * 1024 * 1024  # 512 MiB

# Key Prefixes
KEY_PREFIX_REQ: str = "REQ"
KEY_PREFIX_SEC: str = "SEC"
KEY_PREFIX_INT: str = "INT"
KEY_PREFIX_ISS: str = "ISS"
KEY_PREFIX_OBJ: str = "OBJ"
KEY_PREFIX_DIM: str = "DIM"
KEY_PREFIX_POL: str = "POL"
KEY_PREFIX_RCP: str = "RCP"
KEY_PREFIX_BIND: str = "BND"
KEY_PREFIX_BCFG: str = "BCFG"
KEY_PREFIX_CHK_PLAN: str = "P"
KEY_PREFIX_CHK_COVERAGE: str = "C"
KEY_PREFIX_CHK_IMPLEMENTATION: str = "I"
KEY_PREFIX_CHK: str = "P"

# Design Token Palette (Blueprint Slate)
COLOR_CHROME: str = "#081f33"
COLOR_CANVAS: str = "#f7f9fc"
COLOR_SURFACE: str = "#ffffff"
COLOR_SURFACE_MUTED: str = "#eef3f8"
COLOR_TEXT: str = "#102a43"
COLOR_MUTED_TEXT: str = "#52667a"
COLOR_BORDER: str = "#c8d3df"
COLOR_PRIMARY: str = "#007c89"
COLOR_PLAN_ACCENT: str = "#1d64c8"
COLOR_COVERAGE_ACCENT: str = "#007c89"
COLOR_IMPLEMENTATION_ACCENT: str = "#6550a1"
COLOR_SUCCESS: str = "#17653a"
COLOR_WARNING: str = "#895300"
COLOR_DANGER: str = "#b42318"
COLOR_NEUTRAL: str = "#52667a"
COLOR_FOCUS: str = "#16709a"
