import asyncio
import os
import sys
import json

# Ensure parent directory is in python path to resolve nooa
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../labs-OO-Agents/src')))

from nooa.runtime.sandbox import SandboxSession

async def run_data_analyst_demo():
    workspace_dir = os.path.join(os.path.dirname(__file__), 'workspace')
    os.makedirs(workspace_dir, exist_ok=True)
    
    print("==================================================================")
    print(" NOOA Sandbox: Real-World Data Analyst Agent Scenario")
    print("==================================================================\n")
    
    # 1. Generate a "dirty" dataset representing real-world messy data
    dirty_data_path = os.path.join(workspace_dir, "messy_orders.csv")
    print(f"[HOST] Generating messy dataset at {dirty_data_path}...")
    with open(dirty_data_path, "w", encoding="utf-8") as f:
        f.write("order_id,date,customer,total\n")
        f.write("1,2026-01-15,Alice,$1,200.50\n")
        f.write("2,2026/02/01,Bob,$45.00\n")
        f.write("3,Jan 3rd,Charlie,INVALID_PRICE\n")
        f.write("4,2026-02-15,Alice,$3,150.00\n")
        f.write("5,2026-01-20,David,$150.75\n")
        
    print("\n[SCENARIO] The user asks the AI Agent:")
    print('  "Clean this messy CSV. Parse the dates to YYYY-MM. Filter out invalid prices. ')
    print('   Calculate the total revenue per user and save the results to a clean JSON file."\n')
    
    print("Initializing SandboxSession (The agent is given access ONLY to the workspace)...")
    
    # We instantiate the session. Notice how clean the API is!
    async with SandboxSession(workspace=workspace_dir, timeout=30.0) as session:
        
        # This is the code the AI agent decided to write and run to accomplish the task
        agent_generated_code = """
import csv
import json
import os
import re
from datetime import datetime

input_file = '/workspace/messy_orders.csv'
output_file = '/workspace/clean_revenue.json'

revenue_by_user = {}
processed_rows = 0
dropped_rows = 0

with open(input_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        # Clean price (e.g., "$1,200.50" -> 1200.50)
        raw_price = row['total']
        clean_price_str = re.sub(r'[^0-9.]', '', raw_price)
        
        try:
            if not clean_price_str:
                raise ValueError("Empty price")
            price = float(clean_price_str)
        except ValueError:
            dropped_rows += 1
            continue
            
        user = row['customer']
        if user not in revenue_by_user:
            revenue_by_user[user] = 0.0
            
        revenue_by_user[user] += price
        processed_rows += 1

# Save the final structured report
report = {
    "status": "success",
    "metrics": {
        "processed": processed_rows,
        "dropped": dropped_rows
    },
    "revenue_by_user": revenue_by_user
}

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=4)

print(f"Data cleaning complete! Processed {processed_rows} rows, dropped {dropped_rows} rows.")
"""
        print("[AGENT] Executing Python script inside the secure sandbox...")
        result = await session.run(agent_generated_code)
        
        if result.error:
            print(f"[ERROR] Agent code failed: {result.error}")
            if result.stderr:
                print(f"Stderr:\n{result.stderr}")
        else:
            print(f"[SUCCESS] Sandbox stdout:\n{result.stdout}")

        # Check output report file on host
        report_file = os.path.join(workspace_dir, "clean_revenue.json")
        if os.path.exists(report_file):
            print("\n[HOST] Validating the agent's output file...")
            with open(report_file, "r") as f:
                data = json.load(f)
            
            print("--- Final Cleaned Data Report ---")
            print(json.dumps(data, indent=2))
        else:
            print("[ERROR] Output file was not created by the agent.")
            
        print("\n==================================================================")
        print(" Sandbox Audit Log Trail:")
        print("==================================================================")
        print(session.get_audit_summary())

if __name__ == "__main__":
    asyncio.run(run_data_analyst_demo())
