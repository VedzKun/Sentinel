import os
from typing import Any, Optional

from nooa.events import ExecutionResult
from nooa.runtime.sandbox.config import SandboxConfig
from nooa.runtime.sandbox.executor import SandboxedExecutor
from nooa.runtime.sandbox.audit import SandboxAuditLogger

class SandboxSession:
    """A high-level, plug-and-play API wrapper for the NOOA Sandbox Execution System.
    
    This class abstracts away the boilerplate of configuring SandboxedExecutor, 
    managing the audit logs, and setting up the environment. It can be used as an 
    async context manager.
    
    Example:
        ```python
        async with SandboxSession(workspace="./workspace") as session:
            result = await session.run("print('Hello World')")
            print(session.get_audit_log())
        ```
    """
    
    def __init__(
        self, 
        workspace: str, 
        provider: str = "container",
        timeout: float = 120.0,
        memory_mb: int = 256,
        block_network: bool = True
    ):
        self.workspace = os.path.abspath(workspace)
        self.audit_log_path = os.path.join(self.workspace, ".audit", "sandbox_audit.jsonl")
        
        # Configure the sandbox securely
        self.config = SandboxConfig(
            provider=provider,
            workspace=self.workspace,
            filesystem=True,  # strictly enforce read-only aside from workspace
            allow=[],
            network=not block_network,
            max_memory_mb=memory_mb,
            audit_log_path=self.audit_log_path,
            require=False,  # degrade gracefully on platforms where guardrails are unavailable (e.g. Windows local provider)
        )
        
        self.executor = SandboxedExecutor(
            agent={}, # dummy agent instance
            config=self.config,
            cell_timeout=timeout
        )
        
        # Instance of the logger to parse reports
        self.logger = SandboxAuditLogger(log_file=self.audit_log_path)

    async def run(self, code: str) -> ExecutionResult:
        """Run a single Python cell inside the locked-down sandbox."""
        return await self.executor.run_cell(code)
        
    def get_audit_summary(self) -> str:
        """Return a formatted string of the most recent audit log."""
        return self.logger.read_audit_summary()

    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.executor.aclose()
