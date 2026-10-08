# Imagen autocontenida: Python + Claude Code CLI. No requiere Python ni Node en el host.
FROM node:22-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @anthropic-ai/claude-code \
    && npm cache clean --force

WORKDIR /app
COPY requirements.txt .
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    STUDY_AGENT_VAULT=/vault

COPY study_agent ./study_agent
COPY exams ./exams
COPY tests ./tests
COPY config.example.yaml ./
# Config por defecto; monta tu propio config.yaml en /app/config.yaml para cambiarla
RUN cp config.example.yaml config.yaml \
    && mkdir -p .cache /vault && chown -R node:node /app /vault

# Claude Code no debe correr como root
USER node
ENTRYPOINT ["python", "-m", "study_agent"]
CMD ["--help"]
