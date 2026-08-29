FROM python:3.12-slim

# Base images go stale fast; build with --pull so a rebuild also refreshes this layer.
# (A month-old local base was the single medium finding against the bench this one
# descends from: 42 fixable HIGH CVEs, all Debian packages, none of them ours.)

# openssh-client is the agentic lane's whole contact surface with the test VMs. It is
# the only package added to the base image, and the chat lane never invokes it.
RUN apt-get update && apt-get install -y --no-install-recommends openssh-client \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/app/
COPY skills.yaml /app/skills.yaml

# Non-root. The app writes only to /data (the SQLite file); everything else is read-only.
RUN useradd -u 10001 -m bench && mkdir -p /data && chown bench:bench /data

# ssh calls getpwuid() for the running uid and refuses to start without a passwd entry
# ("No user exists for uid 1000"). compose runs this image as 1000:1000 so that
# ./data/skillbench.db stays owned by the desktop user, and that uid is deliberately not
# the image's own -- so it needs an entry of its own for the agentic lane's ssh to work.
RUN echo 'composeuser:x:1000:1000:skillbench compose uid:/tmp:/usr/sbin/nologin' >> /etc/passwd

USER bench

# Host and port are parameters because the bench runs on the HOST network namespace
# (see compose.yaml): there is no port publishing to redirect, so the app must bind the
# loopback address and the real port itself.
ENV SB_HOST=0.0.0.0 SB_PORT=8080
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('SB_PORT','8080'),timeout=3).status==200 else 1)"

CMD ["sh", "-c", "exec uvicorn app.main:app --host \"$SB_HOST\" --port \"$SB_PORT\" --log-level warning"]
