import json
import logging
import os
import time
from typing import Any

from nooa.events import ExecutionResult
from nooa.runtime.sandbox.errors import CellMemoryError, CellTimeoutError

logger = logging.getLogger(__name__)

class SandboxAuditLogger:
    """Real-time Audit Logger for tracking NOOA sandbox executions and violations."""

    def __init__(self, log_file: str = "sandbox_audit.jsonl"):
        self.log_file = log_file

    def _write_event(self, event_type: str, data: dict[str, Any]) -> None:
        payload = {
            "timestamp": time.time(),
            "event_type": event_type,
            **data
        }
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def log_execution_intent(self, agent: Any, code: str) -> str:
        """Log the intent before execution starts."""
        execution_id = f"exec_{int(time.time() * 1000)}"
        agent_id = getattr(agent, "id", str(agent))
        self._write_event("execution_started", {
            "execution_id": execution_id,
            "agent_id": agent_id,
            "code": code
        })
        return execution_id

    def log_execution_result(self, execution_id: str, result: ExecutionResult) -> None:
        """Log the result and detect any security or resource violations."""
        has_error = result.error is not None
        error_msg = str(result.error) if has_error else None
        
        # Check for access/resource violations
        violation = None
        if has_error:
            if isinstance(result.error, PermissionError):
                violation = "FILE_SYSTEM_ACCESS_DENIED"
            elif isinstance(result.error, CellMemoryError):
                violation = "MEMORY_LIMIT_EXCEEDED"
            elif isinstance(result.error, CellTimeoutError):
                violation = "TIMEOUT_EXCEEDED"
            elif "PermissionError" in error_msg or "Permission denied" in error_msg:
                violation = "PERMISSION_DENIED"

        self._write_event("execution_completed", {
            "execution_id": execution_id,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "error": error_msg,
            "violation": violation
        })

        if violation:
            logger.warning(f"SANDBOX VIOLATION DETECTED: {violation} (Execution ID: {execution_id})")
