"""Unified workflow adapter exposing the three required integration functions."""
from __future__ import annotations

from typing import Any, Dict

from workflow_backend import WorkflowBackendError, build_workflow_backend


_backend = build_workflow_backend()


class WorkflowAdapterError(RuntimeError):
    """Application-level workflow adapter error."""


def runworkflow(user_input: str) -> str:
    """Start workflow and return run_id."""
    if not isinstance(user_input, str) or not user_input.strip():
        raise WorkflowAdapterError("user_input must be a non-empty string")
    try:
        return _backend.runworkflow(user_input.strip())
    except WorkflowBackendError as exc:
        raise WorkflowAdapterError(str(exc)) from exc


def getflowinfo(run_id: str) -> Dict[str, Any]:
    """Get workflow state dictionary by run_id."""
    if not isinstance(run_id, str) or not run_id.strip():
        raise WorkflowAdapterError("run_id must be a non-empty string")
    try:
        return _backend.getflowinfo(run_id.strip())
    except WorkflowBackendError as exc:
        raise WorkflowAdapterError(str(exc)) from exc


def resumeflow(user_input: str, run_id: str) -> None:
    """Resume interrupted workflow with follow-up user input."""
    if not isinstance(user_input, str) or not user_input.strip():
        raise WorkflowAdapterError("user_input must be a non-empty string")
    if not isinstance(run_id, str) or not run_id.strip():
        raise WorkflowAdapterError("run_id must be a non-empty string")

    try:
        _backend.resumeflow(user_input.strip(), run_id.strip())
    except WorkflowBackendError as exc:
        raise WorkflowAdapterError(str(exc)) from exc
