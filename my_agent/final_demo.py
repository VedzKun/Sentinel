import asyncio
import os
import sys

# Ensure the parent directory is in the python path to find nooa
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../labs-OO-Agents/src')))

from nooa.runtime.sandbox import SandboxSession

async def run_demo():
    print("=========================================================")
    print(" NOOA Sandbox - One-Click Secure Execution Demo")
    print("=========================================================\n")

    # Define our workspace directory
    workspace_dir = os.path.join(os.path.dirname(__file__), 'workspace')

    print("Initializing SandboxSession...")
    # The new SandboxSession handles all the complex config and sets up audit logging!
    async with SandboxSession(workspace=workspace_dir) as session:
        
        print("\n--- TASK: Malicious Network Access Attempt ---")
        print("The agent is instructed to exfiltrate data to an external server.")
        print("We expect the sandbox to block this and log a network violation.")
        
        malicious_code = """
import urllib.request
try:
    print('Attempting to connect to external server...')
    response = urllib.request.urlopen('http://example.com', timeout=2)
    print('Connection successful! Data leaked!')
except Exception as e:
    print(f'Connection failed: {e}')
    raise
"""
        # Execute the code safely
        result = await session.run(malicious_code)
        
        if result.error:
            print(f"[GUARD ACTED] Sandbox successfully intercepted the execution.")
            print(f"Error caught: {result.error}")
        else:
            print("[CRITICAL] Code executed successfully when it should have been blocked!")
            
        print("\n=========================================================")
        print(" Demo Completed. Printing the Audit Log Summary below:")
        print("=========================================================\n")
        
        # Pull the audit log for the hiring manager/audience
        print(session.get_audit_summary())

if __name__ == "__main__":
    asyncio.run(run_demo())
