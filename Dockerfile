# Duck Chess — Hugging Face Spaces (Docker SDK)
# Free CPU tier: 2 vCPUs, 16 GB RAM — plenty for torch + MaskablePPO.
# HF Spaces requires the app to listen on port 7860.

FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies (torch is large; build layer is cached by Docker)
COPY requirements-render.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the full application (model in models/duck_ppo/ranked/ is included)
COPY . .

# PORT=7860 is the HF Spaces default. HOST/DUCK_NO_REEXEC are for server.py.
ENV PORT=7860 \
    HOST=0.0.0.0 \
    DUCK_NO_REEXEC=1

EXPOSE 7860

# server.py __main__ calls ensure_models_downloaded() then starts uvicorn.
CMD ["python", "web_ui/server.py"]
