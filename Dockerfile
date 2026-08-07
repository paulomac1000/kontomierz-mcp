FROM python:3.12.11-slim@sha256:9fb9f94e7b4a4b73d779fbf1b1ef8c918514d9f6c1b0e6e646bfe1d83d214b99

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app
COPY dist/ /tmp/dist/
RUN cd /tmp/dist \
    && sha256sum --check SHA256SUMS \
    && python -m pip install --no-cache-dir --no-index \
       --find-links /tmp/dist/wheelhouse /tmp/dist/kontomierz_mcp-*.whl \
    && python -m pip check \
    && rm -rf /tmp/dist

USER app
ENTRYPOINT ["kontomierz-mcp"]
