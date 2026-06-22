# Duck Chess — web UI container image.
#
# Base pinned to Python 3.12 on purpose: the MaskablePPO checkpoints were saved
# with this project's .venv (py3.12 / torch 2.11). Loading them under a different
# Python/torch ABI hard-crashes (segfault, exit 139), so DO NOT bump this without
# re-saving the models.
FROM python:3.12-slim

# Faster, cleaner container Python; flush logs straight to the Railway log stream.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Headless pygame: there is no display/audio device in the container. pygame is
# imported at server startup via the game engine, so force the dummy SDL drivers.
ENV PYGAME_DISPLAY=:99 \
    SDL_VIDEODRIVER=dummy \
    SDL_AUDIODRIVER=dummy

WORKDIR /app

# Install deps first so the layer caches across code-only changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App source.
COPY . .

# Web game saves are written here on demand (git-ignored); create it up front.
RUN mkdir -p saved_replays/web

EXPOSE 7890

# server.py reads HOST/PORT from the environment (Railway injects $PORT).
CMD ["python", "web_ui/server.py"]
