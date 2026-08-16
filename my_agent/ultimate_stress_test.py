import asyncio
import os
import sys
import subprocess

# Ensure parent directory is in python path to resolve nooa
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../labs-OO-Agents/src')))

from nooa.runtime.sandbox import SandboxSession

async def run_ultimate_stress_test():
    workspace_dir = os.path.join(os.path.dirname(__file__), 'workspace')
    os.makedirs(workspace_dir, exist_ok=True)
    
    target_repo_dir = os.path.join(workspace_dir, "django_repo")
    
    print("==================================================================")
    print(" NOOA Sandbox Benchmark: THE ULTIMATE STRESS TEST (Django)")
    print("==================================================================\n")
    
    # Clone Django (Massive repository)
    if not os.path.exists(target_repo_dir):
        print("Cloning django/django (shallow clone)... This is a massive repo!")
        subprocess.run(
            ["git", "clone", "--depth", "1", "https://github.com/django/django.git", target_repo_dir],
            check=True,
            capture_output=True,
            text=True
        )
        print("Clone complete!\n")
    else:
        print("Using existing Django repository in workspace.\n")

    print("Initializing SandboxSession with STRICT limits:")
    print("- Memory Limit: 128 MB (Very tight for big operations)")
    print("- Timeout: 15.0 seconds")
    print("- Fork Bomb Prevention: PIDs limit (Docker internal)\n")
    
    # 128MB is very restrictive. Django is huge.
    async with SandboxSession(workspace=workspace_dir, memory_mb=128, timeout=15.0) as session:
        print("[PHASE 1] Cryptographic File Hashing & Deep AST Traversal...")
        
        # This code will try to hash all python files and parse their ASTs, heavily taxing CPU and Memory.
        heavy_compute_code = """
import os
import ast
import hashlib

repo_path = "/workspace/django_repo/django"
file_hashes = {}
total_files = 0
total_classes = 0

print("Starting massive codebase scan...")

for root, _, files in os.walk(repo_path):
    for file in files:
        if file.endswith(".py"):
            full_path = os.path.join(root, file)
            total_files += 1
            
            with open(full_path, "rb") as f:
                content = f.read()
                
            # Taxing CPU with SHA-256 hashes
            file_hashes[full_path] = hashlib.sha256(content).hexdigest()
            
            # Taxing CPU and Memory with AST parsing
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        total_classes += 1
            except Exception:
                pass

print(f"Success! Hashed and parsed {total_files} files.")
print(f"Discovered {total_classes} classes in Django.")
"""
        res1 = await session.run(heavy_compute_code)
        if res1.error:
            print(f"[GUARD TRIGGERED] Heavy Compute Failed: {res1.error}")
            if res1.stderr:
                print(res1.stderr)
        else:
            print(f"[SUCCESS] Sandbox survived the load! Stdout:\n{res1.stdout}")

        print("\n[PHASE 2] The Fork Bomb Attack (OS Level Crash Attempt)...")
        print("The agent will attempt to spawn infinite processes to bring down the host OS.")
        
        fork_bomb_code = """
import os
import sys

print("Attempting to spawn infinite processes...")
try:
    while True:
        os.fork()
except Exception as e:
    print(f"Fork failed: {e}")
    sys.exit(1)
"""
        res2 = await session.run(fork_bomb_code)
        if res2.error:
            print(f"[INTERCEPTED] Sandbox caught security violation: {res2.error}\n")
        else:
            print(f"[WARNING] Fork bomb finished without catching an error... Stdout:\n{res2.stdout}")
        
        print("\n[PHASE 3] Massive Memory Allocation Attack...")
        print("The agent attempts to allocate 500MB of RAM to crash the server...")
        
        memory_attack_code = """
print("Allocating 500MB of RAM...")
huge_array = bytearray(500 * 1024 * 1024)
print("Allocation successful?! This shouldn't happen.")
"""
        res3 = await session.run(memory_attack_code)
        if res3.error:
            print(f"[INTERCEPTED] Sandbox caught memory violation: {res3.error}\n")
            
        print("==================================================================")
        print(" Sandbox Final Audit Log Trail:")
        print("==================================================================")
        print(session.get_audit_summary())

if __name__ == "__main__":
    asyncio.run(run_ultimate_stress_test())
