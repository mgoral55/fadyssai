FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    TZ=Europe/Warsaw \
    CRETAI_DATA_DIR=/app/data \
    HOME=/root \
    CLAUDE_CONFIG_DIR=/root/.claude

# Doradca AI woła Claude Code CLI (`claude -p`) zamiast SDK dostawcy modelu,
# więc obraz potrzebuje Node.js i samego CLI w przypiętej wersji.
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && npm install -g @anthropic-ai/claude-code@2.1.220 \
    && npm cache clean --force \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data

EXPOSE 8501

# python:3.11-slim nie zawiera curl ani wget
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8501/_stcore/health',timeout=4).status==200 else 1)"

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
