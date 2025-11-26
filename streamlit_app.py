# streamlit_app.py
import streamlit as st
import subprocess
import sys
import json
from pathlib import Path
import pandas as pd

PROJECT_DIR = Path(__file__).parent.resolve()
GENERATOR_SCRIPT = PROJECT_DIR / "generator.py"
CARGO_FILE = PROJECT_DIR / "cargo_data.json"

st.set_page_config(page_title="Cargo Data Generator", layout="wide")

st.title("Basta sakin ang dating")

col1, col2 = st.columns([1, 2])

with col1:
    st.header("Run")
    run_button = st.button("Generate Cargo Data")

with col2:
   
    output_area = st.empty()
    error_area = st.empty()

def run_generator():
    if not GENERATOR_SCRIPT.exists():
        st.error(f"Generator script not found at: {GENERATOR_SCRIPT}")
        return None

    cmd = [sys.executable, str(GENERATOR_SCRIPT)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_DIR), timeout=600)
    except subprocess.TimeoutExpired:
        st.error("Generator run timed out (600s).")
        return {"returncode": 124, "stdout": "", "stderr": "timeout"}
    result = {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    return result

if run_button:
    with st.spinner("Running generator... (this may take a while if contacting an LLM)"):
        res = run_generator()

    if res is None:
        st.error("Generator did not run.")
    else:
        output_area.code(res["stdout"] or "No stdout")
        if res["returncode"] != 0:
            error_area.error(res["stderr"] or f"Process exited with code {res['returncode']}")
        else:
            st.success("Generator completed successfully.")
            if res["stderr"]:
                st.warning("Generator produced stderr output; check logs below.")
                error_area.warning(res["stderr"])

# Show current cargo_data.json if present
st.header("Generated Data")
if CARGO_FILE.exists():
    try:
        with open(CARGO_FILE, "r", encoding="utf-8") as f:
            cargo = json.load(f)
    except Exception as e:
        st.error(f"Failed to read `{CARGO_FILE.name}`: {e}")
        cargo = None

    if cargo:
        # Show top-level keys as tabs
        tabs = st.tabs(list(cargo.keys()))
        for tab, (key, value) in zip(tabs, cargo.items()):
            with tab:
                st.subheader(f"{key} ({len(value) if isinstance(value, list) else '1'})")
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    try:
                        df = pd.json_normalize(value)
                        st.dataframe(df)
                        csv_bytes = df.to_csv(index=False).encode("utf-8")
                        st.download_button(f"Download {key} as CSV", data=csv_bytes, file_name=f"{key}.csv", mime="text/csv")
                    except Exception:
                        st.json(value)
                        st.download_button(f"Download {key} as JSON", data=json.dumps(value, indent=2), file_name=f"{key}.json", mime="application/json")
                else:
                    st.json(value)
                    st.download_button(f"Download {key} as JSON", data=json.dumps(value, indent=2), file_name=f"{key}.json", mime="application/json")

else:
    st.info("No `cargo_data.json` found yet. Click 'Generate Cargo Data' to produce it.")