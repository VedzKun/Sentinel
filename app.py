import streamlit as st
import subprocess
import os
import sys

def main():
    st.set_page_config(page_title="NOOA Auditor", page_icon="🛡️", layout="wide")
    
    st.title("🛡️ NOOA Secure Sandbox Auditor")
    st.markdown("Automated codebase auditor running inside a secure sandbox container.")
    
    with st.form("audit_form"):
        repo_url = st.text_input("GitHub Repository URL", placeholder="https://github.com/django/django")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            memory_mb = st.number_input("Memory Limit (MB)", min_value=128, max_value=4096, value=256, step=128)
        with col2:
            timeout = st.number_input("Timeout (seconds)", min_value=10, max_value=600, value=60, step=10)
        with col3:
            provider = st.selectbox("Provider", ["container", "local"], index=0)
        with col4:
            st.markdown("<br>", unsafe_allow_html=True)
            keep_repo = st.checkbox("Keep Cloned Repo")
            
        submit_button = st.form_submit_button(label="Run Audit")
        
    if submit_button:
        if not repo_url:
            st.error("Please provide a repository URL.")
            return
            
        st.info(f"Starting audit for {repo_url}...")
        
        # Determine paths
        script_dir = os.path.dirname(os.path.abspath(__file__))
        audit_script = os.path.join(script_dir, "audit.py")
        
        cmd = [
            sys.executable,
            audit_script,
            repo_url,
            "--memory-mb", str(int(memory_mb)),
            "--timeout", str(float(timeout)),
            "--provider", provider
        ]
        if keep_repo:
            cmd.append("--keep-repo")
            
        st.markdown("### Execution Log")
        log_container = st.empty()
        
        # Run process and stream output
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace"
            )
            
            output_log = []
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    output_log.append(line.rstrip())
                    # Display the last 50 lines to keep UI responsive
                    display_log = "\n".join(output_log[-50:])
                    log_container.code(display_log, language="text")
                    
            return_code = process.poll()
            if return_code == 0:
                st.success("Audit completed successfully!")
            else:
                st.error(f"Audit failed with exit code {return_code}.")
                
            # Final output rendering
            st.markdown("### Final Complete Output")
            st.code("\n".join(output_log), language="text")
            
        except Exception as e:
            st.error(f"Failed to start the process: {e}")

if __name__ == "__main__":
    main()
