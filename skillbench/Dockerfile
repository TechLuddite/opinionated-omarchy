FROM python:3.12-slim

# Base images go stale fast; build with --pull so a rebuild also refreshes this layer.
# (A month-old local base was the single medium finding against the bench this one
# descends from: 42 fixable HIGH CVEs, all Debian packages, none of them ours.)

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/app/
COPY skills.yaml /app/skills.yaml

# Non-root. The app writes only to /data (the SQLite file); everything else is read-only.
RUN useradd -u 10001 -m bench && mkdir -p /data && chown bench:bench /data
USER bench

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz',timeout=3).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "warning"]
