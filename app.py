"""
HF Spaces entry point — Gradio SDK (free, CPU Basic: 2 vCPU / 16 GB RAM).

gr.mount_gradio_app() mounts an empty Gradio shell onto our FastAPI app so
HF's Gradio SDK is satisfied while the full Duck Chess UI stays at the root.
"""
import os
import sys
import uvicorn
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

os.environ["DUCK_NO_REEXEC"] = "1"                        # no .venv re-exec check
os.environ.setdefault("PORT", "7860")                     # HF Spaces default port

from web_ui.server import app as fastapi_app, ensure_models_downloaded  # noqa: E402

ensure_models_downloaded()   # no-op if models/duck_ppo/ranked/ already has .zip files

import gradio as gr          # noqa: E402  (gradio pre-installed in HF Gradio SDK)

with gr.Blocks() as _demo:
    pass                     # empty shell — real UI is FastAPI's static mount at "/"

# FastAPI is the root app; Gradio is available at /gradio (satisfies the SDK).
app = gr.mount_gradio_app(fastapi_app, _demo, path="/gradio")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "7860"))
    uvicorn.run(app, host="0.0.0.0", port=port)
