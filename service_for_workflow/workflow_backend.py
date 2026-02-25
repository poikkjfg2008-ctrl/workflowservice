"""Workflow backend abstractions and adapters."""
from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Protocol, runtime_checkable

from workflow_mock import workflow_service


class WorkflowBackendError(RuntimeError):
    """Raised when workflow backend execution fails."""


@runtime_checkable
class WorkflowBackend(Protocol):
    """Unified backend protocol for workflow execution."""

    def runworkflow(self, user_input: str) -> str:
        ...

    def getflowinfo(self, run_id: str) -> Dict[str, Any]:
        ...

    def resumeflow(self, user_input: str, run_id: str) -> None:
        ...


class MockWorkflowBackend:
    """Built-in mock backend used for local development."""

    def runworkflow(self, user_input: str) -> str:
        return workflow_service.start_workflow(user_input)

    def getflowinfo(self, run_id: str) -> Dict[str, Any]:
        return workflow_service.get_workflow_info(run_id)

    def resumeflow(self, user_input: str, run_id: str) -> None:
        workflow_service.resume_workflow(user_input, run_id)


@dataclass
class ExternalWorkflowFunctionsBackend:
    """Backend adapter around externally provided Python functions."""

    run_func: Callable[[str], str]
    info_func: Callable[[str], Dict[str, Any]]
    resume_func: Callable[[str, str], None]

    def runworkflow(self, user_input: str) -> str:
        run_id = self.run_func(user_input)
        if not isinstance(run_id, str) or not run_id:
            raise WorkflowBackendError("runworkflow must return a non-empty string run_id")
        return run_id

    def getflowinfo(self, run_id: str) -> Dict[str, Any]:
        info = self.info_func(run_id)
        if not isinstance(info, dict):
            raise WorkflowBackendError("getflowinfo must return dict")
        return info

    def resumeflow(self, user_input: str, run_id: str) -> None:
        self.resume_func(user_input, run_id)


def _load_callable(module_name: str, func_name: str) -> Callable[..., Any]:
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # pragma: no cover - startup guard
        raise WorkflowBackendError(f"cannot import module '{module_name}': {exc}") from exc

    func = getattr(module, func_name, None)
    if func is None or not callable(func):
        raise WorkflowBackendError(f"'{func_name}' not found or not callable in module '{module_name}'")
    return func


def build_workflow_backend() -> WorkflowBackend:
    """Build backend from environment configuration."""
    backend = os.getenv("WORKFLOW_BACKEND", "mock").strip().lower()

    if backend == "mock":
        return MockWorkflowBackend()

    if backend == "external":
        module_name = os.getenv("WORKFLOW_EXTERNAL_MODULE", "external_workflow")
        run_name = os.getenv("WORKFLOW_EXTERNAL_RUN_FUNC", "runworkflow")
        info_name = os.getenv("WORKFLOW_EXTERNAL_INFO_FUNC", "getflowinfo")
        resume_name = os.getenv("WORKFLOW_EXTERNAL_RESUME_FUNC", "resumeflow")

        return ExternalWorkflowFunctionsBackend(
            run_func=_load_callable(module_name, run_name),
            info_func=_load_callable(module_name, info_name),
            resume_func=_load_callable(module_name, resume_name),
        )

    raise WorkflowBackendError(
        f"unsupported WORKFLOW_BACKEND={backend!r}, expected 'mock' or 'external'"
    )
