# Imagen autocontenida: Python + Claude Code CLI. No requiere Python ni Node en el host.
FROM node:22-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @anthropic-ai/claude-code \
    && npm cache clean --force

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY study_agent ./study_agent
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir . \
    && mkdir -p /vault /home/node/.cache/study-agent /home/node/.config/study-agent \
    && chown -R node:node /vault /home/node/.cache /home/node/.config
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    STUDY_AGENT_VAULT=/vault

# Claude Code no debe correr como root
USER node
ENTRYPOINT ["study-agent"]
CMD ["--help"]
