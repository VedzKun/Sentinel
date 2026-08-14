import argparse
import json
import time
import os
import sys

def color_text(text: str, color_code: str) -> str:
    """Helper to colorize terminal output."""
    return f"\033[{color_code}m{text}\033[0m"

def print_event(data: dict):
    """Format and print a single event to the terminal."""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(data.get("timestamp", 0)))
    event_type = data.get("event_type")
    
    print(f"\n[{color_text(timestamp, '90')}] {color_text(event_type.upper(), '94')}")
    
    if event_type == "execution_started":
        print(f"  Agent ID: {data.get('agent_id')}")
        print(f"  Exec ID : {data.get('execution_id')}")
        print(f"  Code    :\n{color_text(data.get('code', ''), '36')}")
        
    elif event_type == "execution_completed":
        print(f"  Exec ID : {data.get('execution_id')}")
        violation = data.get("violation")
        if violation:
            print(f"  {color_text('VIOLATION DETECTED', '91;1')}: {color_text(violation, '91')}")
            print(f"  Error   : {data.get('error')}")
        elif data.get("error"):
            print(f"  {color_text('ERROR', '31')}: {data.get('error')}")
        else:
            print(f"  {color_text('SUCCESS', '32')}")
            
        stdout = data.get("stdout")
        if stdout:
            print(f"  Stdout  :\n{color_text(stdout, '37')}")

def stream_logs(file_path: str):
    """Tail the log file like 'tail -f'."""
    print(color_text(f"Listening for live sandbox events on {file_path}...", "92"))
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            # Seek to end
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                try:
                    data = json.loads(line)
                    print_event(data)
                except json.JSONDecodeError:
                    pass
    except FileNotFoundError:
        print(color_text(f"Log file {file_path} not found. Start an agent to generate logs.", "31"))
    except KeyboardInterrupt:
        print("\nExiting stream...")

def export_logs(file_path: str, output_path: str):
    """Export the JSONL logs to a readable text file."""
    try:
        with open(file_path, "r", encoding="utf-8") as fin, open(output_path, "w", encoding="utf-8") as fout:
            for line in fin:
                try:
                    data = json.loads(line)
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(data.get("timestamp", 0)))
                    fout.write(f"[{timestamp}] {data.get('event_type')}\n")
                    for k, v in data.items():
                        if k not in ["timestamp", "event_type"]:
                            fout.write(f"  {k}: {v}\n")
                    fout.write("-" * 40 + "\n")
                except json.JSONDecodeError:
                    continue
        print(color_text(f"Successfully exported logs to {output_path}", "32"))
    except FileNotFoundError:
        print(color_text(f"Log file {file_path} not found.", "31"))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NOOA Sandbox Audit CLI")
    parser.add_argument("--file", default="sandbox_audit.jsonl", help="Path to the audit log file.")
    parser.add_argument("--export", type=str, help="Export logs to the specified text file instead of streaming.")
    
    args = parser.parse_args()
    
    # On Windows, we need to enable ANSI colors
    if sys.platform == "win32":
        os.system('color')
        
    if args.export:
        export_logs(args.file, args.export)
    else:
        stream_logs(args.file)
