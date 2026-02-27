"""Application configuration for workflow chat service."""
from __future__ import annotations

import os


class Config:
    """Centralized configuration."""

    # Flask
    FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    SECRET_KEY = os.getenv("SECRET_KEY", "workflow-dev-secret")

    # Async processing
    MAX_ASYNC_WORKERS = int(os.getenv("MAX_ASYNC_WORKERS", "10"))
    WORKFLOW_POLL_INTERVAL_SECONDS = float(os.getenv("WORKFLOW_POLL_INTERVAL_SECONDS", "1"))

    # Session
    MAX_SESSIONS = int(os.getenv("MAX_SESSIONS", "1000"))
    MAX_MESSAGES_PER_SESSION = int(os.getenv("MAX_MESSAGES_PER_SESSION", "200"))

    # Memory/cache protection
    MAX_SNAPSHOT_CACHE_SIZE = int(os.getenv("MAX_SNAPSHOT_CACHE_SIZE", "5000"))
    MAX_TASK_HISTORY = int(os.getenv("MAX_TASK_HISTORY", "5000"))

    # Workflow
    WORKFLOW_BACKEND = os.getenv("WORKFLOW_BACKEND", "mock")
