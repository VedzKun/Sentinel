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
        # Ensure the directory exists
        log_dir = os.path.dirname(os.path.abspath(self.log_file))
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

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
            elif "Name resolution" in error_msg or "Temporary failure in name resolution" in error_msg:
                violation = "NETWORK_ACCESS_DENIED"

        self._write_event("execution_completed", {
            "execution_id": execution_id,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "error": error_msg,
            "violation": violation
        })

        if violation:
            logger.warning(f"SANDBOX VIOLATION DETECTED: {violation} (Execution ID: {execution_id})")
            
    def read_audit_summary(self) -> str:
        """Parse the JSONL log file and return a human-readable summary of the last execution."""
        if not os.path.exists(self.log_file):
            return "No audit logs found."
            
        summary = ["--- Sandbox Audit Log Summary ---"]
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
            # Group events by execution_id
            executions = {}
            for line in lines:
                event = json.loads(line)
                exec_id = event.get("execution_id")
                if not exec_id:
                    continue
                if exec_id not in executions:
                    executions[exec_id] = {}
                executions[exec_id][event["event_type"]] = event
                
            if not executions:
                return "No execution events found in audit log."
                
            # Summarize the most recent execution
            latest_exec_id = list(executions.keys())[-1]
            events = executions[latest_exec_id]
            
            start_event = events.get("execution_started")
            end_event = events.get("execution_completed")
            
            summary.append(f"Execution ID: {latest_exec_id}")
            if start_event:
                summary.append(f"Agent ID: {start_event.get('agent_id')}")
                # Truncate code for display
                code = start_event.get("code", "")
                summary.append(f"Code Executed:\n{'-'*30}\n{code.strip()}\n{'-'*30}")
            
            if end_event:
                violation = end_event.get("violation")
                if violation:
                    summary.append(f"[VIOLATION DETECTED]: {violation}")
                    summary.append(f"Error Details: {end_event.get('error')}")
                else:
                    summary.append("[STATUS]: Clean Execution (No Violations)")
                
                stdout = end_event.get("stdout", "").strip()
                if stdout:
                    summary.append(f"Stdout:\n{stdout}")
                    
        except Exception as e:
            return f"Error reading audit log: {e}"
            
        return "\n".join(summary)
