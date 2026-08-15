import asyncio
import os
import sys

# Ensure the parent directory is in the python path to find nooa
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../labs-OO-Agents/src')))

from nooa.runtime.sandbox.executor import SandboxedExecutor
from nooa.runtime.sandbox.config import SandboxConfig

async def run_demo():
    print("=========================================================")
    print("NOOA Sandbox - Large Codebase & Stress Test Demo")
    print("=========================================================\n")

    workspace_path = os.path.join(os.path.dirname(__file__), 'workspace')

    config = SandboxConfig(
        provider="container",
        workspace=workspace_path,
        allow=[],
        filesystem=True,
    )

    executor = SandboxedExecutor(agent={}, config=config, cell_timeout=120.0)

    print("--- TASK 1: Deep Code Analysis (Safe Filesystem Test) ---")
    print("Instruction: Walk through the Flask repository, count Python files,")
    print("count total lines of code, and write a report to /workspace/flask_report.json.")
    
    analysis_task_code = """
import os
import json

repo_path = '/workspace/flask_repo/src/flask'
report_path = '/workspace/flask_report.json'

total_files = 0
total_lines = 0

print(f"Scanning directory: {repo_path}")
for root, dirs, files in os.walk(repo_path):
    for file in files:
        if file.endswith('.py'):
            total_files += 1
            with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                total_lines += len(f.readlines())

report = {
    'total_python_files': total_files,
    'total_lines_of_code': total_lines
}

with open(report_path, 'w') as f:
    json.dump(report, f, indent=4)

print(f"Analysis complete! Found {total_files} files with {total_lines} total lines of code.")
"""
    
    result = await executor.run_cell(analysis_task_code)
    if result.error:
        print(f"[ERROR] Error during analysis: {result.error}")
    else:
        print("[SUCCESS] Data Processing Output:")
        print(result.stdout.strip())

    print("\n--- TASK 2: Resource Exhaustion Attempt (Memory Test) ---")
    print("Instruction: The agent goes rogue and attempts to allocate 1GB of memory.")
    print("The sandbox is configured to strictly kill processes exceeding 256MB.")
    
    stress_task_code = """
import time
print('Attempting to allocate 500 MB of memory...')
# 500 MB string allocation
huge_list = ["A" * (1024 * 1024) for _ in range(500)]
print('Memory allocated successfully! (Wait, this shouldn\\'t happen)')
time.sleep(2)
"""
    
    result_stress = await executor.run_cell(stress_task_code)
    if result_stress.error:
        print(f"[GUARD] Sandbox Guard Triggered! Error caught:")
        print(f"   {result_stress.error}")
    else:
        print("[CRITICAL] Memory allocation succeeded!")

    print("\n=========================================================")
    print("Demo Completed. Check the 'workspace' folder for the generated report.")

if __name__ == "__main__":
    asyncio.run(run_demo())
