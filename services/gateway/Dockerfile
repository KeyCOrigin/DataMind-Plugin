FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY packages/contracts /app/packages/contracts
COPY packages/mcp-tool-provider /app/packages/mcp-tool-provider
COPY services/dataplane /app/services/dataplane
COPY plugins/datamind-context/vendor/datamind-0.3.2-py3-none-any.whl /app/vendor/
COPY services/gateway /app/services/gateway
RUN pip install --no-cache-dir /app/vendor/datamind-0.3.2-py3-none-any.whl /app/packages/contracts /app/packages/mcp-tool-provider /app/services/dataplane /app/services/gateway
USER 10001
CMD ["datamind-mcp"]
