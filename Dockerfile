FROM verilator/verilator:v5.050@sha256:c531ae1e5da8e7293a2bd6793060c2bf484dac358746e69bcc3e689ec265b299

USER root

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y python3-venv \
    && python3 -m venv /opt/rtl-detective \
    && /opt/rtl-detective/bin/pip install --no-cache-dir --upgrade pip \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/rtl-detective/bin:$PATH" \
    ARTIFACTS_DIRECTORY=/app/artifacts \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir --only-binary=:all: -r requirements.lock

COPY --chown=1000:1000 . .
RUN mkdir -p /app/artifacts && chown 1000:1000 /app /app/artifacts

USER 1000:1000
EXPOSE 10000

ENTRYPOINT []
CMD ["sh", "-c", "python -m backend.cli serve --host 0.0.0.0 --port ${PORT:-10000}"]
