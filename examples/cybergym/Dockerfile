FROM ghcr.io/astral-sh/uv:0.11.11 AS uv

FROM python:3.12-slim

COPY --from=uv /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    binutils \
    build-essential \
    ca-certificates \
    curl \
    file \
    git \
    jq \
    less \
    ripgrep \
    strace \
    xxd \
    && rm -rf /var/lib/apt/lists/*

# Build against the NOOA source from this checkout. This is why scripts invoke
# Docker with the repository root as the build context: the agent and framework
# revision cannot silently drift apart between reproductions.
WORKDIR /opt/nooa
COPY pyproject.toml uv.lock README.md THIRD_PARTY_NOTICES.md ./
COPY src ./src
COPY packages ./packages
COPY util/eval_pipeline ./util/eval_pipeline
RUN uv export --frozen --no-dev --extra tracing --package nooa \
        --no-emit-project --no-emit-workspace \
        --output-file /tmp/nooa-requirements.txt \
    && uv pip install --system --require-hashes -r /tmp/nooa-requirements.txt \
    && uv pip install --system --no-deps . \
    && rm /tmp/nooa-requirements.txt

WORKDIR /app
RUN mkdir -p /logs/artifacts && ln -s /logs/artifacts /app/artifacts
COPY examples/cybergym/nooa_cybergym ./nooa_cybergym
COPY examples/cybergym/nooa_cybergym/llm_config.yaml ./.nooa/llm_config.yaml

CMD ["python", "-m", "nooa_cybergym.main", "--help"]
