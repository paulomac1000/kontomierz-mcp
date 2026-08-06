FROM python:3.12-slim@sha256:646fb0bca3dd3ea1bcc6feb72c17ed16eed6e10cffc732fcc1478bd3e7f02d7b

RUN groupadd --system app && useradd --system --gid app --home-dir /app app
WORKDIR /app

# CI resolves one wheelhouse, tests the application wheel against it, and
# publishes the same files. Runtime installation never contacts an index.
COPY dist/ /tmp/dist/
RUN python -m pip install --no-cache-dir --no-index \
      --find-links=/tmp/dist/wheelhouse \
      /tmp/dist/kontomierz_mcp-*.whl \
    && rm -rf /tmp/dist \
    && chown -R app:app /app

USER app
ENV MCP_TRANSPORT=stdio \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

ENTRYPOINT ["kontomierz-mcp"]
