FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY governance_gateway ./governance_gateway
COPY config ./config
COPY data ./data
RUN pip install --no-cache-dir . \
    && python -m governance_gateway.ml.train --out models \
    && python -m governance_gateway.ml.evaluate --card models/model_card.json

RUN useradd --system --uid 10001 app && mkdir -p var && chown -R app /app
USER 10001

EXPOSE 8000
CMD ["uvicorn", "governance_gateway.api:app", "--host", "0.0.0.0", "--port", "8000"]
