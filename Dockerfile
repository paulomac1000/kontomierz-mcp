FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir -e .

EXPOSE 9100 9101 9102

ENV MCP_PORT=9101
ENV REST_API_PORT=9102
ENV HEALTH_PORT=9100
ENV MCP_UNSAFE_PUBLIC_ACCESS_CONFIRMED=1

CMD ["kontomierz-mcp"]
