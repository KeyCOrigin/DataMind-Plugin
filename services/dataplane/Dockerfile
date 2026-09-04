FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY packages/contracts /app/packages/contracts
COPY plugins/datamind-context/vendor/datamind-0.3.2-py3-none-any.whl /app/vendor/
COPY services/dataplane /app/services/dataplane
RUN pip install --no-cache-dir /app/vendor/datamind-0.3.2-py3-none-any.whl /app/packages/contracts /app/services/dataplane
USER 10001
EXPOSE 8080
CMD ["uvicorn", "datamind_dataplane.server:app", "--host", "0.0.0.0", "--port", "8080"]
