FROM python:3.12.11-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

ARG EXPECTED_SOURCE_REVISION

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN addgroup --system app && adduser --system --ingroup app --uid 10001 app
WORKDIR /app

COPY dist/ /tmp/dist/
RUN test -n "$EXPECTED_SOURCE_REVISION" \
    && cd /tmp/dist \
    && sha256sum --check SHA256SUMS \
    && test "$(cat SOURCE_REVISION)" = "$EXPECTED_SOURCE_REVISION" \
    && python -m pip install --no-index --find-links wheelhouse --no-deps --only-binary=:all: --require-hashes -r runtime-linux-x64-py312.lock \
    && python -m pip install --no-index --no-deps kontomierz_mcp-*.whl \
    && rm -rf /tmp/dist

LABEL org.opencontainers.image.revision=$EXPECTED_SOURCE_REVISION

USER app
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 CMD ["python", "-m", "kontomierz_mcp.healthcheck"]
ENTRYPOINT ["kontomierz-mcp"]
