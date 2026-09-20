FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY gym/ gym/
COPY config/ config/
COPY scripts/ scripts/
COPY --from=web /web/dist web/dist
ENV PATH="/app/.venv/bin:$PATH" GYM_DATA_DIR=/app/data GYM_EMBEDDED_WORKER=0
RUN mkdir -p /app/data
EXPOSE 8787
CMD ["uvicorn", "gym.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8787"]
