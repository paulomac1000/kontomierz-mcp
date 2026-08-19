FROM python:3.12.13-slim@sha256:229a2c5bfa27522db7815ea81f9bed70af17ccb9de9fc7ad142b1877b5830d36 AS verified-artifacts

ARG EXPECTED_SOURCE_REVISION
SHELL ["/bin/sh", "-c"]

COPY dist/ /tmp/dist/
RUN test -n "$EXPECTED_SOURCE_REVISION" \
    && read -r ACTUAL_SOURCE_REVISION < /tmp/dist/SOURCE_REVISION \
    && test "$ACTUAL_SOURCE_REVISION" = "$EXPECTED_SOURCE_REVISION"

FROM python:3.12.13-slim@sha256:229a2c5bfa27522db7815ea81f9bed70af17ccb9de9fc7ad142b1877b5830d36

ARG EXPECTED_SOURCE_REVISION

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN addgroup --system app && adduser --system --ingroup app --uid 10001 app
WORKDIR /app

COPY --from=verified-artifacts /tmp/dist/ /tmp/dist/
RUN cd /tmp/dist \
    && sha256sum --check SHA256SUMS \
    && python -m pip install --no-index --find-links wheelhouse --no-deps --only-binary=:all: --require-hashes -r runtime-linux-x64-py312.lock \
    && python -m pip install --no-index --no-deps kontomierz_mcp-*.whl \
    && rm -rf /tmp/dist

LABEL org.opencontainers.image.revision=$EXPECTED_SOURCE_REVISION

USER app
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 CMD ["python", "-m", "kontomierz_mcp.healthcheck"]
ENTRYPOINT ["kontomierz-mcp"]
