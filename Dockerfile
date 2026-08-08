FROM python:3.12.11-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app
COPY dist/ /tmp/dist/
COPY requirements/runtime-linux-x64-py312.lock /tmp/runtime.lock
RUN cd /tmp/dist \
    && sha256sum --check SHA256SUMS \
    && python -m pip install --no-cache-dir --no-index --find-links /tmp/dist/wheelhouse \
       --no-deps --only-binary=:all: --require-hashes -r /tmp/runtime.lock \
    && python -m pip install --no-cache-dir --no-index --no-deps /tmp/dist/kontomierz_mcp-*.whl \
    && python -m pip check \
    && rm -rf /tmp/dist /tmp/runtime.lock

USER app
ENTRYPOINT ["kontomierz-mcp"]
