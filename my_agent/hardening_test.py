import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../labs-OO-Agents/src')))

from nooa.runtime.sandbox import SandboxSession

async def run_tests():
    workspace_dir = os.path.join(os.path.dirname(__file__), 'workspace')
    os.makedirs(workspace_dir, exist_ok=True)
    
    print("=========================================================")
    print(" NOOA Sandbox - Extreme Hardening Tests")
    print("=========================================================\n")

    print("\n--- TEST 1: Memory Exhaustion (Should instantly fail) ---")
    # Set a tiny 64MB limit to easily exhaust it
    async with SandboxSession(workspace=workspace_dir, memory_mb=64) as session:
        # Try to allocate ~250MB
        code_mem = """
try:
    print('Attempting to allocate 250MB...')
    huge_list = ["A" * (1024 * 1024) for _ in range(250)]
    print('[CRITICAL] Memory allocation succeeded when it should have failed!')
except MemoryError:
    print('[GUARD ACTED] Python MemoryError caught successfully.')
    raise
except Exception as e:
    print(f'Other error: {e}')
    raise
"""
        result = await session.run(code_mem)
        if result.error:
            print(f"Sandbox intercepted execution: {result.error}")
        else:
            print("[FAIL] Execution passed.")
            
    print("\n--- TEST 2: Timeout (Should kill container) ---")
    # 2 seconds timeout for a 5 second sleep
    async with SandboxSession(workspace=workspace_dir, timeout=2.0) as session:
        code_timeout = """
import time
print('Sleeping for 5 seconds...')
time.sleep(5)
print('Awake! (Should not reach here)')
"""
        result = await session.run(code_timeout)
        if result.error:
            print(f"Sandbox intercepted execution: {result.error}")
        else:
            print("[FAIL] Execution passed.")

if __name__ == "__main__":
    asyncio.run(run_tests())
