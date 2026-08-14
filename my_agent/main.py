import asyncio
import os
import sys

# Add labs-OO-Agents to path so we can import nooa
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "labs-OO-Agents", "src")))

from nooa.runtime.sandbox.config import SandboxConfig
from nooa.runtime.sandbox.executor import SandboxedExecutor

class MockAgent:
    id = "agent_007"
    def hello(self):
        return "Parent says hello!"

async def main():
    # 1. Configure the sandbox to use our new container provider
    # We turn on filesystem controls, block the network, and set a strict 128MB RAM limit.
    config = SandboxConfig(
        provider="local",
        require=False,
        start_method="spawn",
        filesystem=True,
        network=False,
        max_memory_mb=128
    )
    
    agent = MockAgent()
    
    # 2. Initialize the executor
    executor = SandboxedExecutor(agent=agent, config=config, cell_timeout=10.0)
    
    print("--- 1. Running normal code inside the Docker Sandbox ---")
    code_safe = "print('Hello from the secure container!')"
    result_safe = await executor.run_cell(code_safe)
    print(f"Stdout:\n{result_safe.stdout}")
    
    print("\n--- 2. Running a memory bomb inside the Docker Sandbox ---")
    # This attempts to allocate 256MB, but our Sandbox config restricts it to 128MB.
    # Docker should instantly kill the container and our provider should catch it.
    code_malicious = "a = 'x' * 1024 * 1024 * 256\nprint('I should not print')"
    result_malicious = await executor.run_cell(code_malicious)
    print(f"Error Caught:\n{result_malicious.error}")
    
    await executor.aclose()

if __name__ == "__main__":
    # Make sure we're running from the right directory so the audit logger creates the file here
    os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "labs-OO-Agents")))
    asyncio.run(main())
